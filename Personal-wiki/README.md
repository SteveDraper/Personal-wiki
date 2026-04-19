# Personal wiki (Obsidian vault)

This folder is an **Obsidian vault** for the **LLM Wiki** pattern: structured Markdown maintained by an assistant, built from **immutable** sources under **`raw/`**.

## Policy

- **`AGENTS.md`** (this folder) — Full rules: page conventions, style, operations, session behavior.
- **`raw/`** — Your sources. Assistants **read** for ingest; they **do not** change files here unless you instruct them to.
- **`wiki/`** — Assistant-owned **knowledge pages** plus **`index.md`**, **`log.md`**, and **`meta/`** (e.g. vault-canonical **`concept-aliases.md`** per **`AGENTS.md`**).

## Wiki articles vs `index` / `log`

**Knowledge pages** (under `wiki/concepts/`, `wiki/projects/`, `wiki/people/`, etc.) must use:

- **YAML frontmatter** with `title`, `type`, `sources`, `related`, `created`, `last-updated` (`type` ∈ concept, entity, source-summary, comparison, project, person).
- **`## Sources`** in the body, kept in sync with frontmatter `sources`.
- **Wikilinks** `[[...]]`, **atomic** scope (one main idea per page), consistent **headings** (`##` / `###`, no skipped levels).
- **Style:** clear prose, bullets where helpful; **attribute** claims; **surface contradictions** between sources.

**`wiki/index.md`** and **`wiki/log.md`** are **exempt** from the full article frontmatter set (they are catalog and log, not knowledge atoms).

Subfolders under `raw/`, `wiki/`, `journal/`, and `content/` each have a **`README.md`** describing how that path fits the above.

Open this directory as a vault in Obsidian (links, graph, plugins).
