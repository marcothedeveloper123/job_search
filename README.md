# Job Search Assistant

Turn Claude Desktop into your job search consultant. Tell Claude what you're looking for, and it searches job boards, filters against your criteria, researches companies, and curates opportunities worth your time. A companion web UI lets you review Claude's selections and track your pipeline.

![Job Search Assistant](docs/screenshot.png)

> **Note:** This skill works best with **Claude Opus 4.5**, which has the strongest understanding of how to apply skills effectively.

## Features

- **Multi-board Search**: LinkedIn, Jobs.cz, StartupJobs, EURemoteJobs — with level, location, and AI/ML filters
- **Claude Integration**: Claude reviews jobs against your profile and criteria
- **Deep Dives**: Structured research on promising opportunities (company stage, role scope, fit analysis)
- **Application Prep**: Gap analysis, interview prep, salary research
- **Web UI**: Review Claude's selections and research at http://localhost:8000

## Requirements

- macOS
- [Claude Desktop](https://claude.ai/download)

The setup script auto-installs everything else (Homebrew, Python, Node.js, Poetry).

## Install

1. [Download ZIP](https://github.com/marcothedeveloper123/job_search/archive/refs/heads/main.zip) and unzip it
2. Open Terminal, then drag the `job_search-main` folder into the window and press Enter
3. Run: `./scripts/setup.sh`

Then quit Terminal and restart Claude Desktop.

## Usage

Tell Claude: "search for jobs"

Claude will start the server and guide you through setup on first use. Review results at http://localhost:8000.

## Adding Job Boards

Scraper configuration is fully CLI-driven. Claude can add new job boards or fix broken ones without editing files.

```bash
jbs scraper list              # List existing scrapers
jbs scraper show <name>       # View config
jbs scraper create <name>     # Create new scraper
jbs scraper set <n> <k> <v>   # Set config value
jbs scraper test <n> <query>  # Test scraper
```

### Adding a New Board

Ask Claude: "Add support for nl.indeed.com"

Claude will:
1. Inspect the site's DOM structure (via Browser MCP)
2. Create and configure the scraper:
   ```bash
   jbs scraper create indeed_nl
   jbs scraper set indeed_nl base_url "https://nl.indeed.com/jobs"
   jbs scraper set indeed_nl selectors.card ".job_seen_beacon"
   jbs scraper set indeed_nl selectors.title "h2.jobTitle a"
   ```
3. Test it: `jbs scraper test indeed_nl "product manager"`

### Fixing Broken Scrapers

When a job board redesigns and scraping fails:

1. Ask Claude: "LinkedIn search is returning empty results. Can you fix it?"
2. Claude inspects the updated DOM and fixes selectors:
   ```bash
   jbs scraper set linkedin selectors.card ".NEW_SELECTOR"
   jbs scraper test linkedin "product manager"
   ```

## License

MIT
