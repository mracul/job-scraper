# UI / UX + STRUCTURE REQUIREMENTS (FINAL)

## 1. Sidebar Requirements (Global Only)

### Purpose

The sidebar is **global navigation and global status only**.
It must never compete with page headers, breadcrumbs, or action bars.

### Sidebar MUST contain

* App identity (name/logo)
* Global statistics (e.g. total jobs scraped, reports count)
* Top-level navigation only:

  * Overview
  * Reports
  * New Run
  * Settings

### Sidebar MUST NOT contain

* Contextual navigation (report names, job counts, filters)
* Page-specific actions (Generate, Compile, Save, Export, etc.)
* Breadcrumbs or hierarchical indicators
* Status badges (cached/outdated/dirty)
* Form controls or toggles

### Sidebar Behaviour Rules

* One active section at a time
* No nested or dynamic entries
* Clicking a sidebar item switches **page only**, nothing else

---

## 2. Canonical Page Layout (Mandatory)

Every page MUST render content in the following vertical order:

```
BreadcrumbBar
PageHeader
ActionBar (optional)
Page-specific content
```

Any deviation from this order must be corrected.

---

## 3. Breadcrumb Requirements

### Purpose

Breadcrumbs provide **contextual navigation** and reflect hierarchy within a section.

### Placement

* Breadcrumbs MUST be rendered **inside the PageHeader**
* Breadcrumbs MUST appear on all pages except first-load empty states

### Structure Rules

* First crumb: top-level section (Overview, Reports, New Run, Settings)
* Middle crumbs: selected entities (e.g. report name)
* Last crumb: current view (non-clickable)

### Mapping

| Page          | Breadcrumb                     |
| ------------- | ------------------------------ |
| Overview      | Overview                       |
| Reports list  | Reports                        |
| Report detail | Reports › {Report Name}        |
| Job Explorer  | Reports › {Report Name} › Jobs |
| New Run       | New Run                        |
| Settings      | Settings                       |

### Interaction Rules

* Previous crumbs are clickable
* Current crumb is highlighted and non-clickable
* Breadcrumbs must match session state + URL

---

## 4. PageHeader Requirements

### Purpose

The PageHeader provides **identity, purpose, and state** for a page.

### PageHeader MUST render

* Breadcrumb bar
* Page title (single noun phrase)
* Subtitle (single-line purpose description)
* Optional status badge (right-aligned)

### PageHeader MUST NOT contain

* Buttons
* Filters
* Metrics
* Forms

### Title Rules

* Short, clear, non-duplicative
* Examples:

  * Overview
  * Reports
  * Job Explorer
  * Start New Scraping Run
  * Settings

### Subtitle Rules

* One sentence explaining what the page does
* No dynamic data dumps

---

## 5. Status Badge Requirements

### Purpose

Indicate **data or configuration state** at the page level.

### Allowed States

* cached (✅)
* outdated (⚠️)
* generated (ℹ️)
* dirty (● — Settings only)

### Placement Rules

* Status badge MUST appear only in the PageHeader
* Maximum one badge at a time
* Never clickable
* Never inline with content

---

## 6. Action Button / ActionBar Requirements

### Purpose

Actions must be **clearly associated with the page**, not buried in content.

### Placement

* ActionBar appears directly below PageHeader
* Never inline with forms or content blocks

### Button Hierarchy Rules

* One primary action per page (filled / red)
* Secondary actions are outlined
* Primary action is always left-most

### Page-specific Rules

**Overview**

* Primary: Generate / Update
* Secondary: Export

**Reports**

* Primary: Compile
* Secondary: Delete
* Disabled when no selection

**Job Explorer**

* No ActionBar unless bulk actions exist

**New Run**

* Primary: Start Run
* No competing primary actions

**Settings**

* Primary: Save
* Secondary: Reset
* Save disabled until dirty

---

## 7. Page-Level UX Alignment Rules

### Overview

* Controls grouped in a parameters card
* Actions moved to ActionBar
* Status badge reflects cache state

### Reports

* Rows visually grouped
* Bulk actions separated from rows
* Breadcrumb reflects hierarchy

### Job Explorer

* Breadcrumb anchored to header
* Result count styled as metadata
* Filters visually separated from results

### New Run

* Bundle selection precedes action
* Start Run visually isolated
* No secondary actions competing

### Settings

* Dirty badge visible when modified
* Save disabled until dirty
* Reset visually secondary

---

## 8. Guardrails for Implementation (Agent Rules)

### Absolute Rules

1. Do NOT delete existing logic unless explicitly instructed.
2. Do NOT add new UI concepts or patterns.
3. Do NOT move files unless required by a specific step.
4. One page fixed per commit.
5. If unsure, copy existing code — do not refactor.

### Component Rules

* Components must not import views.
* Views must not import other views.
* Sidebar must remain global and static.
* PageHeader owns breadcrumbs and status.

### Recovery Rule

If a change breaks:

* Revert the last commit
* Do not patch forward blindly

---

## 9. Definition of "Done"

A page is considered correct when:

* Sidebar answers: *Where can I go globally?*
* Breadcrumbs answer: *Where am I within this section?*
* Header answers: *What is this page and what state is it in?*
* Actions answer: *What can I do here?*

If two elements answer the same question, the layout is wrong.

---