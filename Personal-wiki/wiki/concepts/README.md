# concepts

**Definitions, frameworks, themes, topic overviews, and non-person entities** (companies, products, places) when you keep them with general knowledge rather than under **`people/`**.

## Conventions

- **Layout:** Domain-scoped concepts live in **`wiki/concepts/<slug>/`** with **`Concept (Domain)`** titles and YAML **`domain:`** (see **`AGENTS.md`** → Domains). Cross-domain hubs live in **`wiki/concepts/_shared/`** (no `domain:`). **Hub:** `wiki/concepts/<slug>/<Canonical Domain Label>.md`.
- Prefer **stable filenames/titles** that match how you link, e.g. `[[wiki/concepts/planets-nu/Planet (Planets.nu)]]` or short titles when unambiguous.
- **`type`:** usually **`concept`**; use **`entity`** for organizations, products, places, or other “thing” pages when **`person`** does not apply. Use **`source-summary`** or **`comparison`** when the page’s purpose matches those types (still stored here or elsewhere in `wiki/` per taste—see `AGENTS.md`).
- **Frontmatter + `## Sources`** — same as all wiki articles; list every `raw/` file that backs the page; **attribute** claims and **note disagreements** between sources.

### Multi-link topics (procedural answers)

Some questions combine **one main concept** with **other concepts** whose rules live on **separate** pages (interacting subsystems, cross-references, or policies). To keep answers complete without putting domain playbooks in **`AGENTS.md`**:

- On the **hub** page for the main topic, add a **`###` subsection** whose title fits the domain (e.g. *Responses*, *Options*, *Checklist*, *Interactions*, *Resolution steps*) and **list** the coordinated points with dense **`[[wikilinks]]`** to satellite notes.
- Ensure YAML **`related`** on that hub includes **each** satellite page that a full answer should traverse.
- Optional: one short sentence in that subsection pointing readers to this README pattern, or to a **domain** README under **`wiki/concepts/<slug>/README.md`** when the corpus maintains a **table of hubs** that use checklists (see e.g. **`wiki/concepts/planets-nu/README.md`**).

Details: **`AGENTS.md`** (vault root) — **Operations → Query** (*Multi-aspect or procedural questions*).
