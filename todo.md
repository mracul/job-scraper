# TODO — Phase 6–7 UI/UX Upgrade + File Restructure (Agent Guide)

This TODO is designed to be executed **incrementally** with the app remaining runnable after each slice.

## Non‑Negotiables

- **Move first, refactor second.** Extract code verbatim, then improve.
- After each step: **App boots + key pages render**.
- **No direct URL writes** in views/components (must go through existing `navigate_to()` / state sync helpers).
- Avoid circular imports:
  - `ui/components/*` **must not** import `ui/views/*`
  - `pipeline/*` **must not** import Streamlit
  - `ui/views/*` may import `ui/components/*`, `pipeline/*`, `storage/*`, `ai/*`

## Smoke Checks (run after each phase)

- App boots
- Reports list renders
- Open single report overview
- Open Job Explorer and open a job detail view
- Overview page renders
- Settings page renders + saves

---

# Phase 0 — Prep (no behavior changes)

- [ ] Create folders (if missing):
  - [ ] `ui/views/`
  - [ ] `pipeline/`
  - [ ] `storage/`
  - [ ] `scrapers/browser/`
  - [ ] `app/`
- [ ] Add `__init__.py` only if needed by your import style (avoid overdoing packages).

✅ Acceptance: no runtime changes.

---

# Phase 7 — UI/UX Components First (connectivity + consistency)

> Goal: make the UI feel “one product” before splitting views.

## 7.1 Breadcrumb Bar (fix “disconnected” feel)

**Create:** `ui/components/breadcrumb_bar.py`

- [x] Implement `render_breadcrumb_bar(path, chips=None, actions=None, compact=False)`
- [x] Breadcrumb path rules:
  - [x] Render as a true hierarchy with separators: `A › B › Current`
  - [x] Max depth 3
  - [x] Exactly one active segment (final, not clickable)
  - [x] Long labels shortened + tooltip with full text
  - [x] Must not wrap to 2 lines
- [x] Chips rules (informational):
  - [x] Max 4 chips visible
  - [x] Examples: `204 jobs`, `filters: 3`, `match: any`, `topN: 10`
- [x] Actions rules (utilities only here):
  - [x] Hard limit: ≤ 1 primary, ≤ 2 secondary/icon
  - [x] Prefer `Copy link` as **icon-only** action

✅ Acceptance: breadcrumb displays consistently across at least two pages.

---

## 7.3 Status Badge (single source of truth)

**Create:** `ui/components/status_badge.py`

- [x] Implement `render_status_badge(state, text=None, tooltip=None, size='sm', variant='pill')`
- [x] Canonical states:
  - [x] `cached` → ✅ cached
  - [x] `outdated` → ⚠️ outdated
  - [x] `generated` → ℹ️ generated
  - [x] `dirty` → ● unsaved changes
- [x] Rules:
  - [x] Same icon + wording everywhere
  - [x] Tooltip supported
  - [x] Never wraps; tooltip for truncated labels

✅ Acceptance: used in at least 2 places (header + list row).

---

## 7.2 Page Header (standard header for every page)

**Create:** `ui/components/page_header.py`

- [x] Implement `render_page_header(path, title, subtitle=None, actions=None, status=None, compact=False, divider=True)`
- [x] It renders:
  - [x] Breadcrumb bar (7.1)
  - [x] Title (dominant)
  - [x] Subtitle (one-liner; required for non-trivial pages)
  - [x] Optional status badge inline with title
  - [x] Optional divider line

### Action Button Placement & Styling Spec (critical)
- [x] Action hierarchy:
  - [x] **Primary (max 1)**
  - [x] **Secondary (max 2)**
  - [x] Overflow `⋯` for the rest
- [x] Header actions appear ONLY for **decision/operation pages**:
  - [x] Overview, Single Report Overview, Compiled Overview
- [x] Browsing pages should NOT have header primaries:
  - [x] Reports list, Job Explorer, Settings (save is footer), New Run (form CTA)
- [x] Action kinds: `primary | secondary | danger | icon`
- [x] Visual rules:
  - [x] Primary = filled/accent
  - [x] Secondary = outline/muted
  - [x] Icon = icon-only utilities
  - [x] Danger = red outline/solid, spaced away from primary
