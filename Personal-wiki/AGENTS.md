# Personal wiki — agent instructions

In what follows the agent always has the role of the assistant, not the user.

This vault follows the [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern: a **compounding wiki** of interlinked Markdown maintained by the assistant, built from **immutable** sources you add under `raw/`.

## Layers


| Layer                  | Path                   | Who edits                                                                                                                          |
| ---------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Sources**            | `raw/`                 | **User only.** The assistant (agent) reads these files; it does not modify, move, or delete them unless you explicitly ask.        |
| **Wiki**               | `wiki/`                | **The assistant** creates and updates pages: concepts, projects, people, syntheses, cross-links. User reads; the assistant writes. |
| **Journal / pipeline** | `journal/`, `content/` | Reserved for Part 2 workflows; follow the same “Sources” citation rules when those notes feed the wiki.                            |


## Directory layout (vault root)

- `raw/` — Curated source documents (including `raw/Clippings/` for web clips, bulk exports, etc.). Immutable from the assistant’s perspective.
- `raw/Authoritative/` — **User-authored** corrections and disambiguations (short Markdown). Canonical place to state **vault-adopted** rules when `raw/` evidence conflicts or is vague; cite these files in `wiki/` like any other `raw/` path. See **Source errors vs authoritative vault truth** below.
- `wiki/` — Assistant-maintained knowledge.
  - `wiki/index.md` — Catalog of wiki pages (links, one-line summaries, optional metadata).
  - `wiki/log.md` — Append-only activity log (ingests, notable queries, lint passes).
  - `wiki/meta/` — **Assistant-maintained** registries and tooling notes. **`wiki/meta/concept-aliases.md`** is **vault-canonical**: the **alias registry** (prose surface forms → concept wikilinks); see **Concept aliases and normalization**. **`wiki/meta/domain-registry.md`** lists **domains** (canonical labels, slugs, hub paths); see **Domains and concept layout**. Other files here (e.g. `source-quality.md`) are optional unless the vault adopts them. This folder is **not** a layer of full wiki articles—no required YAML article frontmatter unless a specific file defines its own shape.
  - `wiki/concepts/` — Topic pages. **Domain-scoped** concepts live under **`wiki/concepts/<slug>/`** (see below). **Cross-domain / general** concepts live under **`wiki/concepts/_shared/`** (no `domain:` in frontmatter). **`wiki/projects/`**, **`wiki/people/`** — as needed.
- `journal/`, `content/` — Placeholders for later use.

## Domains and concept layout

Concept pages are **scoped by domain** so the same English **stem** (e.g. “Planet”) can exist in different corpora without merging incompatible meanings.

- **Canonical domain label** — A stable string (e.g. `Planets.nu`) used in YAML **`domain:`** and in **titles** as **`Concept (Domain)`**. If unclear at ingest time, **ask the user**.
- **Slug** — A single filesystem directory name under `wiki/concepts/<slug>/`: **lowercase**, ASCII **letters, digits, hyphens** only. Normalize from the label (e.g. `Planets.nu` → `planets-nu`). **`domain:`** stores the **canonical label**, not the slug.
- **Hub page** — **Required** for each domain. Path: **`wiki/concepts/<slug>/<Canonical Domain Label>.md`** (filename equals the canonical label + `.md` when valid on the host OS; if a character is invalid in filenames, use the same safe encoding you use for other notes—e.g. NFC Unicode, or replace only the minimal problematic characters—**and** record the exact path in **`wiki/meta/domain-registry.md`**).
- **Titles (redundant disambiguation)** — Domain-scoped concept notes use **`Concept (Domain)`** as **`title:`** and filename **even though** the slug folder already identifies the domain (option **B**: redundancy for grep, exports, and Obsidian search).
- **Concept stem (disambiguation trigger)** — The **stem** used to detect collisions across corpora is: **Obsidian note name without `.md`**, after removing a trailing **` (Domain)`** suffix, yielding **`Concept`**. If two corpora would use the same stem in the same vault, **disambiguate** with distinct domains and titles; if domain is unclear on a file, **ask the user** at ingest or lint.
- **General / shared concepts** — When the same underlying idea legitimately spans domains, add **`wiki/concepts/_shared/<Title>.md`** summarizing the commonality and linking to each **`Concept (Domain)`** variant. **Omit `domain:`** on these pages (see **`wiki/concepts/_shared/README.md`**). **Merging two meanings into one page is not allowed**; prefer a shared hub plus domain pages.
- **Cross-links** — A **narrower** domain-specific page **must** link to a **more general** shared (or broader) page when one exists. **Sibling** domain variants **need not** link to each other unless a real relationship exists.
- **`raw/Authoritative/`** — Reserve for **factual** corrections and source conflict resolution, **not** for choosing a game vs science domain (that belongs in wiki structure and **`domain-registry.md`**).

## Page conventions

These rules apply to **every wiki article** under `wiki/concepts/`, `wiki/projects/`, `wiki/people/`, and any other assistant-maintained page in `wiki/` **except** `wiki/index.md` and `wiki/log.md` (those two may use minimal or no frontmatter). **Concept pages under `wiki/concepts/_shared/`** use the same article rules **except** they **omit** **`domain:`** (see **Domains and concept layout**).

### YAML frontmatter (required)

Each page must begin with YAML frontmatter including these keys (**`domain:`** is required for domain-scoped concepts under `wiki/concepts/<slug>/`, omitted under `wiki/concepts/_shared/`):


| Field          | Description                                                                                                                                                                                                                                                                                                                                                 |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`        | Display title (can match the note title; use quotes if special characters). Domain-scoped concepts use **`Concept (Domain)`**.                                                                                                                                                                                                                                                                                              |
| `type`         | One of: `concept`, `entity`, `source-summary`, `comparison`, `project`, `person`. Use `**person`** for individuals, `**entity**` for organizations, products, places, or other non-person subjects when a dedicated page fits better under concepts or people than a generic note. Align folder with intent when possible (e.g. `person` → `wiki/people/`). |
| `domain`       | **Required** for notes under **`wiki/concepts/<slug>/`** (must equal the **canonical domain label** for that slug in **`wiki/meta/domain-registry.md`**). **Omit** for **`wiki/concepts/_shared/`**. Optional elsewhere (`projects/`, `people/`).                                                                                                                                                                            |
| `sources`      | List of **vault-relative** paths to files in `raw/` that substantiate the page (YAML list). Keep this list in sync with the `**## Sources`** body section below (same paths). Use `[]` if none yet.                                                                                                                                                         |
| `related`      | List of wikilinks to other wiki pages (strings such as `"[[Other Page]]"`). Use `[]` if none.                                                                                                                                                                                                                                                               |
| `created`      | ISO date `YYYY-MM-DD` when the page was first created.                                                                                                                                                                                                                                                                                                      |
| `last-updated` | ISO date `YYYY-MM-DD` of the latest substantive edit.                                                                                                                                                                                                                                                                                                       |

**Example:**

```yaml
---
title: "Acme Corp"
type: entity
sources:
  - raw/Clippings/acme-announcement.md
  - raw/reports/industry-overview-2025.md
related:
  - "[[Jane Doe]]"
  - "[[Widget market]]"
created: 2026-04-18
last-updated: 2026-04-18
---
```

### Links, atomicity, headings

- Use **Obsidian wikilinks** `[[like this]]` (and `#`/`^` anchors when helpful) to connect pages.
- Prefer **one main idea per page** (atomic notes). If a page grows unwieldy, split into linked pages and update `related` and `wiki/index.md`.
- Use a **consistent heading shape**: optional short introduction in normal text, then `##` for major sections and `###` for subsections; do not skip levels (e.g. do not jump from `##` to `####` without a `###`).

### Dense wikilinking (preferred)

- **Strive for dense linkage** where it stays readable: when prose refers to another vault topic (concept, entity, project, person) that **exists** or clearly **should** exist as its own page, use a **wikilink** `[[Page title]]` (or `[[Page title|display text]]` when the sentence needs different wording)—including early in a section when it helps navigation and backlinks.
- **Anti-pattern:** Using **bold**, *italic*, or other emphasis **primarily** to mark “this is another named concept” instead of linking. That hides relationships from the graph and backlink pane; readers cannot jump. Reserve emphasis for real typographic stress, short definitions, or genuinely exceptional labels—not as a substitute for `[[…]]`.
- **Anti-pattern (compound):** Putting **several** named topics inside **one** emphasis span—whether a **comma/slash list** (`**engines, beams, tubes**`), a **short inline roll** of domain parts, or a **sentence fragment** that bundles multiple things you would otherwise give their own links. That reads like a “tag cloud” in bold: it still fails navigation, and **exact-title linters miss it** because the span does not equal any single note title. **Prefer** separate `[[wiki/concepts/Canonical Title|surface form]]` links (or plain text plus links), not one bold wrapper around an inventory.
- **On any substantive edit:** Prefer replacing concept-shaped emphasis with wikilinks when a target page exists; add reciprocal links or `related` entries where discovery would improve. Pipe-links are fine when the vault title differs from in-prose phrasing.

### Concept aliases and normalization (lint / ingest)

Canonical link targets are **`wiki/concepts/<slug>/<Title>.md`** with frontmatter **`title:`** matching the filename stem. Domain-scoped titles use **`Concept (Domain)`**; the **hub** for a domain is **`wiki/concepts/<slug>/<Canonical Domain Label>.md`** (see **Domains and concept layout**). Prose will not always match that string exactly.

- **Normalization (when matching mentions to pages):** Apply sensible **case-folding** (Engine vs engine). Treat **plural or shortened surface forms** as candidates for a vault topic (e.g. “engines” → [[wiki/concepts/planets-nu/Engines (Planets.nu)]], “beams” → [[wiki/concepts/planets-nu/Beam weapons (Planets.nu)|beams]]) when context supports it—see the **alias registry** below; **do not** guess novel mappings when domain judgment matters (**When to stop and ask the user**).
- **Vault decision — canonical alias registry:** This vault **does not** use **`wiki/index.md`** or extra catalog columns for synonyms. The **only** canonical place for cross-cutting aliases (short forms, plurals, alternate casing, common export wording) is **`wiki/meta/concept-aliases.md`**, maintained by assistants during **ingest** and **lint**. Format: a **table** with columns **Surface form** → optional **Domain** (canonical label) → **Canonical page** → **Notes**. If **Domain** is **empty**, the alias applies **globally**. If **Domain** is set, the alias applies **only** when processing a file whose YAML **`domain:`** matches that label. **Precedence:** for a given surface form, if both a domain-specific and a global row exist, **use the domain-specific target** when the file’s `domain:` matches; otherwise use the global row. **`index.md`** stays the human-readable “what pages exist” list; **`concept-aliases.md`** is the “what strings in prose should resolve to which page” list.
- **Alternatives (use sparingly):** Optional **`aliases:`** in YAML frontmatter on a single concept page is allowed for **rare, note-local** strings only. Cross-cutting forms (e.g. “beams” → Beam weapons) **belong in `concept-aliases.md`**, not duplicated across frontmatter. **Do not** add standing alias columns to **`index.md`**.
- **Lint heuristic — unlinked mention pass:** Build a candidate set from (1) all concept **`title:`** values (or stems under `wiki/concepts/**`), plus (2) every **surface form** in **`wiki/meta/concept-aliases.md`** that applies to the **current file’s** `domain:` (per rules above). Scan wiki Markdown for occurrences that are **not** already part of a wikilink (skip text inside `[[…]]` when implementing). **Extend `concept-aliases.md`** when you repeatedly resolve the same non-title string to a hub page. **Flag** ambiguous hits for review; use **word-boundary** (or whole-token) matching to limit false positives; when still **ambiguous**, use **`wiki/log.md`** or **ask the user** rather than auto-linking the wrong hub.

### Latent concepts (missing hub pages)

- **Definition:** A **latent concept** is a substantive idea (mechanic, component class, faction, rule, entity, etc.) that appears **more than once** across `wiki/` or new `raw/` material—sometimes as bold or plain phrasing, sometimes under different wording—but **does not** yet have a suitable first-class page, or readers would benefit from a single hub that other pages link to.
- **Evaluation (not automatic creation):** During **ingest** and **lint**, notice these echoes. Decide whether to (1) **add** a new concept/entity page and link mentions to it, (2) **link** to an existing page under a different name (aliases in prose, fix titles only with user alignment), or (3) **leave** inline-only when the mention is a one-off or scope is too thin. **Do not invent** a large taxonomy by guesswork—use **When to stop and ask the user** when domain judgment materially affects structure.

## Wiki page structure: **Sources** (body section, required)

Every wiki page that reflects information drawn from `raw/` must also include a `**## Sources`** section near the end (before tags or unrelated appendices, if any), with content that matches the spirit of the frontmatter `sources` list.

**Purpose:** Trace claims back to files under `raw/` without requiring one wiki page per source file. The body section is where you add **short attribution notes** per file; frontmatter `sources` stays the canonical path list for tooling.

**Rules:**

1. List **paths relative to the vault root**, e.g. `raw/Clippings/article.md`, `raw/papers/2024-study.pdf` (use the path Obsidian/your editor shows). These paths must appear in frontmatter `sources` as well.
2. **Multiple sources on one page are expected.** Several clips or papers may support the same entity or concept; one synthesized page with several citations is preferred over artificial 1:1 pages for each file.
3. Optional but useful: short sub-bullets noting what each source contributed (e.g. “confirms founding date”, “contradicts revenue note in X”).
4. If the page has no `raw/` input yet, set `sources: []` in frontmatter and state under `**## Sources`** e.g. “No raw sources yet; stub.” Prefer that over omitting the section.
5. **Optional `###` under `## Sources`:** After the path bullets, you may add a subsection such as **`### Provenance and resolution`** for **audit trail** (conflicting exports, why the vault prefers one reading, pointers to **`raw/Authoritative/`**). See **Corrected facts vs provenance** in the style guide. Do **not** skip heading levels (`##` → `###` is correct).

**Example:**

```markdown
## Sources

- `raw/Clippings/acme-announcement.md` — product launch; quoted CEO statement.
- `raw/reports/industry-overview-2025.md` — market size; cross-check with [[Acme Corp]] revenue claim.
```

## Style guide

- **Prose:** Clear and concise. Prefer **bullet points** for lists of facts, steps, or attributes; use short paragraphs when narrative helps.
- **Claims:** **Attribute every factual claim** to its source—inline (e.g. “Per `raw/...` …”) and/or via the **## Sources** bullets (and any **`### Provenance and resolution`** under Sources) so a reader can verify. The summary does not need to repeat long path lists if the **## Sources** section makes verification obvious.
- **Contradictions:** When sources disagree, **do not silently pick a winner.** Once you have a resolution: **`## Summary`** states the **facts the vault adopts** in plain language (the corrected state); **`## Sources`** carries the disagreement and rationale—use a **`### Provenance and resolution`** subsection there (who said what, which evidence the vault follows, link to **`raw/Authoritative/`** when used). If judgment is **still pending**, say so under Sources (or a brief “Open questions” note) rather than asserting a single truth in the summary.

### Source errors vs authoritative vault truth

Exports under `raw/` are **evidence**, not an infallible specification. When an ingested file is wrong, outdated, or contradicted by better evidence **elsewhere in `raw/`**, the correct approach is **not** to rewrite the bad export to match reality (that would destroy the record of what the export actually said). Use this pattern instead:

1. **Keep the flawed export unchanged** in `raw/` unless you explicitly ask to patch or replace the corpus (e.g. re-download).
2. **Record the correction in `wiki/`** on the relevant concept/entity page: **`## Summary`** describes the **corrected state** only (readable, minimal “editorial” framing). Put the **conflict narrative and rationale** under **`## Sources` → `### Provenance and resolution`** (vault paths, weak vs strong claims, **`raw/Authoritative/`** when applicable). Do **not** bury the reader in “how we got here” inside the summary when a resolution exists.
3. **`raw/Authoritative/` (required location for vault-adopted corrections):** Store **short Markdown files** here that state **authoritative disambiguations and corrections** in your own words—what the vault **treats as true** when sources disagree, optional pointers to the strongest `raw/` paths, and links to relevant `wiki/` pages. This is **user-owned** `raw/`: the assistant **reads** and **cites** these files in **`sources`** / **`## Sources`** next to exports and Host docs; it **does not** create, edit, move, or delete them **unless you explicitly ask** (same immutability rule as the rest of `raw/`). *Workflow:* when you resolve a conflict (or approve an agent-proposed resolution), add or update an entry under `raw/Authoritative/` and ensure the affected wiki pages cite it.
4. **Optional index of known issues:** Maintain **`wiki/meta/source-quality.md`** (or similar) as an append-only **registry**: export path, one-line issue, pointer to the wiki page (and/or `raw/Authoritative/` note) where resolution lives. Helps agents and humans spot repeat offenders without re-litigating each time.

This keeps **provenance** (bad text still citeable), **correction** (clearly stated in the editable layer and in **`raw/Authoritative/`** when you want a single named authority), and **auditability** (readers see why the vault disagrees with a given file).

### Corrected facts vs provenance (summary vs Sources)

When a page reflects a **resolved** correction or disambiguation (e.g. export contradicted by Host docs or by **`raw/Authoritative/`**):

- **`## Summary`** should read as **straight description of the facts the vault treats as true**—easy to read without rehearsing the dispute. Avoid opening with “Vault-adopted rule”, “unlike the export…”, or long inline parentheticals about bad wording unless a **brief** qualifier is truly necessary.
- **`## Sources`** keeps the path list as usual, and adds **`### Provenance and resolution`** when needed: what each source claimed, which reading the vault uses, and why—so the audit trail lives **here**, not in the summary.

### `## Summary` quality (no scaffold prose)

The **`## Summary`** section must read as **finished vault text**, not a backlog item.

- **Do not** use placeholder or TODO phrasing such as: “Expand with direct quotes…”, “as the export is ingested further”, “Stub—”, “Add vault paths when…”, or similar. Reserve explicit scaffolding only for rare, user-approved drafts—and never leave it as the default.
- When `sources` / **`## Sources`** list paths under `raw/`, the Summary must include at least **one short paragraph** (or tight bullets) of **synthesized fact** grounded in those files—by paraphrase with attribution, or inline pointers like “Per `raw/...`, …”.
- If you add new linked entity pages in the same pass as a **link graph**, bring them to this standard **in the same session or an immediate follow-up pass**, not as permanent one-line stubs with TODO language.

## Bulk exports, non-Markdown sources, and entity-centric synthesis

`raw/` is **not** limited to Markdown. It may hold **MediaWiki wikitext** (e.g. `*.mediawiki` from an exported forum or wiki), **PDFs**, clipped HTML converted elsewhere, and other formats. `**wiki/` notes are always Markdown** written to this vault’s conventions (YAML frontmatter, Obsidian `[[wikilinks]]`, `**## Sources`**). Treat everything under `raw/` as **read-only evidence**; **do not** rewrite or “fix” source files there to look like vault Markdown unless the user explicitly asks.

When a directory contains many exports (e.g. hundreds of `.mediawiki` files), you may use `**_export_manifest.json`** next to those files (if present) as an **inventory** (titles, page ids, file paths). It is optional but helps batch planning and coverage checks.

**Flarum JSON:API exports** from this repo’s exporter live under **`raw/`** paths such as **`raw/planets.flarum/`** (and optionally other **`raw/<label>.flarum/`** roots using the same script). Layout: tag **bucket** / one folder per **discussion** / **`discussion.meta.yaml`** + ordered **`posts/post-*.md`**. Interpretation and citation habits: **`wiki/meta/corpus-layout-flarum-jsonapi-export.md`**. Other **`raw/`** corpora (wikitext, clippings, etc.) use **different** shapes—do not assume this tree unless the path matches that layout.

### Synthesis strategy: **entity-centric**

When ingesting a large corpus (especially an exported wiki), **prefer synthesized pages keyed to real-world or domain “things”**—factions, mechanics, ships, places, products, organizations—using `**type: entity`** (or `**concept**` for themes/rules) with `**related**` links between them. **Do not** default to one vault `wiki/` page per source file unless the user asks for that shape. Merge overlapping wikitext about the same subject onto **one entity (or concept) page**, with multiple `raw/` paths listed under `**sources`** / `**## Sources**`.

Source wikitext uses MediaWiki links `[[Like This]]`, templates, and categories. Vault pages use **Obsidian** links. When you summarize, **choose clear vault titles** and map confusing or duplicate source titles into those names; note ambiguity in prose or under `**## Sources`** rather than copying the external wiki’s structure blindly.

Pages that are only `#REDIRECT` in the export often should **not** become separate vault pages; fold them into the target entity’s narrative and cite the redirect file if it matters.

### When to **stop and ask the user**

Before starting or continuing a **large** ingest of a new corpus, if **what counts as the main entities** (the primary “things” that deserve top-level entity pages) is **uncertain** from context—e.g. the domain is unfamiliar, naming is messy, or several competing taxonomies are plausible—**stop and ask the user** to name or confirm the entity set and priorities (and any disambiguation rules). **Do not invent the master list of “main entities” by guesswork** when it would materially shape the vault. Shorter or exploratory ingests may proceed without that pause, but err on the side of **asking** when structure hinges on domain judgment.

## Operations (summary)

- **Ingest:** Read new material in `raw/`, discuss if useful, then update relevant wiki pages, `wiki/index.md`, and append a dated entry to `wiki/log.md` listing touched pages, **raw paths**, and **domain** (canonical label) for the ingest. **New domain:** add **`wiki/meta/domain-registry.md`** row, create **`wiki/concepts/<slug>/<Canonical Domain Label>.md`** hub, and place new concept notes under **`wiki/concepts/<slug>/`** with **`Concept (Domain)`** titles and matching **`domain:`**. While ingesting, apply **Dense wikilinking** and watch for **Latent concepts**: recurring unnamed “things” across sources or existing wiki pages: evaluate whether to add a hub page and replace scattered mentions with `[[wikilinks]]` (see those subsections under **Page conventions**).
- **Query:** Answer from the wiki when possible; cite `raw/` paths via each page’s Sources section and inline where helpful. **Compound** durable material into `wiki/` as described below (answers, corrections, and **new synthesis**).
  - **Multi-aspect or procedural questions:** When the user asks for **options**, **responses**, **steps**, or **what to do** in a situation that may involve **more than one** concept (rules, policies, or entities split across pages), read the **primary page** and, in the **same pass**, other notes linked from its YAML **`related`** and from **`## Summary`** (including **`[[wikilinks]]`** there)—do not treat the first page opened as sufficient by default. If the hub includes a **checklist or merged playbook** subsection (see **`wiki/concepts/README.md` → Multi-link topics**), use it as the coordination point before answering.
  - **What to file:** (1) **Direct answers** to questions that will come up again (facts plus citations). (2) **Corrected** claims when a first pass was wrong—update or add pages so the wiki holds the right answer, with **`### Provenance and resolution`** under **`## Sources`** if the fix depends on reconciling sources or explaining a past mistake. (3) **Synthesis:** connections, scenarios, or comparisons that are **grounded in `raw/`** but **not spelled out in any single source**—for example linking one article’s stat table with another’s racial rules, or stating implications of “no trade / no capture” for fleet comparisons. Synthesis belongs in `wiki/` (often with an explicit **Provenance** note); use **`raw/Authoritative/`** only when `raw/` is **wrong** or the vault needs a named adopted rule file, not merely when ideas are **assembled** from correct exports.
  - **When synthesis is “good” enough to add:** It is **reusable** (not a one-off quirk), **defensible** (every non-obvious claim traceable to cited `raw/` paths), **non-duplicative** (merge into an existing page if the scope fits), and **clearly labeled** where reasoning goes beyond a single quote (see **`### Provenance and resolution`**). If unsure, **prefer asking** rather than inventing taxonomy or game facts.
  - **User approval for new synthesis:** **Before writing** discussion-derived synthesis to `wiki/`, the assistant should **ask the user** whether to add it (unless the user has **already approved** in the same thread—e.g. “add this to the wiki” or a checklist request that includes wiki updates). The user may confirm **multiple** additions in one conversation; **each time** a distinct piece of synthesis becomes worth persisting, **ask again** if approval has not yet been given for that material. After adding, update **`wiki/index.md`** when pages are new or meaningfully changed, and append **`wiki/log.md`** (see session behavior).
- **Lint (on request):** Health-check the wiki. Look for: contradictions between pages, stale claims that newer sources have superseded, mismatch between wiki text and cited `raw/` (including `raw/Authoritative/` when present), orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing cross-references, data gaps that could be filled with a web search.
  - **Domain hygiene (when lint touches concepts):** List every **`wiki/concepts/<slug>/*.md`** (and `_shared/*.md`) and verify: **`domain:`** present and matches **`wiki/meta/domain-registry.md`** for that slug; **`_shared`** notes **omit** **`domain:`**; **`title:`** matches filename stem; **`wiki/index.md`** links use the full path **`wiki/concepts/<slug>/…`**. Flag any legacy flat paths or missing `domain:`.
  - **Domain backfill pass (optional; on request or when registry adds a new domain):** Scan for concept pages that **lack** `domain:` but **belong** to a known corpus (infer from `sources` paths, inbound links from a domain hub, or user confirmation). **Default:** emit a **report** (path, suggested `domain`, suggested `title` rename, link rewrites)—do **not** mass-rename without **user approval in-thread** or a **one-off** explicit instruction. **Auto-apply** only when: a single domain candidate is **unambiguous** (e.g. all `sources` under one corpus) **and** the user has approved batch repair **or** the fix is a trivial follow-up from a **just-completed** ingest.
  - **Linking pass (required when lint touches content):** Prefer a **concept-driven** sweep (titles + aliases) so plain-text and list-shaped mentions are caught—not only **bold** spans. Still scan for **emphasis used like wikilinks** (including **compound** bold). **Replace** with `[[…]]` (pipe display text when grammar or vault title length requires it). Use **`wiki/meta/concept-aliases.md`** plus **Concept aliases and normalization** for surface forms that are not identical to note titles. Where two related pages discuss the same topic without pointing at each other, **add** sensible outbound/inbound wikilinks or `related` frontmatter entries. Prefer **denser** linkage when it does not clutter (see **Dense wikilinking**).
    - **Title/alias mention sweep (generic):** Build a candidate string set from (1) every concept **`title:`** (or filename stem under `wiki/concepts/**`), (2) every **surface form** in **`wiki/meta/concept-aliases.md`** that applies to the file’s **`domain:`** (see **Concept aliases**), and (3) optional rare **note-local** `aliases:` in YAML when present. Search **`wiki/**/*.md`** (respect **`raw/`** immutability—do not “lint” sources there) using **word-boundary** or whole-token matching; **exclude** occurrences inside **wikilink** brackets `[[…]]`, and **exclude** or treat carefully inside **fenced code**, **inline code**, and **YAML frontmatter** so you do not spam candidates from paths or metadata. For each hit, determine whether it is **already linked to that concept**: the span must be covered by a wikilink whose **target** resolves to the right hub (not merely “there is a `[[` elsewhere on the line”). For remaining hits, **triage in context**—batch by file or by concept in one pass; no need for a literal sub-agent per occurrence unless you choose that workflow. If the prose **does** refer to the hub → add `[[wiki/concepts/<slug>/…|…]]` as needed. If **ambiguous** (English collision, domain judgment) → note in **`wiki/log.md`** or **ask the user** per **Concept aliases and normalization**. If it **does not** refer to the vault topic → **leave plain**, **reword**, or document; **do not** force a link. **Optional:** a small script may emit a **candidate list** (path, line, string, suggested target) for the main agent to resolve.
    - **Per span, not per line:** Evaluate **each** emphasis span on its own. **Do not** skip a whole line (or paragraph) just because it already contains a `[[wikilink]]` elsewhere—mixed linked + bold-only mentions on one line are a common miss (e.g. one `[[starbase]]` plus a bold list of component types that should also link).
    - **Split compound emphasis:** If one `**…**` span contains **multiple** separable domain terms (lists, enumerations, “A, B, and C”), **split** into per-term links (or unlink non-concepts) rather than leaving a single bold block.
    - **Matching:** Compare prose to page titles after **case-folding**; use the **alias registry** for **plurals, shortened words, and alternate casing** (e.g. “beams” → `[[wiki/concepts/planets-nu/Beam weapons (Planets.nu)|beams]]`). When the export uses a **generic word** but the vault hub uses a **longer title**, link with a **pipe**. Treat **ambiguous** short aliases in the registry with extra care when grepping (see **Notes** column there).
    - **Enumerations:** Short **comma- or list-style** rolls of domain “parts” (ship components, tech tracks, etc.) should default to **wikilinks to existing notes**, not bold-only, when those pages exist.
    - **Spot-check:** After automated scans, briefly review **high-risk** pages—e.g. `## Summary` sections that contain **both** wikilinks (`[[…]]`) and emphasis (`**…**`)—to catch mixed patterns the heuristic missed. Treat summaries with **compound bold** as high-risk even if a script reported “no exact single-title match.”
  - **Latent concepts (same as ingest):** Search for **recurring references** (bold, plain, or synonymous phrasing) to an idea that still lacks a first-class page—or has overlapping stubs. **Evaluate** whether to promote to a dedicated page, merge into an existing note, or document in **`wiki/log.md`** as an open follow-up; **ask the user** when structure is unclear (**Latent concepts**).
  - **When the fix is obvious:** If the **weight of evidence** in `raw/` (including stronger exports and any **`raw/Authoritative/`** notes) **clearly contradicts** what a wiki page says, **update the wiki** directly: correct the prose, align **`sources`** / **`## Sources`**, bump **`last-updated`**, and append a brief line to **`wiki/log.md`**. Do not leave the wrong claim standing.
  - **When the fix is not obvious:** **Do not guess.** **Raise the issue with the user** in clear terms (what the wiki says, what the sources say, why it is ambiguous). Offer **concrete next steps** where helpful—for example: search for or ingest additional material on a specific topic; ask the user which of two documented options matches their game/host setup; or ask the user to add or amend an entry under **`raw/Authoritative/`** so the vault has an explicit adopted rule.

## Session behavior

- Treat `**wiki/`** as the editable knowledge layer; treat `**raw/**` as read-only unless the user instructs otherwise.
- After substantive edits, refresh `**wiki/index.md**` when new pages appear or titles change; append to `**wiki/log.md**` for ingests and significant maintenance.

## Documentation map

This file (`AGENTS.md`) is **canonical** for assistants. Folder `**README.md`** files in the vault (vault root, `raw/`, `raw/Clippings/`, `wiki/` and its subfolders—**including `wiki/meta/`** when present—`journal/`, `content/`) restate how each path fits these rules—keep them aligned when `AGENTS.md` changes. The workspace `**README.md**` (one level above the vault folder) points into the vault. `**.cursor/rules/personal-wiki-knowledge-base.mdc**` is a short IDE reminder; it does not replace this document.