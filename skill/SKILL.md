---
name: job-search
description: Job search assistant with web UI at localhost:8000. Triggers on "search jobs", "find PM roles", "top picks", "scrape JD", "deep dive", "reorder jobs", "prepare application". All data flows to UI — never output job lists in chat.
---

# Execution

Run ALL commands via Desktop Commander:

```
mcp__desktop-commander__start_process
  command: "jbs <command>"
  timeout_ms: 60000
```

**This is the ONLY way to interact with the job search system.**

File reads: `mcp__desktop-commander__read_file` with absolute path to the project directory.

# Constraints

- **No Python calls** - Use `jbs` CLI only.
- **No direct HTTP** - Don't call localhost:8000 directly. Use `jbs` CLI only.
- **No invented tools** - If a tool doesn't exist, don't call it. Use `jbs --help` to see available commands.
- **Browser MCP required for research** - Deep dives and application prep require online research (Glassdoor, LinkedIn, company sites). Use Browser MCP for all web lookups. If Browser MCP is unavailable, stop research and ask user to reconnect.

# Startup

Before first search, verify profile files exist in `data/profile/`. If missing, ask user and create them.

## Filters (required for search)

Run `jbs filter` to see current settings. Update with:
- `jbs filter set <key> <value>` — set param (comma-separated for arrays)
- `jbs filter clear <key>` — remove param
- `jbs filter reset` — clear all

| Key | Effect |
|-----|--------|
| `title_must_contain` | Job title must include at least one term |
| `include_locations` | Location must match at least one term |
| `exclude_levels` | Skip jobs with these levels |
| `exclude_companies` | Skip these companies |

## anti-positioning.md (required for qualifying)

**Ask:** What red flags should disqualify a job? What signals indicate bad fit? Topics to avoid discussing?

```markdown
# Anti-Positioning
## Red Flags in Job Descriptions
## Red Flags in Titles
## Topics to Avoid
```

## base.md (required for applications)

**Ask:** Current CV content? Key achievements? Contact info?

```markdown
# Profile
## Summary
## Experience
## Skills
## Contact
```

## star-bank.md (required for interview prep)

**Ask:** Key accomplishments with metrics? STAR stories for common questions?

```markdown
# STAR Bank
## Achievement 1
- Situation:
- Task:
- Action:
- Result:
```

# Workflow

| Step | Command | Returns |
|------|---------|---------|
| 0. Overview | `jbs pipeline` | Full state: jobs, dives, apps |
| 1. Check | `jbs status` | `OK \| auth: yes \| user: <name>` |
| 2. Selections | `jbs sel` | Jobs user selected in UI — work on THESE |
| 3. Search | `jbs jobs "query" location` | `Added N` |
| 4. Filter | `jbs list`, then `jbs archive` non-fits | Archive count |
| 5. Scrape | `jbs scrape job_id [...]` | `Scraped N JDs` |
| 6. Qualify | `jbs get job_id`, archive non-fits | JD text |
| 7. Research | `jbs dive job_id key=value...` | Posted |
| 8. Apply | `jbs apply job_id` | `app_id` |

**Step 4 is mandatory.** Review `jbs list` against `jbs filter`. Archive jobs that fail hard filters (wrong location, wrong level, excluded companies) BEFORE scraping.

**If `auth: no`**: `jbs login`. **If connection refused**: `poetry run python -m server.app`

# Profile Files

| File | Read before |
|------|-------------|
| `data/profile/anti-positioning.md` | Qualifying (red flags, signals) |
| `data/profile/base.md` | CV, cover letter |
| `data/profile/star-bank.md` | Interview prep |

# Standards

These reference files are bundled inside this skill. Read them from the skill's `references/` folder.

| Reference | Read when |
|-----------|-----------|
| `references/deep-dive.md` (in this skill) | Before Step 6-7 (qualifying + research). Has qualification gate, research questions, **all `jbs dive` fields with examples**, verdict guidelines. |
| `references/application.md` (in this skill) | Before Step 8 (apply). Has gap analysis, CV tailoring, cover letter, salary research, interview prep, referral search, follow-up plan. |

# Rules

