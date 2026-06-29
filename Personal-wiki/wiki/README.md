# wiki

**Assistant-maintained knowledge**—synthesis, entity pages, comparisons, and cross-links. You read; assistants write and update.

## What belongs here

| Path | Role |
|------|------|
| **`index.md`** | Master catalog of wiki pages. **Exempt** from full article frontmatter (see `AGENTS.md`). |
| **`log.md`** | Append-only activity log. **Exempt** from full article frontmatter. |
| **`meta/`** | Registries: **`concept-aliases.md`** (aliases), **`domain-registry.md`** (domains / slugs / hubs), **`corpus-layout-flarum-jsonapi-export.md`** (Flarum exporter under **`raw/*.flarum/`**), **`corpus-layout-donovansvgap-static-export.md`** (Donovan static mirror under **`raw/donovansvgap/`**—see **`AGENTS.md`**). |
| **`concepts/`** | Domain-scoped notes under **`concepts/<slug>/`**, cross-domain hubs under **`concepts/_shared/`** (see **`AGENTS.md`** → Domains). |
| **`projects/`** | **`type: project`** pages. |
| **`people/`** | **`type: person`** dossiers. |

## Article conventions (all knowledge pages)

Per **`AGENTS.md`**:

- **Frontmatter:** `title`, `type`, `domain` (required under `concepts/<slug>/`, omitted under `concepts/_shared/`), `sources`, `related`, `created`, `last-updated`.
- **Body:** **`## Sources`** listing vault-relative `raw/` paths, with notes per file; must match frontmatter `sources`. Optional **`### Provenance and resolution`** under Sources for how conflicts were resolved; keep **`## Summary`** as plain corrected fact (see **`AGENTS.md`**).
- **Links & structure:** wikilinks `[[...]]` (prefer **dense** cross-links for references to other topics; do not use bold only as a stand-in for links—see **`AGENTS.md`**), one main **idea per page** where practical, **headings** without skipped levels.
- **Style:** concise prose and bullets; **attribute** every factual claim; **call out contradictions** between sources.

There is **no** requirement for one wiki page per raw file; many sources may support one page.

**Folder READMEs:** **`concepts/README.md`** — layout and **Multi-link topics** (generic pattern for hub checklists that span several pages). Optional **`concepts/<slug>/README.md`** — per-domain notes (e.g. **`planets-nu/README.md`**) listing which hub pages in that corpus use the pattern. **`projects/`** and **`people/`** READMEs describe typical `type` values and usage.
