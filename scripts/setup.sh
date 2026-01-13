#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "Installing backend dependencies..."
poetry install

echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Packaging skill..."
rm -f skill.skill job-search.skill
# Use the skill-creator package script if available, otherwise create a simple zip
if command -v python3 &> /dev/null; then
    SKILL_PACKAGER="$HOME/.claude/plugins/cache/anthropic-agent-skills/example-skills/"
    PACKAGER=$(find "$SKILL_PACKAGER" -name "package_skill.py" 2>/dev/null | head -1)
    if [ -n "$PACKAGER" ]; then
        python3 "$PACKAGER" skill 2>/dev/null || (cd skill && zip -r ../job-search.skill . -x "*.DS_Store")
        # Rename if packager created skill.skill
        [ -f skill.skill ] && mv skill.skill job-search.skill
    else
        (cd skill && zip -r ../job-search.skill . -x "*.DS_Store")
    fi
else
    (cd skill && zip -r ../job-search.skill . -x "*.DS_Store")
fi

echo "Installing jbs CLI..."
mkdir -p ~/bin

# Get absolute path to poetry (works across different install methods)
POETRY_PATH=$(which poetry)
if [ -z "$POETRY_PATH" ]; then
    echo "Error: poetry not found in PATH"
    exit 1
fi

# Get absolute path to project directory
PROJECT_DIR=$(pwd)

cat > ~/bin/jbs << SCRIPT
#!/bin/bash
cd "$PROJECT_DIR" && $POETRY_PATH run python -m job_search.cli "\$@"
SCRIPT
chmod +x ~/bin/jbs

if ! echo "$PATH" | grep -q "$HOME/bin"; then
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshenv
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bash_profile
    echo "Added ~/bin to PATH in ~/.zshrc, ~/.zshenv, and ~/.bash_profile"
fi

echo ""
echo "=== Claude Desktop MCP Setup ==="
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

if [ ! -f "$CLAUDE_CONFIG" ]; then
    echo "Claude Desktop config not found. Install Claude Desktop first."
else
    # Check what's missing using Python
    MISSING=$(python3 << 'PYEOF'
import json, os
config_path = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
try:
    with open(config_path) as f:
        servers = json.load(f).get("mcpServers", {})
    missing = []
    if "desktop-commander" not in servers:
        missing.append("desktop-commander")
    if "browsermcp" not in servers and "playwright" not in servers:
        missing.append("browser")
    print(" ".join(missing))
except: print("desktop-commander browser")
PYEOF
)

    if [ -z "$MISSING" ]; then
        echo "✓ All required MCPs already configured"
    else
        if [[ "$MISSING" == *"desktop-commander"* ]]; then
            read -p "Install Desktop Commander MCP? [y/N] " -n 1 -r; echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                npx @wonderwhy-er/desktop-commander@latest setup
            fi
        fi

        if [[ "$MISSING" == *"browser"* ]]; then
            read -p "Install Playwright MCP (for web research)? [y/N] " -n 1 -r; echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                python3 << 'PYEOF'
import json, os
config_path = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
with open(config_path) as f:
    config = json.load(f)
config.setdefault("mcpServers", {})["playwright"] = {
    "command": "npx",
    "args": ["@playwright/mcp@latest", "--vision"]
}
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
print("✓ Added Playwright MCP")
PYEOF
            fi
        fi
        echo ""
        echo "Restart Claude Desktop to apply MCP changes."
    fi
fi

echo ""
echo "=== Skill Installation ==="
echo "Install the job-search skill in Claude Desktop:"
echo "  1. Open Claude Desktop → Settings → Capabilities"
echo "  2. Drag job-search.skill into the window"
echo ""
echo "Or double-click: $(pwd)/job-search.skill"
echo ""

echo "=== Next Steps ==="
echo "1. Source your shell config:  source ~/.zshrc"
echo "2. Restart Claude Desktop (if MCP changes were made)"
echo "3. Start the server:  poetry run python -m server.app"
echo "4. Open http://localhost:8000"
echo ""
read -p "Set up LinkedIn auth now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    poetry run python backend/scripts/linkedin_scraper.py --login
fi
