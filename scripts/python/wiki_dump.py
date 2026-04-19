"""
Export all main-namespace pages from a MediaWiki site as wikitext files under a vault raw/ subpath.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

USER_AGENT = "mediawiki-raw-import/0.1 (MediaWiki export script; no public homepage)"


def normalize_wiki_root(url: str) -> str:
    s = url.strip()
    if not s:
        raise ValueError("wiki root URL is empty")
    if not urllib.parse.urlparse(s).scheme:
        s = "https://" + s
    p = urllib.parse.urlparse(s)
    if not p.scheme or not p.netloc:
        raise ValueError(f"could not parse wiki root URL: {url!r}")
    return f"{p.scheme}://{p.netloc}".rstrip("/")


def discover_api_endpoint(wiki_root: str) -> str:
    """Return full URL to api.php for this site."""
    candidates = (
        f"{wiki_root}/api.php",
        f"{wiki_root}/w/api.php",
    )
    for endpoint in candidates:
        q = urllib.parse.urlencode(
            {"action": "query", "meta": "siteinfo", "format": "json"}
        )
        url = f"{endpoint}?{q}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status != 200:
                    continue
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            continue
        if data.get("error"):
            continue
        if "query" in data:
            return endpoint
    raise RuntimeError(
        f"could not find MediaWiki api.php at {wiki_root} (tried /api.php and /w/api.php)"
    )


def url_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def fetch_json(params: dict[str, str]) -> dict:
    """POST application/x-www-form-urlencoded (reliable for long continuation tokens)."""
    api_url = params.get("_endpoint")
    if not api_url:
        raise ValueError("internal: missing _endpoint")
    post_body = {k: v for k, v in params.items() if k != "_endpoint"}
    data = urllib.parse.urlencode(post_body).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


PAGEIDS_PER_REQUEST = 50
"""MediaWiki commonly allows ~50 titles/pageids per `action=query`."""


def list_allpages(
    api_endpoint: str, namespace: int, sleep: float
) -> list[dict[str, object]]:
    """Return [{'pageid': int, 'title': str}, ...] for all pages in the namespace."""
    base: dict[str, str] = {
        "_endpoint": api_endpoint,
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "list": "allpages",
        "apnamespace": str(namespace),
        "aplimit": "max",
    }
    continue_params: dict[str, str] | None = None
    rows: list[dict[str, object]] = []
    while True:
        payload = dict(base)
        if continue_params:
            payload.update(continue_params)
        if sleep > 0 and continue_params:
            time.sleep(sleep)
        data = fetch_json(payload)
        if data.get("error"):
            raise SystemExit(f"MediaWiki API error (list=allpages): {data['error']}")
        for p in (data.get("query") or {}).get("allpages") or []:
            rows.append({"pageid": p["pageid"], "title": p["title"]})
        if "continue" not in data:
            break
        continue_params = {k: str(v) for k, v in data["continue"].items()}
    return rows


def revision_wikitext(rev: dict) -> str | None:
    slots = rev.get("slots") or {}
    main = slots.get("main") or {}
    txt = main.get("content")
    if txt is None:
        txt = main.get("*")
    if txt is not None:
        return txt
    if "*" in rev:
        return rev["*"]
    return None


_ILLEGAL_FS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def report_page_progress(count: int) -> None:
    """Print a single updating line to stderr with the number of pages handled so far."""
    print(f"\rProgress: {count} page(s) so far", end="", file=sys.stderr, flush=True)


def safe_filename(title: str) -> str:
    t = title.replace("/", "__")
    t = _ILLEGAL_FS.sub("_", t)
    t = t.strip(" .")
    if not t:
        t = "untitled"
    return t[:200]


def output_filename(title: str, pageid: int) -> str:
    """Stable unique on-disk name (avoids collisions between distinct titles)."""
    return f"{safe_filename(title)}__{pageid}.mediawiki"


def default_vault_path() -> Path:
    # scripts/python/wiki_dump.py -> repo root -> Personal-wiki vault
    return Path(__file__).resolve().parent.parent.parent / "Personal-wiki"


def main() -> None:
    p = argparse.ArgumentParser(
        description="Export MediaWiki main-space wikitext into vault raw/ subfolder."
    )
    p.add_argument(
        "--wiki-root",
        required=True,
        help="Wiki base URL (e.g. https://vgaplanets.org). Path/query are ignored for discovery.",
    )
    p.add_argument(
        "--raw-subpath",
        required=True,
        help='Subdirectory under the vault\'s raw/ folder (e.g. planets/wiki). Use "/" only as separators.',
    )
    p.add_argument(
        "--vault",
        type=Path,
        default=None,
        help=f"Path to Obsidian vault root (folder containing raw/). Default: {default_vault_path()}",
    )
    p.add_argument(
        "--namespace",
        type=int,
        default=0,
        help="MediaWiki namespace id (0 = main articles).",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.05,
        help="Seconds to sleep between API pagination requests (politeness).",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Stop after writing this many pages (for testing).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="List page titles only; do not write files.",
    )
    args = p.parse_args()

    wiki_root = normalize_wiki_root(args.wiki_root)
    api_endpoint = discover_api_endpoint(wiki_root)

    raw_parts = [part for part in args.raw_subpath.replace("\\", "/").split("/") if part]
    raw_sub = Path(*raw_parts) if raw_parts else Path()
    vault = (args.vault or default_vault_path()).resolve()
    out_dir = vault / "raw" / raw_sub

    pages_written = 0
    manifest_pages: list[dict[str, object]] = []

    print(f"API: {api_endpoint}", file=sys.stderr)
    print(f"Output: {out_dir}", file=sys.stderr)

    site_name = ""
    try:
        si = url_json(
            f"{api_endpoint}?{urllib.parse.urlencode({'action': 'query', 'meta': 'siteinfo', 'format': 'json', 'formatversion': '2'})}"
        )
        site_name = (si.get("query", {}) or {}).get("general", {}).get("sitename", "") or ""
    except OSError:
        pass

    print("Listing all page titles (namespace)...", file=sys.stderr)
    all_rows = list_allpages(api_endpoint, args.namespace, args.sleep)
    if args.max_pages is not None:
        all_rows = all_rows[: args.max_pages]
    print(f"Found {len(all_rows)} page(s) to export.", file=sys.stderr)

    if args.dry_run:
        for row in all_rows:
            print(row["title"])
        pages_written = len(all_rows)
        report_page_progress(pages_written)
        print(file=sys.stderr)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        for start in range(0, len(all_rows), PAGEIDS_PER_REQUEST):
            batch = all_rows[start : start + PAGEIDS_PER_REQUEST]
            if args.sleep > 0 and start > 0:
                time.sleep(args.sleep)
            ids = "|".join(str(int(row["pageid"])) for row in batch)
            payload: dict[str, str] = {
                "_endpoint": api_endpoint,
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "pageids": ids,
                "prop": "revisions",
                "rvprop": "content|timestamp",
                "rvslots": "main",
            }
            data = fetch_json(payload)
            if data.get("error"):
                raise SystemExit(f"MediaWiki API error: {data['error']}")
            pages = (data.get("query") or {}).get("pages") or []
            for pg in pages:
                if pg.get("missing"):
                    continue
                title = pg.get("title") or ""
                pageid = int(pg.get("pageid", 0))
                revs = pg.get("revisions") or []
                rev = revs[0] if revs else {}
                wikitext = revision_wikitext(rev)
                if wikitext is None:
                    wikitext = ""
                ts = rev.get("timestamp") or ""
                fn = output_filename(title, pageid)
                rel = str(raw_sub / fn).replace("\\", "/") if raw_sub.parts else fn

                manifest_pages.append(
                    {
                        "title": title,
                        "pageid": pageid,
                        "file": rel,
                        "bytes": len(wikitext.encode("utf-8")),
                    }
                )

                out_path = out_dir / fn
                front = (
                    "---\n"
                    f'title: {json.dumps(title)}\n'
                    f"source_wiki: {json.dumps(wiki_root + '/index.php?title=' + urllib.parse.quote(title.replace(' ', '_')))}\n"
                    f'mw_page_id: {pageid}\n'
                    f'export_api: {json.dumps(api_endpoint)}\n'
                    f"revision_timestamp: {json.dumps(ts)}\n"
                    f"exported_at: {json.dumps(datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'))}\n"
                    "---\n\n"
                )
                out_path.write_text(front + wikitext, encoding="utf-8")

                pages_written += 1
                report_page_progress(pages_written)

    if pages_written:
        print(file=sys.stderr)

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "wiki_root": wiki_root,
            "api_endpoint": api_endpoint,
            "sitename": site_name,
            "namespace": args.namespace,
            "exported_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page_count": len(manifest_pages),
            "pages": manifest_pages,
        }
        (out_dir / "_export_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    print(
        f"Done. {'Would write' if args.dry_run else 'Wrote'} {pages_written} page(s).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
