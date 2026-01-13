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

- Python 3.11+
- Node.js 18+
- [Claude Desktop](https://claude.ai/download)
- [Desktop Commander MCP](https://desktopcommander.app/) — For Claude to run CLI commands
- [Browser MCP](https://browsermcp.io/) or [Playwright MCP](https://github.com/anthropics/claude-mcp/tree/main/packages/mcp-server-playwright) — For online research

## Install

```bash
git clone https://github.com/marcothedeveloper123/job_search.git
cd job_search
./scripts/setup.sh
source ~/.zshrc
```

The setup script:
- Installs Python dependencies (Poetry)
- Builds the frontend
- Packages the skill (`job-search.skill`)
- Adds `jbs` CLI to your PATH
- Optionally installs missing MCPs

### Install the Skill

After running setup, install the skill in Claude Desktop:

1. Open Claude Desktop → Settings → Capabilities
2. Drag `job-search.skill` into the window

## Usage

1. Start the server: `poetry run python -m server.app`
2. Open Claude Desktop and say "search for jobs" to activate the skill
3. Review results at http://localhost:8000

Claude will guide you through creating your profile on first use.

## License

MIT