- [x] Sticky action bar:
  - [x] Only on long pages with critical primary action (Overview, Compiled Overview)
  - [x] Shows primary action only + optional timestamp text

✅ Acceptance: Overview and Reports list use the header, but only Overview shows a primary action there.

---

## 7.4 Bulk Action Bar (Reports selection UX)

**Create:** `ui/components/bulk_action_bar.py`

- [x] Render only when selection count > 0
- [x] Shows: `X selected | Compile (primary) | Delete (danger) | Clear`
- [x] Must explain disabled actions via tooltip if relevant

✅ Acceptance: Reports list no longer shows dead “Compile/Delete” buttons when nothing selected.

---

## 7.5 Reports List Table (density + scanability)

**Create:** `ui/components/run_list_table.py`

- [x] Replace tall run "cards" with compact rows
- [x] Columns: checkbox | title | job count | timestamp | status | actions (icons/⋯)
- [x] Add: search + sort (newest, jobs count, name)
- [x] Keep per-row actions minimal; prefer ⋯ menu

✅ Acceptance: Reports page scroll height reduces significantly; selection workflow is clearer.

---

## 7.6 Job Explorer Components (scale + clarity)

**Create:**
- `ui/components/job_filter_toolbar.py`
- `ui/components/job_result_row.py`
- (optional) `ui/components/pagination.py`

- [x] Toolbar includes:
  - [x] Search box (title/company)
  - [x] Sort dropdown
  - [x] Match any/all toggle
  - [x] Clear filters inline
  - [x] "filters active" summary chip
- [x] Job rows:
  - [x] Row clickable OR compact "View" icon (avoid giant button per row)
  - [x] Metadata chips: source, posted age, work type, remote/hybrid/onsite, salary
- [x] Pagination:
  - [x] "Show 50 more" to avoid rendering hundreds of rows

✅ Acceptance: Job Explorer feels faster and less visually noisy.

---

## 7.7 Overview Components (consistency + previews)

**Create:**
- `ui/components/metrics_row.py` (optional)
- `ui/components/bar_rank_list.py` (optional)
- `ui/components/category_snapshot_row.py` (recommended)

- [x] Category snapshot rows show:
  - [x] Category name
  - [x] Top 3 terms as chips
  - [x] "View all (n)"
  - [x] Truncation indicator if topN applied
- [x] Market context bars show totals and "Other" if non-100%

✅ Acceptance: Overview “Category Snapshots” no longer feels empty when collapsed.

---

# Phase 4 — Storage + Pipeline Regroup (safe moves)

> Goal: separate storage and transforms from UI.

## 4.1 Storage moves (verbatim)

Move files (update imports, no logic changes):

- [x] `job_storage.py` → `storage/job_store.py`
- [x] `compiled_report_store.py` → `storage/compiled_report_store.py`
- [x] `cookie_store.py` → `storage/cookie_store.py`
- [x] `url_skip_store.py` → `storage/url_skip_store.py`

✅ Acceptance: existing functions callable, no Streamlit imports added.

---

## 4.2 Pipeline: dedup + requirements analysis

Move/rename:

- [x] `deduplication.py` → `pipeline/deduplicator.py`
- [x] `analyze_requirements.py` → `pipeline/requirements_analyzer.py`

Add orchestrator:

- [x] Create `pipeline/analysis_runner.py`
  - [x] Deduplicate once
  - [x] Run requirements analysis (with analyzer dedupe disabled if supported)
  - [x] Return: analysis_json + dedup stats + effective_jobs

✅ Acceptance: counts stable across views; no double-dedupe.

---

## 4.3 Overview pipeline

- [x] Create `pipeline/overview_builder.py`
  - [x] Takes run set + cutoff/half-life/topN
  - [x] Returns overview payload used by UI + AI bundle

(Optional later)
- [ ] `exports/overview_export.py`

✅ Acceptance: Overview page calls builder; logic removed from UI.

---

# Phase 5 — AI Bundle (assumed complete, but verify integration)

> Verify all views pass the **bundle** to AI UI and prompts are bounded.

- [x] Ensure `ai/ai_payloads.py` bundle schema is used in all callsites
- [x] Ensure AI prompt uses structured JSON first; only **capped** report text excerpt
- [x] Ensure cache key uses bundle fingerprint (stable)