1. **NEVER output job data in chat.** User sees everything at localhost:8000. Don't list jobs, don't summarize JDs, don't repeat what the CLI returned. Just confirm the action: "Scraped 3 JDs" or "Posted deep dive for Acme Corp". The web UI is the interface—chat is just for commands.
2. **Filter before scraping.** Hard filters from `jbs filter` are auto-applied during search. Archive remaining non-fits.
3. **Scrape JD before qualifying.** No speculation from titles.
4. **One action, confirm, next.** Don't batch silently. Don't narrate.

# Troubleshooting

| Error | Fix |
|-------|-----|
| `AUTH_FAILED: ProcessSingleton` / browser profile locked | Run `pkill -f "Google Chrome for Testing"` then retry |
| `Connection refused` | Start server: `poetry run python -m server.app` |
| `auth: no` | Run `jbs login` to authenticate with LinkedIn |
| Browser MCP unavailable / web lookup fails | Stop research. Tell user: "Browser MCP is disconnected. Please reconnect it so I can continue research." |

# Commands

| Command | Purpose |
|---------|---------|
| `jbs --help` | Show all commands |
| `jbs status` | Server + auth check |
| `jbs login` | Open browser for LinkedIn auth |
| `jbs pipeline [--all]` | Summary + active jobs; `--all` for full list |
| `jbs filter` | Show current search filters |
| `jbs filter set <k> <v>` | Set filter (comma-sep for arrays) |
| `jbs filter clear <k>` | Remove filter |
| `jbs filter reset` | Clear all filters |
| `jbs jobs <query> [location]` | Search, filter, auto-ingest |
| `jbs picks [--level=X] [--ai]` | LinkedIn recommendations |
| `jbs scrape <id> [id...]` | Scrape JDs |
| `jbs get <id>` | Single job with JD text |
| `jbs list [--archived] [--limit=N] [--page=N]` | List jobs (default limit 20 for archived) |
| `jbs sel` | Show user-selected jobs (what to work on next) |
| `jbs select <id> [id...]` | Mark jobs for review |
| `jbs deselect <id> [id...]` | Unmark jobs |
| `jbs verdict <id> <Pursue\|Maybe\|Skip>` | Set verdict |
| `jbs dead <id> [id...]` | Mark jobs as expired/closed |
| `jbs archive-listings <id> [id...]` | Archive job listings |
| `jbs unarchive-listings <id> [id...]` | Unarchive job listings |
| `jbs dives [--archived]` | List deep dives |
| `jbs dive <id> [--file path.json]` | Post deep dive (use JSON for complex values) |
| `jbs archive-dive <id> [id...]` | Archive deep dives (by job_id) |
| `jbs unarchive-dive <id> [id...]` | Unarchive deep dives (by job_id) |
| `jbs apps [--archived]` | List applications |
| `jbs apply <id>` | Prepare application |
| `jbs app update <id> --file path.json` | Update application (CV, cover letter, prep) |
| `jbs archive-app <id> [id...]` | Archive applications (by app_id) |
| `jbs unarchive-app <id> [id...]` | Unarchive applications (by app_id) |
| `jbs clear-all` | Archive all jobs, dives, and apps |

**Aliases:** `jbs dive list` → `jbs dives`, `jbs app list` → `jbs apps`, `jbs selections` → `jbs sel`

# Output Format

Commands return terse pipe-delimited strings. Examples:

| Command | Output |
|---------|--------|
| `jbs pipeline` | Summary + jobs with activity only (see below) |
| `jbs pipeline --all` | Summary + all jobs grouped by stage |
| `jbs list` | `id\|title\|company\|loc\|level\|ai\|jd\|verdict` per job |
| `jbs dives` | `id\|company\|title\|status\|verdict\|fit` per dive |
| `jbs apps` | `id\|company\|title\|status\|cv\|cl` per app |

**Pipeline output:**
```
active:99|archived:3|inbox:45|scraped:42|researched:6|applying:2
verdicts: pursue=4 maybe=1 skip=1
--- Applying (2) ---
li_123|Company|Title|pursu|9|jd|dive|app
--- Researched (4) ---
li_456|Company|Title|maybe|6|jd|dive|-
```

Stage meanings: `inbox` (no JD), `scraped` (JD, no dive), `researched` (dive), `applying` (app).

**Pagination:** `--page=1/5` as last line when paginated.

**ID prefixes:** `li_` (LinkedIn), `cz_` (jobs.cz), `sj_` (startupjobs), `er_` (euremotejobs).
