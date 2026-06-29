#!/usr/bin/env python3
"""
Wiki dense-linking helper: concept titles + concept-aliases.md → wikilink opportunities.

Passes (see Personal-wiki/AGENTS.md → Lint → Linking pass):
  1) Plain-text / word-boundary sweep for note titles and alias surfaces (longest match first).
  2) **surface** → [[target|surface]] when the whole bold span matches an alias (case-insensitive).

Skips YAML frontmatter (caller passes body only), [[wikilinks]], fenced code, inline code,
and [markdown](links).

Run from repo root:
  scripts/python/.venv/bin/python scripts/python/wiki_linking_lint.py --wiki-root Personal-wiki/wiki
  scripts/python/.venv/bin/python scripts/python/wiki_linking_lint.py --wiki-root Personal-wiki/wiki --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinkRule:
    """Single link opportunity: match surface (case-insensitive) → vault wikilink target path."""

    surface: str
    target: str  # e.g. wiki/concepts/planets-nu/Foo (Planets.nu)
    target_rel: str  # concepts/.../*.md relative to wiki root
    domain: str | None  # None = global / title-based


def parse_aliases(md_path: Path) -> list[tuple[str, str | None, str, str]]:
    """Rows: (surface_lower, domain_label_or_None, wikilink_target, target_rel)."""
    text = md_path.read_text(encoding="utf-8")
    rows: list[tuple[str, str | None, str, str]] = []
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("| Surface form"):
            in_table = True
            continue
        if not in_table or not line.strip().startswith("|"):
            continue
        if line.strip().startswith("| ---"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 3:
            continue
        surface, domain_cell, canonical = parts[0], parts[1], parts[2]
        if not surface or surface.startswith("Add rows"):
            continue
        m = re.search(r"\[\[([^\]]+)\]\]", canonical)
        if not m:
            continue
        target = m.group(1).strip()
        dom = domain_cell if domain_cell and domain_cell != "—" else None
        target_rel = wikilink_to_rel(target)
        rows.append((surface.lower(), dom, target, target_rel))
    rows.sort(key=lambda x: len(x[0]), reverse=True)
    return rows


def wikilink_to_rel(target: str) -> str:
    """wiki/concepts/foo/Bar → concepts/foo/Bar.md"""
    t = target.strip()
    if t.startswith("wiki/"):
        t = t[len("wiki/") :]
    return f"{t}.md"


def rel_to_wikilink(rel: str) -> str:
    """concepts/planets-nu/Foo.md → wiki/concepts/planets-nu/Foo"""
    p = Path(rel)
    return "wiki/" + str(p.with_suffix("")).replace("\\", "/")


def parse_frontmatter(raw: str) -> tuple[dict[str, str | list[str]], int] | None:
    if not raw.startswith("---"):
        return None
    end = raw.find("\n---", 3)
    if end == -1:
        return None
    fm = raw[3:end]
    meta: dict[str, str | list[str]] = {}
    # title
    tm = re.search(r"^title:\s*(.+)$", fm, re.M)
    if tm:
        meta["title"] = tm.group(1).strip().strip('"').strip("'")
    dm = re.search(r"^domain:\s*(.+)$", fm, re.M)
    if dm:
        meta["domain"] = dm.group(1).strip().strip('"').strip("'")
    # optional aliases: list (YAML simple)
    am = re.search(r"^aliases:\s*$", fm, re.M)
    if am:
        lines = fm[am.end() :].splitlines()
        als: list[str] = []
        for ln in lines:
            if ln.strip().startswith("- "):
                als.append(ln.strip()[2:].strip().strip('"').strip("'"))
            elif ln and not ln.startswith(" ") and not ln.startswith("\t"):
                break
        if als:
            meta["aliases"] = als
    return meta, end + 4


def load_wiki_pages(wiki_root: Path) -> list[tuple[str, dict[str, str | list[str]]]]:
    """(rel_path, meta) for markdown with YAML title."""
    out: list[tuple[str, dict[str, str | list[str]]]] = []
    for p in wiki_root.rglob("*.md"):
        if p.name in ("log.md",):
            continue
        if p.name == "README.md" and "concepts" not in str(p):
            continue
        if p.name == "concept-aliases.md" and "meta" in str(p.relative_to(wiki_root)):
            continue
        raw = p.read_text(encoding="utf-8")
        parsed = parse_frontmatter(raw)
        if not parsed or "title" not in parsed[0]:
            continue
        meta, _ = parsed
        rel = str(p.relative_to(wiki_root))
        out.append((rel, meta))
    return out


def alias_applies(domain_cell: str | None, file_domain: str | None) -> bool:
    if domain_cell is None:
        return True
    return file_domain == domain_cell


# Surfaces we never auto-link in the plain pass (registry Notes: ambiguous / high false-positive).
PLAIN_SURFACE_BLOCKLIST = frozenset({"nu"})


def build_link_rules(
    alias_rows: list[tuple[str, str | None, str, str]],
    pages: list[tuple[str, dict[str, str | list[str]]]],
) -> list[LinkRule]:
    """Merge title-based and alias-based rules; longest surface wins at match time."""
    rules: list[LinkRule] = []
    seen: set[tuple[str, str]] = set()  # (surface_lower, target)

    for rel, meta in pages:
        title = meta.get("title")
        if not isinstance(title, str):
            continue
        target = rel_to_wikilink(rel)
        key = (title.lower(), target)
        if key in seen:
            continue
        seen.add(key)
        rules.append(
            LinkRule(
                surface=title,
                target=target,
                target_rel=rel,
                domain=None,
            )
        )
        als = meta.get("aliases")
        if isinstance(als, list):
            for a in als:
                if not isinstance(a, str):
                    continue
                ak = (a.lower(), target)
                if ak in seen:
                    continue
                seen.add(ak)
                rules.append(
                    LinkRule(surface=a, target=target, target_rel=rel, domain=None)
                )

    for surf, dom, target, target_rel in alias_rows:
        key = (surf, target)
        if key in seen:
            continue
        seen.add(key)
        rules.append(LinkRule(surface=surf, target=target, target_rel=target_rel, domain=dom))

    rules.sort(key=lambda r: len(r.surface), reverse=True)
    return rules


def word_boundary_pattern(surface: str) -> re.Pattern[str]:
    """Case-insensitive match; avoid alphanumeric runs extending the span.

    Also disallow a match immediately after `-` so compounds like *non-Horwasp* do not
    partially link *Horwasp* (registry surfaces are whole tokens, not hyphen suffixes).
    """
    esc = re.escape(surface)
    return re.compile(rf"(?<![\-A-Za-z0-9]){esc}(?![A-Za-z0-9])", re.IGNORECASE)


def compute_skip_mask(body: str) -> list[bool]:
    """True = may edit; False = inside wikilink, code, or [text](url)."""
    n = len(body)
    allow = [True] * n
    i = 0

    def mark_false(a: int, b: int) -> None:
        for k in range(max(0, a), min(n, b)):
            allow[k] = False

    while i < n:
        if i + 1 < n and body[i] == "[" and body[i + 1] == "[":
            j = body.find("]]", i + 2)
            if j == -1:
                i += 1
                continue
            mark_false(i, j + 2)
            i = j + 2
            continue

        if body.startswith("```", i):
            line_end = body.find("\n", i + 3)
            if line_end == -1:
                mark_false(i, n)
                break
            end_block = body.find("```", line_end + 1)
            if end_block == -1:
                mark_false(i, n)
                break
            mark_false(i, end_block + 3)
            i = end_block + 3
            continue

        if body[i] == "`":
            if i + 1 < n and body[i + 1] == "`":
                i += 1
                continue
            j = body.find("`", i + 1)
            if j == -1:
                i += 1
                continue
            mark_false(i, j + 1)
            i = j + 1
            continue

        if body[i] == "[" and (i + 1 >= n or body[i + 1] != "["):
            m = re.match(r"\[([^\]]*)\]\(([^)]*)\)", body[i:])
            if m:
                mark_false(i, i + len(m.group(0)))
                i += len(m.group(0))
                continue

        i += 1

    return allow


def apply_plain_rules(
    body: str,
    rules: list[LinkRule],
    file_domain: str | None,
    file_rel: str,
) -> tuple[str, int]:
    """Left-to-right: earliest start, then longest span among matches at that start."""
    total = 0
    out = body

    while True:
        allow = compute_skip_mask(out)
        best: tuple[int, int, LinkRule, str] | None = None

        for rule in rules:
            if rule.domain is not None and not alias_applies(rule.domain, file_domain):
                continue
            if rule.target_rel == file_rel:
                continue
            if rule.surface.lower() in PLAIN_SURFACE_BLOCKLIST:
                continue

            pat = word_boundary_pattern(rule.surface)
            for m in pat.finditer(out):
                s, e = m.span()
                if s >= e:
                    continue
                if not all(allow[s:e]):
                    continue
                matched = m.group(0)
                cand = (s, e, rule, matched)
                if best is None:
                    best = cand
                    continue
                bs, be = best[0], best[1]
                if s < bs or (s == bs and (e - s) > (be - bs)):
                    best = cand

        if best is None:
            break

        s, e, rule, matched = best
        link = f"[[{rule.target}|{matched}]]"
        out = out[:s] + link + out[e:]
        total += 1

    return out, total


def mask_wikilinks_and_code(body: str) -> str:
    """Parallel string with \\0 inside [[...]] and fenced code (for bold pass)."""
    parts: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        if body.startswith("[[", i):
            j = body.find("]]", i)
            if j == -1:
                parts.append(body[i])
                i += 1
                continue
            parts.append("\0" * (j - i + 2))
            i = j + 2
            continue
        if body.startswith("```", i):
            j = body.find("```", i + 3)
            if j == -1:
                parts.append(body[i:])
                break
            j2 = body.find("\n", j + 3)
            if j2 == -1:
                parts.append(body[i:])
                break
            end_block = body.find("```", j2 + 1)
            if end_block == -1:
                parts.append(body[i:])
                break
            block = body[i : end_block + 3]
            parts.append("\0" * len(block))
            i = end_block + 3
            continue
        parts.append(body[i])
        i += 1
    return "".join(parts)


def apply_bold_aliases(
    body: str,
    alias_rows: list[tuple[str, str | None, str, str]],
    file_domain: str | None,
) -> tuple[str, int]:
    """**surface** → [[target|surface]] when inner matches alias (case-insensitive)."""
    masked = mask_wikilinks_and_code(body)
    out: list[str] = []
    i = 0
    n = len(body)
    count = 0
    while i < n:
        if body[i : i + 2] != "**":
            out.append(body[i])
            i += 1
            continue
        j = body.find("**", i + 2)
        if j == -1:
            out.append(body[i:])
            break
        inner = body[i + 2 : j]
        inner_lower = inner.lower().strip()
        repl: str | None = None
        for surf, dom, target, _tr in alias_rows:
            if not alias_applies(dom, file_domain):
                continue
            if inner_lower != surf:
                continue
            if "\0" in masked[i : j + 2]:
                break
            repl = f"[[{target}|{inner}]]"
            break
        if repl:
            out.append(repl)
            count += 1
            i = j + 2
        else:
            out.append(body[i : j + 2])
            i = j + 2
    return "".join(out), count


def split_frontmatter(raw: str) -> tuple[str, str] | None:
    if not raw.startswith("---"):
        return None
    end = raw.find("\n---", 3)
    if end == -1:
        return None
    return raw[: end + 4], raw[end + 4 :]


def main() -> None:
    ap = argparse.ArgumentParser(description="Wiki title/alias → wikilink lint")
    ap.add_argument("--wiki-root", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--bold-only",
        action="store_true",
        help="Only run **alias** → wikilink pass (legacy behavior subset)",
    )
    ap.add_argument(
        "--plain-only",
        action="store_true",
        help="Only run plain-text word-boundary pass",
    )
    args = ap.parse_args()
    wiki_root: Path = args.wiki_root.resolve()
    alias_path = wiki_root / "meta" / "concept-aliases.md"
    if not alias_path.is_file():
        print("No concept-aliases.md", file=sys.stderr)
        sys.exit(1)

    alias_rows = parse_aliases(alias_path)
    pages = load_wiki_pages(wiki_root)
    rules = build_link_rules(alias_rows, pages)

    do_plain = not args.bold_only
    do_bold = not args.plain_only
    if args.bold_only and args.plain_only:
        print("Cannot use both --bold-only and --plain-only", file=sys.stderr)
        sys.exit(2)

    total_plain = 0
    total_bold = 0
    touched: list[str] = []

    for rel, meta in pages:
        path = wiki_root / rel
        raw = path.read_text(encoding="utf-8")
        sp = split_frontmatter(raw)
        if not sp:
            continue
        fm, body = sp
        domain = meta.get("domain")
        file_domain = domain if isinstance(domain, str) else None

        new_body = body
        pc = 0
        bc = 0
        if do_plain:
            new_body, pc = apply_plain_rules(new_body, rules, file_domain, rel)
        if do_bold:
            new_body, bc = apply_bold_aliases(new_body, alias_rows, file_domain)

        c = pc + bc
        if c == 0:
            continue
        total_plain += pc
        total_bold += bc
        touched.append(rel)
        if args.apply:
            path.write_text(fm + new_body, encoding="utf-8")
        else:
            print(f"{rel}: would replace {pc} plain + {bc} bold (total {c})")

    print(
        f"Total: {total_plain} plain + {total_bold} bold = {total_plain + total_bold} in {len(touched)} files",
        file=sys.stderr,
    )
    if touched and not args.apply:
        for t in touched[:40]:
            print(t, file=sys.stderr)
        if len(touched) > 40:
            print(f"... and {len(touched) - 40} more", file=sys.stderr)


if __name__ == "__main__":
    main()
