# raw

**Your curated source library.** Articles, papers, exports, archives, and other inputs to the knowledge base.

Files here are the **source of truth** for factual claims that appear in **`wiki/`**. Assistants **read** `raw/` to ingest material; they **do not** edit, move, or delete paths here unless you explicitly ask. Vault-relative paths (e.g. `raw/Clippings/note.md`) are listed in each wiki article’s **YAML `sources`** field and **`## Sources`** section—keep those lists aligned with what you actually cite.

Put subfolders here as needed (`Clippings/` for web clips, bulk exports by domain, and so on).

**`Authoritative/`** — Fixed location for **your** short Markdown notes that state **vault-adopted corrections and disambiguations** when exports disagree or are vague. List these paths in **`sources`** / **`## Sources`** on affected wiki pages. Assistants **read** and **cite** them; they **do not** edit this folder unless you **explicitly** ask. See **`AGENTS.md` → “Source errors vs authoritative vault truth”.**

**Full conventions:** `AGENTS.md` in the vault root.
