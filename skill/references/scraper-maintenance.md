# Scraper Maintenance & New Job Boards

All scraper configuration is done via CLI. Never edit files directly.

## CLI Commands

```bash
# Configure
jbs scraper list                       # List existing scrapers
jbs scraper show <name>                # Show scraper config
jbs scraper create <name>              # Create empty scraper (search + JD config)
jbs scraper create <n> --json '{...}'  # Create with full config
jbs scraper create <n> --json '{...}' --force  # Overwrite existing
jbs scraper set <n> <k> <v>            # Set config value (dot notation)
jbs scraper test <n> <query>           # Test search scraper
jbs scraper test-jd <n> <job_id>       # Test JD scraper

# Use
jbs jobs "query" --sources=<name>      # Search and ingest jobs
jbs scrape <job_id>                    # Scrape JD (auto-routes by prefix)
```

---

## Adding a New Job Board

Use an **iterative test loop**: configure a few fields, test, read diagnostics, adjust, repeat.

### 1. Create and Test Minimal Config

```bash
jbs scraper create myboard
jbs scraper set myboard base_url "https://jobs.example.com"
jbs scraper set myboard search_url.pattern "https://jobs.example.com/search?q={query}&loc={location}"

# TEST EARLY - check if page loads
jbs scraper test myboard "product manager"
```

**Read the diagnostics:**
```
page="Blocked"           ← Bot blocking! Need stealth or different approach.
page="100+ jobs..."      ← Good, page loaded.
```

### 2. Add Selectors, Test Each

Use Playwright MCP to find selectors on the live site, then test after each one:

```bash
jbs scraper set myboard selectors.card ".job-listing"
jbs scraper test myboard "product manager"
# Check: card=16 (ok) or card=0 (wrong selector)?

jbs scraper set myboard selectors.title ".job-title a"
jbs scraper test myboard "product manager"
# Check: jobs=16 now?
```

### 3. Add Job ID Extraction

```bash
# Option A: From data attribute (preferred)
jbs scraper set myboard url_pattern.job_id_attr "data-job-id"

# Option B: From URL regex
jbs scraper set myboard url_pattern.job_id_regex "/job/([0-9]+)"

jbs scraper set myboard url_pattern.job_url_template "https://jobs.example.com/job/{id}"
# Or if site uses slugs: "https://jobs.example.com/job/{id}/{slug}"

jbs scraper test myboard "product manager"
# Check: jobs=N (should show actual jobs now)
```

### 4. Add Optional Fields

```bash
jbs scraper set myboard selectors.company ".company-name"
jbs scraper set myboard selectors.location ".job-location"
jbs scraper set myboard pagination.type "url_param"
jbs scraper set myboard pagination.param "page"
jbs scraper set myboard pagination.increment 1
```

### Reading Test Output

**Success** (terse one-liner):
```
myboard: jobs=16 | card=16 | page="100+ jobs for..."
```

**Failure** (expands to show diagnostics):
```
myboard: jobs=0 | card=0 | page="100+ jobs for..."
---
Page: 100+ jobs for Product Manager
Selectors:
  card: 0
  title: 16
```

**Hints:**
- `page="Blocked"` → Site blocking headless browser
- `card=0` → Wrong card selector, inspect DOM again
- `jobs=0` but `card=16` → Check job ID extraction

### Bulk Config (Alternative)

If you know the full config upfront, create in one command:

```bash
jbs scraper create myboard --json '{
  "base_url": "https://jobs.example.com",
  "search_url": {"pattern": "https://jobs.example.com/search?q={query}&loc={location}"},
  "selectors": {"card": ".job-listing", "title": ".job-title a"},
  "url_pattern": {"job_id_attr": "data-job-id", "job_url_template": "https://jobs.example.com/job/{id}"},
  "cookie_dismiss": "#cookie-accept-btn"
}'
```

Use `--force` to overwrite an existing scraper.

### 5. Configure JD Scraping

After search works, configure JD (job description) scraping for detail pages:

```bash
# Set selectors for job description text (comma-separated, tries in order)
jbs scraper set myboard jd.selectors "#job-description,.job-details,article"

# Optional: disable JSON-LD extraction (enabled by default)
jbs scraper set myboard jd.use_jsonld false

# Optional: adjust wait time (default 2000ms)
jbs scraper set myboard jd.wait_ms 3000

# Test with a job ID from your search results
jbs scraper test-jd myboard abc123
```

**JD Test Output:**
```
myboard: ok | chars=5234 | source=selector:#job-description
  First 200 chars of job description preview...
```

**If JD scraping fails:**
- `source=jsonld` → JSON-LD worked (preferred)
- `source=selector:X` → CSS selector X worked
- `JD_NOT_FOUND` → Try different selectors
- `BOT_BLOCKED` → Site blocking, may need different approach

### 6. Set when_to_use (Required)

