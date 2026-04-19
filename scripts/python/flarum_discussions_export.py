"""
Export public Flarum discussions via JSON:API into a folder hierarchy suitable for vault raw/ ingest.

Layout::

    <output-dir>/
      <SectionTagName>/          # most specific tag on the thread (deepest in tag tree; tie-break by name)
        <id>-<discussion-slug>/
          discussion.meta.yaml   # thread-level metadata
          posts/
            post-0001-<postId>.md

Each run appends one JSON object (JSON Lines) to the run log, for use as a coarse cursor::

    {"run_utc": "...", "base_url": "...", "since": "..."|null,
     "last_content_instant": "..."|null, "discussions_processed": n,
     "discussions_written": n, "posts_written": n}

For incremental passes, pass ``--since`` equal to ``last_content_instant`` from the previous
line (inclusive filter: posts whose ``createdAt`` or ``editedAt`` is >= since). Re-exporting
overwrites the same paths, so overlap is safe.
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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

USER_AGENT = "flarum-discussions-export/0.1 (+personal wiki raw ingest; JSON:API)"

_ILLEGAL_FS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


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


def safe_segment(name: str, max_len: int = 120) -> str:
    t = name.replace("/", "__").strip()
    t = _ILLEGAL_FS.sub("_", t)
    t = t.strip(" .")
    if not t:
        t = "unnamed"
    return t[:max_len]


def parse_instant(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    s = value.strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        # Date only: treat as start of that day UTC
        return datetime.fromisoformat(s + "T00:00:00+00:00").astimezone(UTC)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def http_json(url: str, sleep: float) -> dict[str, Any]:
    if sleep > 0:
        time.sleep(sleep)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def index_by_type_id(included: list[dict[str, Any]] | None) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for item in included or []:
        t = item.get("type")
        i = item.get("id")
        if t and i is not None:
            out[(str(t), str(i))] = item
    return out


def walk_tag_depth(tag_id: str, tags: dict[str, TagMeta]) -> int:
    depth = 0
    seen: set[str] = set()
    cur = tag_id
    while cur and cur not in seen:
        seen.add(cur)
        meta = tags.get(cur)
        if not meta or not meta.parent_id:
            break
        depth += 1
        cur = meta.parent_id
    return depth


@dataclass(frozen=True)
class TagMeta:
    name: str
    slug: str
    parent_id: str | None


def load_tags(base: str, sleep: float) -> dict[str, TagMeta]:
    data = http_json(f"{base}/api/tags", sleep)
    tags: dict[str, TagMeta] = {}
    for item in data.get("data") or []:
        tid = str(item.get("id", ""))
        if not tid:
            continue
        attrs = item.get("attributes") or {}
        parent = (item.get("relationships") or {}).get("parent") or {}
        pdata = parent.get("data")
        parent_id = str(pdata["id"]) if pdata and pdata.get("id") is not None else None
        tags[tid] = TagMeta(
            name=str(attrs.get("name") or tid),
            slug=str(attrs.get("slug") or tid),
            parent_id=parent_id,
        )
    return tags


def pick_section_name(tag_ids: list[str], tags: dict[str, TagMeta]) -> str:
    if not tag_ids:
        return "_uncategorized"
    best: tuple[int, str, str] | None = None
    for tid in tag_ids:
        meta = tags.get(tid)
        name = meta.name if meta else tid
        d = walk_tag_depth(tid, tags)
        key = (-d, name.lower(), name)
        if best is None or key < best:
            best = key
    assert best is not None
    return best[2]


def iter_discussion_summaries(base: str, sleep: float) -> Iterable[dict[str, Any]]:
    url: str | None = f"{base}/api/discussions?page%5Blimit%5D=50&include=tags"
    while url:
        data = http_json(url, sleep)
        for item in data.get("data") or []:
            yield item
        next_url = (data.get("links") or {}).get("next")
        url = str(next_url) if next_url else None


def discussion_tag_ids(disc: dict[str, Any]) -> list[str]:
    rel = (disc.get("relationships") or {}).get("tags") or {}
    out: list[str] = []
    for ref in (rel.get("data") or []):
        if ref.get("type") == "tags" and ref.get("id") is not None:
            out.append(str(ref["id"]))
    return out


def post_content_instant(attrs: dict[str, Any]) -> datetime:
    created = parse_instant(attrs.get("createdAt"))
    if created is None:
        return datetime.min.replace(tzinfo=UTC)
    edited = parse_instant(attrs.get("editedAt"))
    if edited is None:
        return created
    return max(created, edited)


def post_matches_since(attrs: dict[str, Any], since: datetime | None) -> bool:
    if since is None:
        return True
    created = parse_instant(attrs.get("createdAt"))
    edited = parse_instant(attrs.get("editedAt"))
    if created and created >= since:
        return True
    if edited and edited >= since:
        return True
    return False


def fetch_discussion_document(base: str, disc_id: str, sleep: float) -> dict[str, Any]:
    q = urllib.parse.urlencode({"include": "posts,user,tags"})
    return http_json(f"{base}/api/discussions/{disc_id}?{q}", sleep)


def yaml_quote(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render_post_markdown(
    post: dict[str, Any],
    users: dict[tuple[str, str], dict[str, Any]],
) -> str:
    pid = str(post.get("id", ""))
    attrs = post.get("attributes") or {}
    rel_user = ((post.get("relationships") or {}).get("user") or {}).get("data")
    username = ""
    if rel_user and rel_user.get("id") is not None:
        u = users.get(("users", str(rel_user["id"])))
        if u:
            username = str((u.get("attributes") or {}).get("displayName") or "") or str(
                (u.get("attributes") or {}).get("username") or ""
            )

    content_type = str(attrs.get("contentType") or "")
    lines = [
        "---",
        f"flarum_post_id: {pid}",
        f"post_number: {attrs.get('number')}",
        f"content_type: {yaml_quote(content_type)}",
        f"author_display: {yaml_quote(username)}",
        f"created_at: {yaml_quote(str(attrs.get('createdAt') or ''))}",
        f"edited_at: {yaml_quote(str(attrs.get('editedAt') or ''))}",
        "---",
        "",
    ]

    if content_type == "comment":
        html_body = attrs.get("contentHtml") or ""
        lines.append(html_body)
        lines.append("")
    else:
        lines.append("```json")
        lines.append(json.dumps(attrs.get("content"), ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def write_discussion(
    *,
    base: str,
    out_root: Path,
    tags: dict[str, TagMeta],
    doc: dict[str, Any],
    since: datetime | None,
) -> tuple[int, datetime | None]:
    """Return (posts_written, max_content_instant for this discussion's written posts)."""
    disc = doc.get("data") or {}
    if disc.get("type") != "discussions":
        return 0, None

    disc_id = str(disc.get("id", ""))
    attrs = disc.get("attributes") or {}
    slug = str(attrs.get("slug") or disc_id)
    title = str(attrs.get("title") or slug)

    included = index_by_type_id(doc.get("included"))

    tag_ids: list[str] = []
    trel = (disc.get("relationships") or {}).get("tags") or {}
    for ref in (trel.get("data") or []):
        if ref.get("type") == "tags" and ref.get("id") is not None:
            tag_ids.append(str(ref["id"]))
    section = pick_section_name(tag_ids, tags)

    posts_rel = (disc.get("relationships") or {}).get("posts") or {}
    post_refs = posts_rel.get("data") or []

    posts: list[dict[str, Any]] = []
    for ref in post_refs:
        if ref.get("type") != "posts" or ref.get("id") is None:
            continue
        p = included.get(("posts", str(ref["id"])))
        if p:
            posts.append(p)

    posts.sort(key=lambda p: int((p.get("attributes") or {}).get("number") or 0))

    if since is not None:
        any_match = any(
            post_matches_since(p.get("attributes") or {}, since) for p in posts
        )
        if not any_match:
            return 0, None

    # Flarum slugs are already unique (typically ``{id}-{title}``); avoid ``38-38-...`` duplication.
    disc_dir = out_root / safe_segment(section) / safe_segment(slug, max_len=180)
    posts_dir = disc_dir / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "flarum_discussion_id": disc_id,
        "title": title,
        "slug": slug,
        "api_url": f"{base}/api/discussions/{disc_id}",
        "web_url": f"{base}/d/{slug}",
        "section_tag": section,
        "tag_ids": tag_ids,
        "created_at": attrs.get("createdAt"),
        "last_posted_at": attrs.get("lastPostedAt"),
        "comment_count": attrs.get("commentCount"),
        "attributes": {
            k: attrs.get(k)
            for k in (
                "isSticky",
                "isLocked",
                "participantCount",
                "lastPostNumber",
            )
            if k in attrs
        },
    }
    (disc_dir / "discussion.meta.yaml").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    max_inst: datetime | None = None
    n_written = 0
    for p in posts:
        pattrs = p.get("attributes") or {}
        num = int(pattrs.get("number") or 0)
        pid = str(p.get("id", ""))
        body = render_post_markdown(p, included)
        fn = f"post-{num:04d}-{pid}.md"
        (posts_dir / fn).write_text(body, encoding="utf-8")
        n_written += 1
        inst = post_content_instant(pattrs)
        max_inst = inst if max_inst is None else max(max_inst, inst)

    return n_written, max_inst


