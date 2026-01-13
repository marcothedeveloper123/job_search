# API Reference

Server: `http://localhost:8000`. Module: `from job_search import *`

## Data Structures

### Job

| Field | Type | Notes |
|-------|------|-------|
| `job_id` | string | Prefix: `job_li_`, `job_cz_`, `job_sj_` |
| `title`, `company`, `location`, `url` | string | Core info |
| `source` | string | `linkedin` / `jobs.cz` / `startupjobs.cz` |
| `level` | string | `senior` / `staff` / `principal` / `lead` / `other` |
| `ai_focus` | bool | AI/ML signals detected |
| `jd_text` | string? | JD markdown (NOT `description`) |
| `verdict` | string? | `Pursue` / `Maybe` / `Skip` |
| `archived`, `stale` | bool | Stale = >45 days posted |

### DeepDive

| Field | Type | Notes |
|-------|------|-------|
| `job_id` | string | References Job |
| `status` | string | `pending` / `complete` |
| `research` | object | `{company, role, compensation}` |
| `research_notes` | object | `{employee: [{finding, sentiment}], customer: [...], company: [...]}` |
| `conclusions` | object | `{fit_score, attractions, concerns}` |
| `recommendations` | object | `{verdict, next_steps, questions_to_ask}` |

### Application

| Field | Type | Notes |
|-------|------|-------|
| `application_id` | string | Use for update calls |
| `job` | object | `{job_id, title, company, url}` |
| `status` | string | `pending` / `submitted` / `interviewing` / `rejected` / `offer` |
| `cv_tailored`, `cover_letter` | string | Markdown. DOCX auto-generated on save |
| `gap_analysis` | object | `{strong, partial, weak}` |

---

## Error Handling

| Code | Meaning | Recovery |
|------|---------|----------|
| `AUTH_REQUIRED` | LinkedIn session expired | `login()`, complete browser auth |
| `RATE_LIMITED` | LinkedIn block | Wait 10+ min, reduce `max_pages` |
| `SCRAPE_FAILED` | Network/parse error | Retry once, then `archive_jobs([id])` |
| `SERVER_ERROR` | Server down | `poetry run python -m server.app` |
| `NOT_FOUND` | ID doesn't exist | Check ID spelling |
| `VALIDATION_ERROR` | Bad params | Check function signature |

**Persistence:** `data/runtime/` (JSON files). Delete to reset.

---

## Functions

### Status & Auth

| Function | Returns |
|----------|---------|
| `status()` | `OK \| auth: yes \| user: <name>` or error |
| `login()` | Opens browser for LinkedIn auth |

### Search

| Function | Purpose |
|----------|---------|
| `search_jobs(query, location, sources, days, skip_filters)` | Search → filter → ingest |
| `scrape_top_picks(min_level, ai_only, exclude_existing)` | LinkedIn recommendations |

**Regions:** `eu_remote`, `prague`, `netherlands`, `germany`, `spain`, `france`, `italy`, `poland`

### Pipeline

| Function | Purpose |
|----------|---------|
| `pipeline()` | Full pipeline state: active/archived counts + each job's dive/app status |

### Jobs

| Function | Purpose |
|----------|---------|
| `get_jobs(ids, include_archived, full, limit, page)` | List with pagination |
| `get_job(job_id)` | Single job with `jd_text` |
| `ingest_jobs(jobs, dedupe_by)` | Add → `{added, skipped}` |
| `archive_jobs(job_ids)` | Soft delete |
| `unarchive_jobs(job_ids)` | Restore (refuses stale) |
| `reorder_jobs(job_ids)` | Set display order |

**Slim vs Full:** `get_jobs()` returns `has_jd` boolean. Use `full=True` or `get_job()` for actual JD text.

### JD Scraping

| Function | Purpose |
|----------|---------|
| `scrape_jd(job_id)` | Scrape single JD (auto-routes by prefix) |
| `scrape_jds(job_ids)` | Batch scrape (auto-routes by prefix) |

**Auto-routing:** `job_li_*` → LinkedIn, `job_cz_*` → jobs.cz, `job_sj_*` → startupjobs

### Selections

| Function | Purpose |
|----------|---------|
| `select_jobs(job_ids, source)` | Add to selection |
| `deselect_jobs(job_ids)` | Remove |
| `get_selections(source)` | `{claude: [...], user: [...]}` |

### Workflow

| Function | Purpose |
|----------|---------|
| `set_priority(job_id, priority)` | `high` / `medium` / `low` |
| `set_verdict(job_id, verdict)` | `Pursue` / `Maybe` / `Skip` |
| `move_to_stage(job_id, stage)` | `select` / `deep_dive` / `application` |

### Deep Dives

| Function | Purpose |
|----------|---------|
| `get_deep_dives(include_archived, full, limit, page)` | List with pagination |
| `get_deep_dive(job_id)` | Single with full research |
| `get_prior_company_research(company)` | Reuse existing findings |
| `post_deep_dive_simple(job_id, ...)` | Create (flat fields) |
| `archive_deep_dives(job_ids)` | Hide |

**post_deep_dive_simple fields:** `company_stage`, `company_product`, `role_scope`, `posting_analysis`, `fit_score`, `fit_explanation`, `attractions`, `concerns`, `verdict`, `next_steps`

### Applications

| Function | Purpose |
|----------|---------|
| `get_applications(include_archived, full, limit, page)` | List with pagination |
| `prepare_application(job_id)` | Create → `{application_id}` |
| `get_application(app_id)` | Single with CV/cover |
| `update_application_cv(app_id, md)` | Post CV markdown |
| `update_application_cover(app_id, md)` | Post cover letter |
| `update_application_gap_analysis(app_id, dict)` | Post analysis |
| `archive_applications(app_ids)` | Hide |

---

## Output Format

Default returns are terse pipe-delimited strings. Pass `full=True` for JSON.

| Function | Format |
|----------|--------|
| `pipeline()` | Line 1: `active:N\|archived:N\|dives:N\|apps:N` |
| | Lines 2+: `id\|company\|title\|verdict\|fit\|jd\|dive\|app` |
| `get_jobs()` | `id\|title\|company\|loc\|level\|ai\|jd\|verdict` |
| `get_deep_dives()` | `id\|company\|title\|status\|verdict\|fit` |
| `get_applications()` | `id\|company\|title\|status\|cv\|cl` |

**Pagination:** When `limit` is set, last line shows `--page=1/5` (current/total).