After creating a scraper, set `when_to_use` so the AI knows when to include it:

```bash
jbs scraper set myboard when_to_use "Jobs in Germany, Berlin-based tech companies."
```

Ask the user if unclear: "When should I search this board? (e.g., specific country, industry, job type)"

---

## Fixing Broken Scrapers

All scrapers are config-driven. **Config supersedes hardcoded values.** Fix via CLI, never edit code.

### Broken Search (0 jobs returned)

```bash
# 1. Diagnose
jbs scraper test myboard "product manager"
# jobs=0 means selectors or URL pattern broken

# 2. Inspect new DOM with Playwright MCP, then update config
jbs scraper set myboard selectors.card ".NEW_CARD_SELECTOR"
jbs scraper set myboard selectors.title ".NEW_TITLE_SELECTOR"

# 3. Verify
jbs scraper test myboard "product manager"
```

### Broken JD URLs (404 errors on scrape)

Job detail page URLs often change format. Fix via `url_pattern.job_url_template`:

```bash
# 1. Diagnose - scrape returns 404
jbs scrape sj_12345
# ERROR: 404 Not Found

# 2. Find new URL format
# Use Playwright MCP to navigate to a job and check the URL pattern
# Example: site changed from /job/{id} to /job/{id}/{slug}

# 3. Update URL template (supports {id} and {slug} placeholders)
jbs scraper set myboard url_pattern.job_url_template "https://site.com/job/{id}/{slug}"

# 4. Re-run search to update stored URLs for existing jobs
jbs jobs "query" --sources=myboard
# URLs auto-update for duplicate jobs

# 5. Verify JD scraping works
jbs scrape sj_12345
```

**URL template placeholders:**
- `{id}` - Job ID (always available)
- `{slug}` - URL slug from API (if provided by job board)

### Broken JD Selectors (JD_NOT_FOUND errors)

```bash
# 1. Diagnose
jbs scraper test-jd myboard job_12345
# JD_NOT_FOUND = selectors don't match

# 2. Inspect job detail page with Playwright MCP, find new selectors
jbs scraper set myboard jd.selectors ".new-description,article,.job-content"

# 3. Verify
jbs scraper test-jd myboard job_12345
```

---

## Config Reference

### Engine Types

| Engine | Use When |
|--------|----------|
| `playwright` | JS-heavy sites (default) |
| `beautifulsoup` | Simple HTML, faster |
| `api` | JSON API endpoints |

```bash
jbs scraper set myboard engine "beautifulsoup"
```

### Cookie Consent

Many sites show cookie banners that block content. Dismiss them:

```bash
jbs scraper set myboard cookie_dismiss "#onetrust-accept-btn-handler"
```

The selector should match the "Accept" or "Reject All" button.

### Pagination Types

| Type | Config | Behavior |
|------|--------|----------|
| `button` | `pagination.selector "button.next"` | Click next button |
| `load_more` | `pagination.selector "button.load-more"` | Click load more |
| `scroll` | `pagination.type "scroll"` | Scroll to load |
| `url_param` | `pagination.param "page"` | Increment `?page=N` |

### Selectors

Required selectors:
- `selectors.card` - Job listing container
- `selectors.title` - Title link

Optional selectors:
- `selectors.company`
- `selectors.location`
- `selectors.posted`
- `selectors.salary`

### Job ID Extraction

Choose ONE method:

| Method | Config | Use When |
|--------|--------|----------|
| Data attribute | `url_pattern.job_id_attr "data-jk"` | Job ID in element attribute (preferred) |
| URL regex | `url_pattern.job_id_regex "jk=([a-f0-9]+)"` | Job ID in URL |

Also set: `url_pattern.job_url_template "https://site.com/job?id={id}"`

### Custom Extraction JS

For complex sites, provide custom JS:

```bash
jbs scraper set myboard extraction_js "() => { const jobs = []; /* logic */ return jobs; }"
```

The JS must return array of: `{job_id, title, company, location, url}`

### JD Scraping Config

| Field | Default | Purpose |
|-------|---------|---------|
| `jd.selectors` | `[]` | CSS selectors for JD text (comma-separated, tries in order) |
| `jd.use_jsonld` | `true` | Try JSON-LD extraction first |
| `jd.wait_ms` | `2000` | Wait after page load before extracting |

**JSON-LD** is structured data many sites include for SEO. When `use_jsonld=true`, the scraper first looks for `<script type="application/ld+json">` with `@type: JobPosting` and extracts the `description` field. Falls back to CSS selectors if not found.

---

## Existing Scrapers

| Name | Engine | ID Prefix |
|------|--------|-----------|
| linkedin | playwright | li_ |
| jobscz | beautifulsoup | cz_ |
| startupjobs | python | sj_ |
| euremotejobs | playwright | er_ |
| indeed_nl | playwright | in_ |

View any config: `jbs scraper show <name>`
