#!/usr/bin/env python3
"""CLI for job_search. Usage: jbs <command> [args]"""

import sys
from job_search import tool


def _parse_flags(args: list[str], flags: dict[str, type]) -> tuple[dict, list[str]]:
    """Parse --flag=value args. Returns (parsed_flags, remaining_args)."""
    parsed = {}
    remaining = []
    for arg in args:
        if arg.startswith("--") and "=" in arg:
            key, val = arg.split("=", 1)
            key = key[2:]  # strip --
            if key in flags:
                parsed[key] = flags[key](val)
            else:
                remaining.append(arg)
        elif arg.startswith("--"):
            key = arg[2:]
            if key in flags and flags[key] is bool:
                parsed[key] = True
            else:
                remaining.append(arg)
        else:
            remaining.append(arg)
    return parsed, remaining


HELP = """Usage: jbs <command> [args]

Config:
  config                  Show project paths
  scraper list            List scrapers
  scraper show <name>     Show scraper config
  scraper create <name>   Create new scraper
  scraper set <n> <k> <v> Set config value
  scraper test <n> <q>    Test scraper

Profile:
  profile                 Show path and list files
  profile show <name>     Show profile contents

Status:
  status                  Server + auth check
  login                   LinkedIn auth
  pipeline [--all]        Overview (--all for full list)

Search:
  filter                  Show search filters
  filter set <k> <v>      Set filter (comma-sep for arrays)
  filter clear <k>        Remove filter
  filter reset            Clear all filters
  jobs <q> [loc]          Search and ingest
  picks [--level] [--ai]  LinkedIn recommendations

Jobs:
  list [--archived]       List jobs
  get <id>                Show job with JD
  scrape <id> [...]       Scrape JDs
  select <id> [...]       Mark jobs for review
  deselect <id> [...]     Unmark jobs
  sel                     Show selected jobs
  verdict <id> <v>        Set Pursue|Maybe|Skip
  dead <id> [...]         Mark jobs as expired/closed
  archive-listings <id>   Archive job listings
  unarchive-listings <id> Restore job listings

Deep Dives:
  dives [--archived]      List deep dives
  dive <id> [k=v...]      Post deep dive (--help for fields)
  archive-dive <id>       Archive dives (by job_id)
  unarchive-dive <id>     Restore dives

Applications:
  apps [--archived]       List applications
  apply <id>              Start application
  app update <id> --file  Update application
  archive-app <id>        Archive apps (by app_id)
  unarchive-app <id>      Restore apps

Bulk:
  clear-all               Archive all jobs, dives, apps
"""


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP.strip())
        return

    cmd = args[0]
    rest = args[1:]

    if cmd == "config":
        from pathlib import Path
        root = Path(__file__).parent.parent.parent.resolve()
        print(f"PROJECT_ROOT={root}")
        print(f"SCRAPERS_DIR={root / 'data' / 'scrapers'}")
        print(f"SCRIPTS_DIR={root / 'backend' / 'scripts'}")

    elif cmd == "scraper":
        from pathlib import Path
        import json as json_mod
        root = Path(__file__).parent.parent.parent.resolve()
        scrapers_dir = root / "data" / "scrapers"

        if not rest or rest[0] in ("--help", "-h"):
            print("Usage: jbs scraper <list|show|create|set|test> [args]")
            print("  list              List configured scrapers")
            print("  show <name>       Show scraper config as JSON")
            print("  create <name>     Create new scraper (--json '{...}' --force)")
            print("  set <n> <k> <v>   Set config value (dot notation)")
            print("  test <n> <query>  Test scraper with search query")
            return

        subcmd = rest[0]
        subrest = rest[1:]

        if subcmd == "list":
            if not scrapers_dir.exists():
                print("No scrapers configured yet.")
                return
            for f in sorted(scrapers_dir.glob("*.json")):
                name = f.stem
                try:
                    cfg = json_mod.loads(f.read_text())
                    engine = cfg.get("engine", "playwright")
                    print(f"  {name} ({engine})")
                except Exception:
                    print(f"  {name} (invalid)")

        elif subcmd == "show":
            if not subrest:
                print("Usage: jbs scraper show <name>")
                return
            name = subrest[0]
            cfg_path = scrapers_dir / f"{name}.json"
            if not cfg_path.exists():
                print(f"Scraper '{name}' not found")
                return
            print(cfg_path.read_text())

        elif subcmd == "create":
            if not subrest:
                print("Usage: jbs scraper create <name> [--json '{...}'] [--force]")
                return
            name = subrest[0]
            cfg_path = scrapers_dir / f"{name}.json"
            force = "--force" in subrest
            if cfg_path.exists() and not force:
                print(f"Scraper '{name}' already exists. Use --force to overwrite.")
                return
            scrapers_dir.mkdir(parents=True, exist_ok=True)

            # Check for --json flag
            json_config = None
            if "--json" in subrest:
                json_idx = subrest.index("--json")
                if json_idx + 1 < len(subrest):
                    try:
                        json_config = json_mod.loads(subrest[json_idx + 1])
                    except json_mod.JSONDecodeError as e:
                        print(f"Invalid JSON: {e}")
                        return

            if json_config:
                # Use provided config, add defaults for missing fields
                prefix = json_config.get("id_prefix", name[:2] + "_")
                config = {
                    "name": name,
                    "id_prefix": prefix,
                    "engine": "playwright",
                    "auth_required": False,
                    "delay_ms": 2000,
                    **json_config,
                    "name": name,  # Ensure name matches
                }
            else:
                # Create minimal empty config
                prefix = name[:2] + "_"
                config = {
                    "name": name,
                    "id_prefix": prefix,
                    "base_url": "",
                    "engine": "playwright",
                    "auth_required": False,
                    "delay_ms": 2000,
                    "search_url": {"pattern": ""},
                    "selectors": {"card": "", "title": "", "company": "", "location": ""},
                    "url_pattern": {"job_id_attr": "", "job_url_template": ""},
                    "pagination": {"type": "url_param", "param": "page"},
                    "jd": {"selectors": [], "use_jsonld": True, "wait_ms": 2000},
                    "when_to_use": "",
                }

            cfg_path.write_text(json_mod.dumps(config, indent=2))
            print(f"Created {name}")

        elif subcmd == "set":
            if len(subrest) < 3:
                print("Usage: jbs scraper set <name> <key> <value>")
                print("Examples:")
                print("  jbs scraper set indeed_nl base_url \"https://nl.indeed.com\"")
                print("  jbs scraper set indeed_nl selectors.card \".jobCard\"")
                print("  jbs scraper set indeed_nl jd.selectors \"#desc,.details\"  # comma-sep for arrays")
                return
            name, key, value = subrest[0], subrest[1], subrest[2]
            cfg_path = scrapers_dir / f"{name}.json"
            if not cfg_path.exists():
                print(f"Scraper '{name}' not found. Create it first: jbs scraper create {name}")
                return
            config = json_mod.loads(cfg_path.read_text())
            # Handle dot notation
            parts = key.split(".")
            obj = config
            for part in parts[:-1]:
                if part not in obj:
                    obj[part] = {}
                obj = obj[part]

            # Known array fields - accept comma-separated values
            array_fields = {"jd.selectors"}
            current_val = obj.get(parts[-1])

            if key in array_fields or isinstance(current_val, list):
                # Convert comma-separated string to array (unless already JSON array)
                if value.startswith("["):
                    try:
                        obj[parts[-1]] = json_mod.loads(value)
                    except json_mod.JSONDecodeError:
                        obj[parts[-1]] = [v.strip() for v in value.split(",") if v.strip()]
                else:
                    obj[parts[-1]] = [v.strip() for v in value.split(",") if v.strip()]
            else:
                # Try to parse value as JSON, otherwise use string
                try:
                    parsed = json_mod.loads(value)
                    obj[parts[-1]] = parsed
                except json_mod.JSONDecodeError:
                    obj[parts[-1]] = value

            cfg_path.write_text(json_mod.dumps(config, indent=2))
            print(f"Set {key} = {obj[parts[-1]]}")

        elif subcmd == "test":
            if len(subrest) < 2:
                print("Usage: jbs scraper test <name> <query>")
                return
            name, query = subrest[0], " ".join(subrest[1:])

            # Check if config specifies python engine
            cfg_path = scrapers_dir / f"{name}.json"
            use_python = False
            if cfg_path.exists():
                try:
                    config = json_mod.loads(cfg_path.read_text())
                    use_python = config.get("engine") == "python"
                except (json_mod.JSONDecodeError, IOError):
                    pass

            if use_python:
                # Python engine scrapers
                builtin = {
                    "startupjobs": lambda: __import__("scripts.startupjobs_search", fromlist=["search_startupjobs"]).search_startupjobs(query),
                    "jobscz": lambda: __import__("scripts.jobscz_search", fromlist=["search_jobscz"]).search_jobscz(query),
                }
                if name in builtin:
                    result = builtin[name]()
                else:
                    print(f"Error: No Python handler for {name}")
                    return
            else:
                from scripts.generic_search import search_generic
                result = search_generic(name, query, max_pages=1, collect_diagnostics=True)
            diag = result.get("diagnostics", {})

            if result.get("status") == "ok":
                job_count = result['job_count']
                # Terse one-line output
                parts = [f"jobs={job_count}"]
                if diag:
                    card_count = diag.get("selector_matches", {}).get("card", "?")
                    parts.append(f"card={card_count}")
                    title = diag.get("page_title", "")[:30]
                    if title:
                        parts.append(f'page="{title}"')
                print(f"{name}: {' | '.join(parts)}")

                # Show sample jobs if found
                if job_count > 0:
                    for job in result.get("jobs", [])[:3]:
                        print(f"  {job['title'][:40]} @ {job.get('company', '?')[:20]}")
                    if job_count > 3:
                        print(f"  ... +{job_count - 3} more")

                # Expand diagnostics only on failure
                if job_count == 0 and diag:
                    print("---")
                    print(f"Page: {diag.get('page_title', 'N/A')}")
                    print("Selectors:")
                    for sel, count in diag.get("selector_matches", {}).items():
                        print(f"  {sel}: {count}")
                    title = (diag.get("page_title") or "").lower()
                    if "block" in title or "captcha" in title:
                        print("Hint: Bot blocking detected")
            else:
                print(f"Error: {result.get('error')}")

        elif subcmd == "test-jd":
            if len(subrest) < 2:
                print("Usage: jbs scraper test-jd <name> <job_id>")
                return
            name, job_id = subrest[0], subrest[1]
            from scripts.generic_jd import scrape_jd_generic
            result = scrape_jd_generic(name, job_id, collect_diagnostics=True)
            diag = result.get("diagnostics", {})

            if result.get("status") == "ok":
                jd_len = len(result.get("jd_text", ""))
                source = diag.get("source", "unknown")
                print(f"{name}: ok | chars={jd_len} | source={source}")
                # Show JD preview
                jd_preview = result.get("jd_text", "")[:200].replace("\n", " ")
                print(f"  {jd_preview}...")
            else:
                print(f"{name}: {result.get('code', 'ERROR')} | {result.get('error')}")
                if diag:
                    print(f"  url: {diag.get('url', 'N/A')}")
                    print(f"  page: {diag.get('page_title', 'N/A')}")
                    if diag.get("selectors_tried"):
                        print(f"  selectors tried: {', '.join(diag['selectors_tried'])}")

        else:
            print(f"Unknown scraper command: {subcmd}")

    elif cmd == "status":
        print(tool.status())

    elif cmd == "login":
        print(tool.login())

    elif cmd == "jobs":
        if not rest or rest[0] in ("--help", "-h"):
            print("Usage: jbs jobs <query> [location] [--sources=X,Y]")
            print("  Search for jobs. LinkedIn always included.")
            print("  --sources=X,Y  Additional sources (indeed_nl,jobscz,...)")
            return
        # Parse --sources flag
        sources = ["linkedin"]  # Always include linkedin
        filtered_rest = []
        for arg in rest:
            if arg.startswith("--sources="):
                for s in arg.split("=")[1].split(","):
                    if s and s not in sources:
                        sources.append(s)
            elif arg.startswith("--board="):  # Legacy alias
                s = arg.split("=")[1]
                if s and s not in sources:
                    sources.append(s)
            else:
                filtered_rest.append(arg)
        query = filtered_rest[0] if filtered_rest else ""
        location = filtered_rest[1] if len(filtered_rest) > 1 else None
        print(tool.search_jobs(query=query, location=location, sources=sources))

    elif cmd == "picks":
        level = "senior"
        ai_only = False
        for arg in rest:
            if arg.startswith("--level="):
                level = arg.split("=")[1]
            elif arg == "--ai":
                ai_only = True
        print(tool.scrape_top_picks(min_level=level, ai_only=ai_only))

    elif cmd == "scrape":
        if not rest:
            print("Usage: jbs scrape <job_id> [job_id...]")
            return
        if len(rest) == 1:
            print(tool.scrape_jd(rest[0]))
        else:
            print(tool.scrape_jds(rest))

    elif cmd == "get":
        if not rest:
            print("Usage: jbs get <job_id>")
            return
        result = tool.get_job(rest[0])
        job = result.get("job", result) if isinstance(result, dict) else result
        if isinstance(job, dict) and job.get("jd_text"):
            print(f"# {job.get('title')} @ {job.get('company')}\n")
            print(job.get("jd_text"))
        else:
            print(f"No JD for {rest[0]}")

    elif cmd == "list":
        flags, rest = _parse_flags(rest, {"archived": bool, "limit": int, "page": int})
        include_archived = flags.get("archived", False)
        limit = flags.get("limit", 20 if include_archived else None)
        page = flags.get("page", 1)
        print(tool.get_jobs(include_archived=include_archived, limit=limit, page=page))

    elif cmd in ("sel", "selections"):
        print(tool.get_selections())

    elif cmd == "archive-listings":
        if not rest:
            print("Usage: jbs archive-listings <job_id> [job_id...]")
            return
        print(tool.archive_jobs(rest))

    elif cmd == "archive-dive":
        if not rest:
            print("Usage: jbs archive-dive <job_id> [job_id...]")
            return
        print(tool.archive_deep_dives(rest))

    elif cmd == "archive-app":
        if not rest:
            print("Usage: jbs archive-app <app_id> [app_id...]")
            return
        print(tool.archive_applications(rest))

    elif cmd == "unarchive-listings":
        if not rest:
            print("Usage: jbs unarchive-listings <job_id> [job_id...]")
            return
        print(tool.unarchive_jobs(rest))

    elif cmd == "unarchive-dive":
        if not rest:
            print("Usage: jbs unarchive-dive <job_id> [job_id...]")
            return
        print(tool.unarchive_deep_dives(rest))

    elif cmd == "unarchive-app":
        if not rest:
            print("Usage: jbs unarchive-app <app_id> [app_id...]")
            return
        print(tool.unarchive_applications(rest))

    elif cmd == "select":
        if not rest:
            print("Usage: jbs select <job_id> [job_id...] | --all")
            return
        if rest[0] == "--all":
            # Get all active (non-archived) job IDs
            jobs = tool.get_jobs(full=True)
            if jobs.get("status") == "ok":
                job_ids = [j["job_id"] for j in jobs.get("jobs", []) if not j.get("archived")]
                if job_ids:
                    print(tool.select_jobs(job_ids))
                else:
                    print("No active jobs to select")
            else:
                print("Failed to get jobs")
        else:
            print(tool.select_jobs(rest))

    elif cmd == "deselect":
        if not rest:
            print("Usage: jbs deselect <job_id> [job_id...] | --all")
            return
        if rest[0] == "--all":
            # Deselect all currently selected jobs
            sel = tool.get_selections(full=True)
            job_ids = sel.get("claude", []) + sel.get("user", [])
            if job_ids:
                print(tool.deselect_jobs(job_ids))
            else:
                print("No jobs selected")
        else:
            print(tool.deselect_jobs(rest))

    elif cmd == "verdict":
        if len(rest) < 2:
            print("Usage: jbs verdict <job_id> <Pursue|Maybe|Skip>")
            return
        print(tool.set_verdict(rest[0], rest[1]))

    elif cmd == "dead":
        if not rest:
            print("Usage: jbs dead <job_id> [job_id...]")
            return
        print(tool.mark_dead(rest))

    elif cmd == "dive":
        # Alias: jbs dive list -> jbs dives
        if rest and rest[0] == "list":
            flags, _ = _parse_flags(rest[1:], {"archived": bool, "limit": int, "page": int})
            print(tool.get_deep_dives(
                include_archived=flags.get("archived", False),
                limit=flags.get("limit"),
                page=flags.get("page", 1),
            ))
            return
        if not rest or rest[0] in ("-h", "--help", "help"):
            print("""Usage: jbs dive <job_id> [key=value...]

Fields (all optional, use key=value syntax):

Company Research:
  company_stage     Stage + funding + revenue with citation
  company_product   What they sell + who buys it
  company_size      Headcount with source

Sentiment Research:
  employee_sentiment  Glassdoor/Blind rating + patterns with links
  customer_sentiment  G2/TrustRadius rating + product feedback

Role Research:
  role_scope        What you own, who you report to
  role_team         Team structure if mentioned

Context Research:
  market_context    Competitors, market position, recent news
  interview_process Glassdoor interview reviews, round count
  remote_reality    Actual remote policy, timezone expectations

Analysis:
  posting_analysis  JD language analysis: count "ship" vs "governance"
  fit_explanation   Connect to user's profile stories

Conclusions:
  fit_score         1-10 based on level/AI/location/company/clarity
  attractions       Comma-separated positives
  concerns          Comma-separated gaps or risks
  verdict           Pursue|Maybe|Skip
  next_steps        Comma-separated actions

Example:
  jbs dive li_123 company_stage="Series C" fit_score=8 verdict=Pursue

For complex values with quotes/links, use JSON file:
  jbs dive li_123 --file /tmp/dive.json""")
            return
        if rest[0].startswith("-") and rest[0] not in ("--file",):
            print("Usage: jbs dive <job_id> [key=value...] [--file path.json]")
            return
        job_id = rest[0]
        kwargs = {}
        # Check for --file flag
        file_path = None
        remaining = []
        i = 1
        while i < len(rest):
            if rest[i] == "--file" and i + 1 < len(rest):
                file_path = rest[i + 1]
                i += 2
            elif rest[i].startswith("--file="):
                file_path = rest[i].split("=", 1)[1]
                i += 1
            else:
                remaining.append(rest[i])
                i += 1
        # Load from JSON file if provided
        if file_path:
            import json
            with open(file_path) as f:
                kwargs = json.load(f)
        # Parse key=value args (can override file values)
        for arg in remaining:
            if "=" in arg:
                k, v = arg.split("=", 1)
                kwargs[k] = v
        print(tool.post_deep_dive_simple(job_id, **kwargs))

    elif cmd == "dives":
        flags, _ = _parse_flags(rest, {"archived": bool, "limit": int, "page": int})
        print(tool.get_deep_dives(
            include_archived=flags.get("archived", False),
            limit=flags.get("limit"),
            page=flags.get("page", 1),
        ))

    elif cmd == "apply":
        if not rest:
            print("Usage: jbs apply <job_id>")
            return
        print(tool.prepare_application(rest[0]))

    elif cmd == "app":
        # Alias: jbs app list -> jbs apps
        if rest and rest[0] == "list":
            flags, _ = _parse_flags(rest[1:], {"archived": bool, "limit": int, "page": int})
            print(tool.get_applications(
                include_archived=flags.get("archived", False),
                limit=flags.get("limit"),
                page=flags.get("page", 1),
            ))
            return
        # jbs app update <app_id> --file path.json
        if rest and rest[0] == "update":
            if len(rest) < 2 or rest[1] in ("-h", "--help", "help"):
                print("""Usage: jbs app update <app_id> --file path.json

Fields (provide via JSON file):

CV & Cover Letter:
  cv_tailored       Tailored CV content (markdown string)
  cover_letter      Cover letter content (markdown string)

Analysis:
  gap_analysis      {matches: [...], partial_matches: [...], gaps: [...], missing_stories: [...]}

Interview Prep:
  interview_prep    {what_to_say: [...], what_not_to_say: [...], questions_to_ask: [...], red_flags: [...]}

Research:
  salary_research   {range: "€X-Y", glassdoor: "...", anchoring_strategy: "..."}
  referral_search   {contacts: [...], channel_priority: [...]}
  follow_up         {milestones: [...], backup_contacts: [...]}

Status:
  status            pending|in_progress|ready|submitted|rejected|accepted

Example JSON:
{
  "cv_tailored": "# [Your Name]\\n\\n## Summary\\n...",
  "cover_letter": "Dear Hiring Manager,\\n\\n...",
  "gap_analysis": {
    "matches": ["AI product experience", "Enterprise scale"],
    "gaps": ["Legal domain knowledge"],
    "missing_stories": ["Ask about compliance experience"]
  },
  "interview_prep": {
    "what_to_say": [{"question": "Tell me about yourself", "answer": "..."}],
    "questions_to_ask": ["What does success look like in 6 months?"]
  }
}""")
                return
            app_id = rest[1]
            # Find --file flag
            file_path = None
            for i, arg in enumerate(rest[2:], start=2):
                if arg == "--file" and i + 1 < len(rest):
                    file_path = rest[i + 1]
                    break
                elif arg.startswith("--file="):
                    file_path = arg.split("=", 1)[1]
                    break
            if not file_path:
                print("Usage: jbs app update <app_id> --file path.json")
                return
            import json
            with open(file_path) as f:
                kwargs = json.load(f)
            print(tool.update_application(app_id, **kwargs))
            return
        print("Usage: jbs app <list|update> [args]")

    elif cmd == "apps":
        flags, _ = _parse_flags(rest, {"archived": bool, "limit": int, "page": int})
        print(tool.get_applications(
            include_archived=flags.get("archived", False),
            limit=flags.get("limit"),
            page=flags.get("page", 1),
        ))

    elif cmd == "pipeline":
        flags, _ = _parse_flags(rest, {"all": bool})
        print(tool.pipeline(full=flags.get("all", False)))

    elif cmd == "sources":
        from pathlib import Path
        import json as json_mod
        root = Path(__file__).parent.parent.parent.resolve()
        scrapers_dir = root / "data" / "scrapers"
        if not scrapers_dir.exists():
            print("No sources configured.")
            return
        print("Available sources (always include linkedin):")
        print()
        for cfg_file in sorted(scrapers_dir.glob("*.json")):
            try:
                cfg = json_mod.loads(cfg_file.read_text())
                name = cfg.get("name", cfg_file.stem)
                when = cfg.get("when_to_use", "No description")
                print(f"  {name}: {when}")
            except (json_mod.JSONDecodeError, IOError):
                pass

    elif cmd == "filter":
        if not rest:
            print(tool.get_filters())
        elif rest[0] == "set" and len(rest) >= 3:
            print(tool.set_filter(rest[1], rest[2]))
        elif rest[0] == "clear" and len(rest) >= 2:
            print(tool.clear_filter(rest[1]))
        elif rest[0] == "reset":
            print(tool.reset_filters())
        else:
            print("Usage: jbs filter [set <key> <value> | clear <key> | reset]")

    elif cmd == "profile":
        from pathlib import Path
        profile_dir = Path(__file__).parent.parent.parent / "data" / "profile"
        profile_files = {
            "anti-positioning": "anti-positioning.md",
            "base": "base.md",
            "star-bank": "star-bank.md",
            "search-preferences": "search-preferences.md",
            "writing-style": "writing-style.md",
        }
        if not rest:
            # List available profile files
            print(f"path: {profile_dir.resolve()}")
            for name, filename in profile_files.items():
                path = profile_dir / filename
                status = "✓" if path.exists() else "✗"
                print(f"  {name}: {status}")
        elif rest[0] == "show" and len(rest) >= 2:
            name = rest[1]
            if name not in profile_files:
                print(f"Unknown profile: {name}")
                print(f"Available: {', '.join(profile_files.keys())}")
            else:
                path = profile_dir / profile_files[name]
                if not path.exists():
                    print(f"Profile file not found: {name}")
                    print(f"Create it at: {path}")
                else:
                    print(path.read_text())
        else:
            print("Usage: jbs profile [show <name>]")
            print("       jbs profile          Show path and list files")
            print("       jbs profile show X   Show contents of profile X")

    elif cmd == "clear-all":
        print(tool.clear_all())

    else:
        print(f"Unknown command: {cmd}\n")
        print(HELP.strip())


if __name__ == "__main__":
    main()