✅ Acceptance: no prompt overflow; AI card shows Inputs row (jobs/scope/topN/model).

---

# Phase 6 — Extract Views (thin slices, one at a time)

> Goal: `streamlit_app.py` becomes a router.

## 6.1 Reports view

- [x] Create `ui/views/reports.py`
- [x] Move (verbatim first):
  - [x] reports list rendering
  - [x] single report overview rendering
  - [x] compiled overview rendering
- [x] Replace in `streamlit_app.py` with:
  - [x] `from ui.views.reports import render_reports_page`
  - [x] route to `render_reports_page()`

Use components:
- [x] `render_page_header`
- [x] `run_list_table`
- [x] `bulk_action_bar`
- [x] AI summary block

✅ Acceptance: reports list + overview + compiled overview work.

---

## 6.2 Jobs view

- [x] Create `ui/views/jobs.py`
- [x] Move:
  - [x] Job Explorer list
  - [x] Job detail view
- [x] Use:
  - [x] `job_filter_toolbar`
  - [x] `job_result_row`

✅ Acceptance: explorer filters + job detail work; URL back/forward still works.

---

## 6.3 Overview view

- [x] Create `ui/views/overview.py`
- [x] Move overview page render
- [x] Call `pipeline/overview_builder.py`
- [ ] Add sticky action bar (primary only) due to long page

✅ Acceptance: overview generate/export unchanged; sticky CTA visible.

---

## 6.4 New Run view

- [ ] Create `ui/views/new_run.py`
- [ ] Move:
  - [ ] single search form
  - [ ] bundle selection UI
  - [ ] run progress/state display
- [ ] Wrap form in `st.form` for cleaner submits
- [ ] Split options: common vs advanced within expander

✅ Acceptance: start run works; progress works.

---

## 6.5 Settings view

- [ ] Create `ui/views/settings.py`
- [ ] Move settings UI + save/reset
- [ ] Add dirty tracking:
  - [ ] show status badge `dirty` in header when unsaved
  - [ ] disable Save unless changes exist
- [ ] Move Reset to “Danger zone” section

✅ Acceptance: settings persist; UX improved.

---

# Phase 7.9 — Thin Router + Final Cleanup

## Router module

- [ ] Create `app/router.py`
  - [ ] reads session state
  - [ ] calls correct view
  - [ ] no business logic

## Reduce `streamlit_app.py`

- [ ] Keep only:
  1) session init
  2) URL → state apply
  3) sidebar render
  4) router call
  5) passive URL sync

Target: **200–400 lines**

✅ Acceptance: app behavior unchanged, codebase navigable.

---

# File Splitting Guide (Current → Target Mapping)

## AI
- `ai/ai_payloads.py` (exists)
- `ai_summary_core.py` → `ai/ai_summary_core.py` (optional relocate)
- `ai_summary_ui.py` → `ai/ai_summary_ui.py` (optional relocate)

## Pipeline
- `analyze_requirements.py` → `pipeline/requirements_analyzer.py`
- `analyze_requirements_optimized.py` → fold into `pipeline/requirements_analyzer.py` or delete after merge
- `deduplication.py` → `pipeline/deduplicator.py`

## Storage
- `job_storage.py` → `storage/job_store.py`
- `compiled_report_store.py` → `storage/compiled_report_store.py`
- `cookie_store.py` → `storage/cookie_store.py`
- `url_skip_store.py` → `storage/url_skip_store.py`

## Scrapers (optional later)
- `browser_scraper.py` → `scrapers/browser/browser_scraper.py`
- `seek_scraper.py` → `scrapers/seek_scraper.py`
- `indeed_scraper.py` → `scrapers/indeed_scraper.py`

---

# Definition of Done

- `streamlit_app.py` is a router (thin).
- Views live in `ui/views/*` and are readable.
- Reusable UI elements live in `ui/components/*`.
- Pipeline + storage separated; no Streamlit imports in pipeline/storage.
- Breadcrumbs/headers/actions follow the UX rules:
  - browsing pages don’t show header primaries
  - decision pages do
  - sticky CTA only when necessary
- AI summaries are structured + bounded + auditable.
