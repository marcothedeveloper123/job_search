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

    if cmd == "status":
        print(tool.status())

    elif cmd == "login":
        print(tool.login())

    elif cmd == "jobs":
        if not rest:
            print("Usage: jbs jobs <query> [location]")
            return
        query = rest[0]
        location = rest[1] if len(rest) > 1 else "eu_remote"
        print(tool.search_jobs(query=query, location=location))

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
            print("Usage: jbs select <job_id> [job_id...]")
            return
        print(tool.select_jobs(rest))

    elif cmd == "deselect":
        if not rest:
            print("Usage: jbs deselect <job_id> [job_id...]")
            return
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

    elif cmd == "clear-all":
        print(tool.clear_all())

    else:
        print(f"Unknown command: {cmd}\n")
        print(HELP.strip())


if __name__ == "__main__":
    main()
