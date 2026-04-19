---
name: ingest-planets-flarum
description: >-
  Runs flarum_discussions_export.py against https://planets.flarum.cloud/ into
  Personal-wiki/raw/planets.flarum/, uses _export.runs.jsonl as an incremental
  cursor, appends wiki/log.md for the export, then performs the vault
  ingestion synthesis step: compound new or updated forum evidence into wiki/
  per Personal-wiki/AGENTS.md Operations → Ingest (entity-centric pages,
  sources/## Sources, dense wikilinks, index.md and log when wiki pages
  change). Use when the user wants to ingest or update Planets Flarum forum
  exports, refresh raw/planets.flarum discussions, or run the full Flarum
  JSON:API + wiki synthesis workflow.
---

# Ingest Planets Flarum into `raw/planets.flarum`

**On-disk layout and ingest semantics** (thread vs bucket, metadata files, post ordering): **`Personal-wiki/wiki/meta/corpus-layout-flarum-jsonapi-export.md`** (vault-relative: **`wiki/meta/corpus-layout-flarum-jsonapi-export.md`**).

## Assumptions

- **Repo root** is the workspace folder that contains **`Personal-wiki/`** (vault: `raw/`, `wiki/`) and **`scripts/python/flarum_discussions_export.py`**.
- **Python:** `scripts/python/pyproject.toml` sets **`requires-python = ">=3.11"`**. The exporter is **stdlib-only**, but it uses **3.11+ APIs** (e.g. `datetime.UTC`). **Do not** run it with whatever `python3` is first on `PATH`—that may be an older pyenv/system Python.

## Python interpreter (always use the project venv)

From **repo root**, prefer the checked-in venv (created under `scripts/python/`, often via **`uv`**):

| Approach | Command pattern |
|----------|-----------------|
| **Direct (recommended for agents)** | `scripts/python/.venv/bin/python scripts/python/flarum_discussions_export.py …` |
| **uv** (from `scripts/python/`) | `cd scripts/python && uv run flarum-export-discussions …` — use **paths relative to that cwd** for `--output-dir` / `--run-log` (e.g. `../../Personal-wiki/raw/planets.flarum`), or stay at repo root and use the **`.venv/bin/python`** line above. |

If **`.venv` is missing**, run **`cd scripts/python && uv sync`** (or install **Python ≥3.11** and recreate the venv per project norms), then retry.

## Paths (from repo root)

| Role | Path |
|------|------|
| Script | `scripts/python/flarum_discussions_export.py` |
| Output directory | `Personal-wiki/raw/planets.flarum/` |
| Run log (JSON Lines, cursor) | `Personal-wiki/raw/planets.flarum/_export.runs.jsonl` |

## Procedure

### 1. Choose `--since`

- If **`_export.runs.jsonl`** exists: read the **last non-empty line**, parse JSON. If **`last_content_instant`** is a non-empty string, pass **`--since`** with that value exactly (inclusive filter in the exporter).
- Otherwise: **omit `--since`** for a full export over all public threads the API lists.

### 2. Execute

From repo root (replace the interpreter path if your venv lives elsewhere, but **always** use **≥3.11** from this project):

```bash
scripts/python/.venv/bin/python scripts/python/flarum_discussions_export.py \
  --base-url https://planets.flarum.cloud \
  --output-dir Personal-wiki/raw/planets.flarum \
  --run-log Personal-wiki/raw/planets.flarum/_export.runs.jsonl \
  [--since "<last_content_instant from previous line>"]
```

Keep default **`--sleep`** (0.15) unless rate-limit errors suggest increasing it.

### 3. Vault bookkeeping (`Personal-wiki/AGENTS.md` → **Operations → Ingest**)

After **success** (script exit 0):

1. Parse the **last line** of **`_export.runs.jsonl`** for `run_utc`, `since`, `last_content_instant`, `discussions_processed`, `discussions_written`, `posts_written`.
2. **Append** to **`Personal-wiki/wiki/log.md`** (bottom):

   - Heading: `## [YYYY-MM-DD] ingest | Planets Flarum JSON:API export` (date = calendar day of the run in the user’s context, or UTC date from `run_utc` if unknown).
   - Bullets: base URL; whether **`since`** was `all time` or the ISO instant; the counts above; next-run cursor = **`last_content_instant`** (or note `null` if nothing written).
   - Footer line: `_Raw paths touched: raw/planets.flarum/ (see _export.runs.jsonl)._` (adjust to match existing log tone).

3. **`wiki/index.md`:** Update when new wiki pages are added or existing pages are meaningfully changed (**`AGENTS.md` → session behavior / Operations → Ingest**).

4. **Ingestion synthesis (required in the same session):** After the export log entry, perform the **`AGENTS.md` → Operations → Ingest** pass on material under **`raw/planets.flarum/`** written or updated by this run—**not** raw-only. Treat forum exports as **`raw/` evidence**: merge durable, reusable claims into existing **`wiki/concepts/**`** (and related) pages where scope fits; add or split pages per **entity-centric synthesis** and **atomic** scope; keep **`sources`** and **`## Sources`** in sync with cited paths; apply **dense wikilinking** and extend **`wiki/meta/concept-aliases.md`** when new surface forms recur. **Stop and ask the user** when domain taxonomy or “main entities” are unclear (**`AGENTS.md` → When to stop and ask the user**). **Append or extend `wiki/log.md`** to record wiki pages touched, **`raw/planets.flarum/…`** paths substantiating changes, and domain label(s) when concepts under a scoped slug were updated—either merged into the same dated ingest block as the export or as a follow-on subsection, consistent with existing `log.md` tone.

### 4. Failure handling

If the script fails: report stderr/exit code; **do not** append a success ingest entry to **`wiki/log.md`**. Partial files under **`raw/planets.flarum/`** may exist from interrupted runs; re-running is idempotent for paths the exporter overwrites.

## Output shape (raw mirror + input to synthesis)

- **`raw/planets.flarum/<SectionTag>/<discussion-slug>/discussion.meta.yaml`**
- **`raw/planets.flarum/<SectionTag>/<discussion-slug>/posts/post-NNNN-<id>.md`**

Section folder = deepest tag on the thread (see script docstring). Treat everything under **`raw/`** as **read-only evidence** after export except re-running this tool.

## Scope limits

- **Guest-visible** threads only (no API token in this workflow).
- Cursor field **`last_content_instant`** = max of post **`createdAt`** / **`editedAt`** among posts **written** that run; use it as the next **`--since`**.