def append_run_log(
    path: Path,
    record: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Export Flarum discussions (JSON:API) into section/discussion/posts tree."
    )
    ap.add_argument(
        "--base-url",
        required=True,
        help="Forum root URL (e.g. https://planets.flarum.cloud).",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write (section / discussion / posts).",
    )
    ap.add_argument(
        "--run-log",
        type=Path,
        required=True,
        help="Append one JSON Lines record per run (cursor + stats).",
    )
    ap.add_argument(
        "--since",
        default=None,
        help="ISO date or datetime (UTC if no offset). Include posts with createdAt/editedAt >= this instant. Omit for full export.",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="Seconds to sleep between HTTP calls (default: 0.15).",
    )
    ap.add_argument(
        "--max-discussions",
        type=int,
        default=None,
        help="Stop after this many discussions (testing).",
    )
    args = ap.parse_args()

    base = normalize_base_url(args.base_url)
    since = parse_instant(args.since) if args.since else None
    out_root: Path = args.output_dir.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"Base: {base}", file=sys.stderr)
    print(f"Output: {out_root}", file=sys.stderr)
    print(f"Since: {since.isoformat() if since else 'all time'}", file=sys.stderr)

    tags = load_tags(base, 0.0)
    print(f"Loaded {len(tags)} tag(s).", file=sys.stderr)

    total_posts = 0
    discussions_written = 0
    global_max: datetime | None = None
    n_processed = 0

    for summary in iter_discussion_summaries(base, args.sleep):
        if args.max_discussions is not None and n_processed >= args.max_discussions:
            break
        n_processed += 1
        disc_id = str(summary.get("id", ""))
        if not disc_id:
            continue
        try:
            doc = fetch_discussion_document(base, disc_id, args.sleep)
        except urllib.error.HTTPError as e:
            print(f"WARN: discussion {disc_id}: HTTP {e.code}", file=sys.stderr)
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"WARN: discussion {disc_id}: {e}", file=sys.stderr)
            continue

        n_posts, disc_max = write_discussion(
            base=base, out_root=out_root, tags=tags, doc=doc, since=since
        )
        if n_posts > 0:
            discussions_written += 1
            total_posts += n_posts
            if disc_max is not None:
                global_max = disc_max if global_max is None else max(global_max, disc_max)
            title = (doc.get("data") or {}).get("attributes", {}).get("title", disc_id)
            print(f"Wrote {n_posts} post(s): {title!r}", file=sys.stderr)

    record = {
        "run_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": base,
        "since": since.isoformat() if since else None,
        "last_content_instant": global_max.isoformat() if global_max else None,
        "discussions_processed": n_processed,
        "discussions_written": discussions_written,
        "posts_written": total_posts,
    }
    append_run_log(args.run_log.resolve(), record)

    print(
        f"Done. discussions_processed={n_processed} written={discussions_written} "
        f"posts={total_posts} last_content_instant={record['last_content_instant']}",
        file=sys.stderr,
    )
    print(f"Run log: {args.run_log.resolve()}", file=sys.stderr)


if __name__ == "__main__":
    main()
