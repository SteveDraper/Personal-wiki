"""
Crawl a same-origin static HTML site into a folder tree under ``raw/`` for vault ingest.

Suited for documentation mirrors (e.g. Donovan VGA Planets, Planets.nu help). For
forum-shaped JSON:API exports, use ``flarum_discussions_export.py`` instead.

- Same-origin HTML pages only; discovers links from ``<a href>``, ``<area href>``,
  ``<frame src>``, ``<iframe src>``, and respects ``<base href>`` for relative URLs.
- Honors ``robots.txt`` ``Disallow`` path prefixes for ``User-agent: *`` (small
  parser; stdlib ``robotparser`` misparses some legacy files).
- Optional path-prefix exclusions (Donovan’s ``/museum/`` is applied automatically
  only when crawling donovansvgap.com hosts).
- No incremental change detection: full crawl each run.

Layout::

    <output-dir>/
      _export.runs.jsonl          # one JSON object per run (stats only)
      <path-mirror>/             # URL path mirrored as directories
        page.meta.yaml           # JSON inside .yaml (same convention as Flarum exporter)
        body.html                # decoded page text (UTF-8 on disk)

Path mirror: URL path ``/a/b/c.htm`` → ``a/b/c/``; extensionless ``/a/b/c`` → ``a/b/c/``;
``/`` → ``_root/``.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import zlib
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

DEFAULT_USER_AGENT = "static-html-site-export/0.2 (+personal wiki raw ingest)"

_ILLEGAL_FS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Conservative cap to avoid pulling huge binaries if mis-linked.
MAX_BODY_BYTES = 8 * 1024 * 1024


def normalize_base_url(url: str) -> str:
    s = url.strip()
    if not s:
        raise ValueError("base URL is empty")
    if not urllib.parse.urlparse(s).scheme:
        s = "https://" + s
    p = urllib.parse.urlparse(s)
    if not p.scheme or not p.netloc:
        raise ValueError(f"could not parse base URL: {url!r}")
    return f"{p.scheme}://{p.netloc}".rstrip("/")


def site_registrable_domain(netloc: str) -> str:
    """Rough host key: lowercase, strip common leading ``www.``."""
    h = netloc.lower().split("@")[-1].split(":")[0]
    if h.startswith("www."):
        h = h[4:]
    return h


def is_donovansvgap_host(base: str) -> bool:
    return site_registrable_domain(urllib.parse.urlparse(base).netloc) == "donovansvgap.com"


def safe_segment(name: str, max_len: int = 120) -> str:
    t = name.replace("/", "__").strip()
    t = _ILLEGAL_FS.sub("_", t)
    t = t.strip(" .")
    if not t:
        t = "unnamed"
    return t[:max_len]


def canonical_url(url: str) -> str:
    """Stable string for de-duplication and visited set (query/fragment stripped)."""
    p = urllib.parse.urlparse(url.strip())
    scheme = p.scheme.lower()
    if scheme == "http":
        scheme = "https"
    netloc = p.netloc.lower()
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))


def same_origin(base: str, url: str) -> bool:
    b = urllib.parse.urlparse(base)
    u = urllib.parse.urlparse(url)
    return (u.scheme in ("http", "https")) and (u.netloc.lower() == b.netloc.lower())


def normalize_path_prefix(prefix: str) -> str:
    p = prefix.strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    return p


def path_matches_prefix_list(path: str, prefixes: list[str]) -> bool:
    """True if ``path`` equals a prefix or is under ``prefix/`` (prefix match)."""
    p = path or "/"
    if not p.startswith("/"):
        p = "/" + p
    pl = p.lower()
    for raw in prefixes:
        pr = normalize_path_prefix(raw).lower().rstrip("/")
        if not pr:
            continue
        if pl == pr or pl.startswith(pr + "/"):
            return True
    return False


def url_to_output_relpath(url: str) -> Path:
    """Map canonical page URL to a relative directory under output root."""
    p = urllib.parse.urlparse(url)
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return Path("_root")
    out: list[str] = []
    for i, seg in enumerate(parts):
        is_last = i == len(parts) - 1
        low = seg.lower()
        if is_last and low.endswith((".htm", ".html")):
            stem = seg[: -4] if low.endswith(".htm") else seg[: -5]
            stem = stem or "index"
            out.append(safe_segment(stem))
        else:
            out.append(safe_segment(seg))
    return Path(*out) if out else Path("_root")


def charset_from_headers(content_type: str | None) -> str | None:
    if not content_type:
        return None
    m = re.search(r"charset\s*=\s*([\w_.-]+)", content_type, re.I)
    return m.group(1).strip("'\"") if m else None


def charset_from_html_snippet(text: str) -> str | None:
    m = re.search(
        r'<meta[^>]+charset\s*=\s*["\']?([\w_.-]+)',
        text[:8000],
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(
        r'http-equiv\s*=\s*["\']Content-Type["\'][^>]+content\s*=\s*["\'][^"\']*charset\s*=\s*([\w_.-]+)',
        text[:8000],
        re.I,
    )
    if m:
        return m.group(1)
    return None


def http_decompress(body: bytes, content_encoding: str | None) -> bytes:
    """Decode bytes after HTTP transfer codings (``Content-Encoding``)."""
    if not content_encoding:
        return body
    # Use first token only; chained codings are rare for HTML crawls.
    ce = content_encoding.split(",")[0].strip().lower()
    if ce in ("gzip", "x-gzip"):
        return gzip.decompress(body)
    if ce == "deflate":
        try:
            return zlib.decompress(body, -zlib.MAX_WBITS)
        except zlib.error:
            return zlib.decompress(body)
    if ce == "br":
        try:
            import brotli  # type: ignore[import-untyped]
        except ImportError as e:
            raise ValueError(
                "response is Brotli-compressed (Content-Encoding: br); "
                "install the brotli package or crawl a mirror without br"
            ) from e
        return brotli.decompress(body)
    return body


def decode_body(raw: bytes, content_type: str | None) -> tuple[str, str]:
    """Return (text, encoding_used)."""
    enc = charset_from_headers(content_type)
    if enc:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            pass
    snippet = raw[:8000].decode("latin-1", errors="replace")
    enc2 = charset_from_html_snippet(snippet)
    if enc2:
        try:
            return raw.decode(enc2), enc2
        except (UnicodeDecodeError, LookupError):
            pass
    return raw.decode("utf-8", errors="replace"), "utf-8 (fallback)"


@dataclass
class FetchResult:
    final_url: str
    status: int
    content_type: str | None
    body_text: str
    encoding_used: str
    raw_bytes: int


def http_get(url: str, sleep: float, user_agent: str) -> FetchResult:
    if sleep > 0:
        time.sleep(sleep)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=120) as resp:
        status = getattr(resp, "status", 200)
        final = resp.geturl()
        ct = resp.headers.get("Content-Type")
        enc_hdr = resp.headers.get("Content-Encoding")
        raw = resp.read(MAX_BODY_BYTES + 1)
    if len(raw) > MAX_BODY_BYTES:
        raise ValueError(f"response larger than {MAX_BODY_BYTES} bytes")
    raw = http_decompress(raw, enc_hdr)
    text, enc = decode_body(raw, ct)
    return FetchResult(
        final_url=final,
        status=status,
        content_type=ct,
        body_text=text,
        encoding_used=enc,
        raw_bytes=len(raw),
    )


class LinkExtractor(HTMLParser):
    """Collect same-page navigation targets; respects ``<base href>``."""

    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._page_url = page_url
        self._base = page_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: v for k, v in attrs if v is not None}
        if tag == "base" and "href" in ad:
            self._base = urllib.parse.urljoin(self._page_url, ad["href"])
            return
        b = self._base
        if tag in ("a", "area") and "href" in ad:
            self.links.append(urllib.parse.urljoin(b, ad["href"]))
        if tag in ("frame", "iframe") and "src" in ad:
            self.links.append(urllib.parse.urljoin(b, ad["src"]))


def extract_links(html: str, page_url: str) -> list[str]:
    ex = LinkExtractor(page_url)
    try:
        ex.feed(html)
    except Exception:
        pass
    ex.close()
    out: list[str] = []
    for raw in ex.links:
        u = urllib.parse.urldefrag(raw)[0].strip()
        if u:
            out.append(u)
    return out


def looks_like_html(text: str) -> bool:
    s = text.lstrip()[:500].lower()
    return bool(
        s.startswith("<!doctype html")
        or s.startswith("<html")
        or s.startswith("<!--")
        or s.startswith("<!doctype ")
    )


def fetch_robots_disallow_prefixes(base: str, sleep: float, user_agent: str) -> list[str]:
    """Return non-empty Disallow path prefixes for ``User-agent: *`` from robots.txt."""
    if sleep > 0:
        time.sleep(sleep)
    url = f"{base}/robots.txt"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=60) as resp:
        enc_hdr = resp.headers.get("Content-Encoding")
        raw_b = resp.read()
    raw_b = http_decompress(raw_b, enc_hdr)
    raw = raw_b.decode("utf-8", errors="replace")
    in_star = False
    out: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        low = line.lower()
        if low.startswith("user-agent:"):
            ua = line.split(":", 1)[1].strip()
            in_star = ua == "*"
            continue
        if not in_star:
            continue
        if low.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                out.append(path)
    return out


def path_blocked_by_robots(path: str, disallow_prefixes: list[str]) -> bool:
    """True if URL path is prefixed by a Disallow rule (prefix match)."""
    p = path or "/"
    if not p.startswith("/"):
        p = "/" + p
    pl = p.lower()
    for d in disallow_prefixes:
        dl = d.lower()
        if pl.startswith(dl):
            return True
    return False


def append_run_log(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def default_seeds_for_base(base: str) -> list[str]:
    if is_donovansvgap_host(base):
        return [
            f"{base}/",
            f"{base}/main.htm",
            f"{base}/menu.htm",
        ]
    return [f"{base}/"]


def default_exclude_path_prefixes_for_base(base: str) -> list[str]:
    if is_donovansvgap_host(base):
        return ["/museum"]
    return []


def resolve_seed_urls(base: str, seeds: list[str]) -> list[str]:
    out: list[str] = []
    for s in seeds:
        t = s.strip()
        if not t:
            continue
        if urllib.parse.urlparse(t).scheme:
            out.append(t)
        else:
            out.append(urllib.parse.urljoin(base + "/", t))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Crawl a static HTML site (same origin) into raw/ folders: "
            "body.html + page.meta.yaml per URL path."
        )
    )
    ap.add_argument(
        "--base-url",
        default="https://www.donovansvgap.com",
        help="Site origin (scheme + host, no trailing path). Default keeps Donovan export behavior.",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write mirrored pages (e.g. Personal-wiki/raw/donovansvgap).",
    )
    ap.add_argument(
        "--run-log",
        type=Path,
        required=True,
        help="Append one JSON Lines record per run (stats).",
    )
    ap.add_argument(
        "--seed",
        action="append",
        dest="seeds",
        default=None,
        help=(
            "Starting URL (repeatable). Absolute or path relative to --base-url. "
            "Default: / and Donovan main/menu for donovansvgap.com; else only /."
        ),
    )
    ap.add_argument(
        "--exclude-path-prefix",
        action="append",
        dest="exclude_path_prefixes",
        default=None,
        help=(
            "Do not fetch URLs whose path equals this prefix or lies under it (repeatable). "
            "Default: /museum for donovansvgap.com hosts only; otherwise none. "
            "If you pass this flag at least once, host defaults are replaced by your list."
        ),
    )
    ap.add_argument(
        "--no-host-default-excludes",
        action="store_true",
        help=(
            "Do not apply host-specific default exclusions (e.g. skip /museum on donovansvgap.com). "
            "Still honors explicit --exclude-path-prefix values."
        ),
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep before each HTTP GET (default: 1.0).",
    )
    ap.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Stop after this many successfully written pages (testing).",
    )
    ap.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help=f"HTTP User-Agent (default: {DEFAULT_USER_AGENT!r}).",
    )
    ap.add_argument(
        "--robots-on-error",
        choices=("fail", "allow-all"),
        default="fail",
        help=(
            "If robots.txt cannot be read: fail the run (default) or continue with no "
            "Disallow rules (still applies --exclude-path-prefix)."
        ),
    )
    args = ap.parse_args()

    base = normalize_base_url(args.base_url)
    out_root: Path = args.output_dir.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    if args.exclude_path_prefixes is not None:
        exclude_prefixes = [x for x in args.exclude_path_prefixes if x is not None]
    elif args.no_host_default_excludes:
        exclude_prefixes = []
    else:
        exclude_prefixes = default_exclude_path_prefixes_for_base(base)

    if args.seeds is not None:
        seed_urls = resolve_seed_urls(base, args.seeds)
    else:
        seed_urls = default_seeds_for_base(base)

    robots_url = f"{base}/robots.txt"
    disallow_prefixes: list[str] = []
    robots_error: str | None = None
    try:
        disallow_prefixes = fetch_robots_disallow_prefixes(base, args.sleep, args.user_agent)
    except Exception as e:
        robots_error = str(e)
        if args.robots_on_error == "fail":
            print(f"ERROR: could not read {robots_url}: {e}", file=sys.stderr)
            sys.exit(1)
        print(
            f"WARN: could not read {robots_url} ({e}); continuing with no robots Disallow rules.",
            file=sys.stderr,
        )

    print(f"Robots Disallow prefixes ({len(disallow_prefixes)}): {disallow_prefixes}", file=sys.stderr)
    if exclude_prefixes:
        print(f"Extra path exclusions ({len(exclude_prefixes)}): {exclude_prefixes}", file=sys.stderr)

    def allowed_by_policy(url: str) -> bool:
        if not same_origin(base, url):
            return False
        path = urllib.parse.urlparse(url).path or "/"
        if path_matches_prefix_list(path, exclude_prefixes):
            return False
        return not path_blocked_by_robots(path, disallow_prefixes)

    seeds = [canonical_url(u) for u in seed_urls]
    queue: deque[str] = deque(seeds)
    enqueued: set[str] = set(seeds)
    fetched: set[str] = set()
    written_final: set[str] = set()
    written = 0
    skipped_policy = 0
    skipped_seen = 0
    skipped_duplicate_final = 0
    errors = 0
    non_html = 0

    print(f"Base: {base}", file=sys.stderr)
    print(f"Seeds: {seeds}", file=sys.stderr)
    print(f"Output: {out_root}", file=sys.stderr)
    print(f"Sleep: {args.sleep}s between requests", file=sys.stderr)
    print(f"Robots source: {robots_url}", file=sys.stderr)

    while queue:
        if args.max_pages is not None and written >= args.max_pages:
            break
        c = canonical_url(queue.popleft())
        if c in fetched:
            skipped_seen += 1
            continue
        if not allowed_by_policy(c):
            skipped_policy += 1
            continue

        try:
            fr = http_get(c, args.sleep, args.user_agent)
        except urllib.error.HTTPError as e:
            print(f"WARN: HTTP {e.code} {c}", file=sys.stderr)
            fetched.add(c)
            errors += 1
            continue
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            print(f"WARN: {c}: {e}", file=sys.stderr)
            fetched.add(c)
            errors += 1
            continue

        final = canonical_url(fr.final_url)
        fetched.add(c)
        fetched.add(final)

        path = urllib.parse.urlparse(final).path or "/"
        if path_matches_prefix_list(path, exclude_prefixes):
            skipped_policy += 1
            continue

        ctype = (fr.content_type or "").lower()
        is_html = "html" in ctype or "xml" in ctype or looks_like_html(fr.body_text)
        if not is_html:
            non_html += 1
            continue

        if final in written_final:
            skipped_duplicate_final += 1
            continue

        rel = url_to_output_relpath(final)
        page_dir = out_root / rel
        page_dir.mkdir(parents=True, exist_ok=True)

        meta: dict[str, Any] = {
            "source_url": final,
            "requested_url": c,
            "fetched_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": fr.status,
            "content_type": fr.content_type,
            "bytes": fr.raw_bytes,
            "encoding_used": fr.encoding_used,
        }
        (page_dir / "page.meta.yaml").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (page_dir / "body.html").write_text(fr.body_text, encoding="utf-8")
        written_final.add(final)
        written += 1
        print(f"Wrote [{written}] {final} -> {rel}", file=sys.stderr)

        for link in extract_links(fr.body_text, final):
            joined = urllib.parse.urljoin(final, link)
            if not same_origin(base, joined):
                continue
            cc = canonical_url(joined)
            if cc in enqueued:
                continue
            if not allowed_by_policy(cc):
                continue
            enqueued.add(cc)
            queue.append(cc)

    notes_parts = [
        "Full crawl; robots.txt Disallow prefixes enforced when readable.",
        f"path exclusions: {exclude_prefixes!r}",
    ]
    if is_donovansvgap_host(base):
        notes_parts.append("donovansvgap host: default seeds + /museum exclusion unless overridden.")

    record: dict[str, Any] = {
        "run_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": base,
        "seeds": seeds,
        "exclude_path_prefixes": exclude_prefixes,
        "pages_written": written,
        "urls_fetched_distinct": len(fetched),
        "written_final_distinct": len(written_final),
        "skipped_already_fetched": skipped_seen,
        "skipped_duplicate_final": skipped_duplicate_final,
        "skipped_policy_or_exclude": skipped_policy,
        "skipped_non_html": non_html,
        "errors": errors,
        "sleep_seconds": args.sleep,
        "user_agent": args.user_agent,
        "robots_disallow_prefixes": disallow_prefixes,
        "robots_txt_error": robots_error,
        "robots_on_error": args.robots_on_error,
        "notes": " ".join(notes_parts),
    }
    append_run_log(args.run_log.resolve(), record)

    print(
        f"Done. written={written} fetched_distinct={len(fetched)} "
        f"skipped_policy={skipped_policy} dup_final={skipped_duplicate_final} "
        f"non_html={non_html} errors={errors}",
        file=sys.stderr,
    )
    print(f"Run log: {args.run_log.resolve()}", file=sys.stderr)


if __name__ == "__main__":
    main()
