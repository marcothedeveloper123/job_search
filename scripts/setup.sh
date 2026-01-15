#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "=== Job Search Assistant Setup ==="
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for this session
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# Check for Python 3.11+
if ! command -v python3 &> /dev/null; then
    echo "Installing Python..."
    brew install python@3.12
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    brew install node
fi

# Check for Poetry
if ! command -v poetry &> /dev/null; then
    echo "Installing Poetry..."
    brew install poetry
fi

echo ""
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
cd "$PROJECT_DIR" && "$POETRY_PATH" run python -m job_search.cli "\$@"
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
echo "Installing skill..."

# Find Claude Desktop skills directory
SKILLS_MANIFEST=$(find "$HOME/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin" -name "manifest.json" 2>/dev/null | head -1)

if [ -n "$SKILLS_MANIFEST" ]; then
    SKILLS_DIR=$(dirname "$SKILLS_MANIFEST")/skills

    # Unzip skill to skills directory
    rm -rf "$SKILLS_DIR/job-search"
    unzip -q job-search.skill -d "$SKILLS_DIR/job-search"

    # Update manifest.json
    python3 << PYEOF
import json
from datetime import datetime

manifest_path = "$SKILLS_MANIFEST"
with open(manifest_path) as f:
    manifest = json.load(f)

# Read skill metadata from SKILL.md frontmatter
skill_md_path = "$SKILLS_DIR/job-search/SKILL.md"
with open(skill_md_path) as f:
    content = f.read()

# Parse YAML frontmatter
import re
frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if frontmatter_match:
    fm = frontmatter_match.group(1)
    name_match = re.search(r'^name:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
    desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
    name = name_match.group(1) if name_match else "job-search"
    description = desc_match.group(1) if desc_match else ""
else:
    name = "job-search"
    description = ""

# Remove existing entry if present
manifest["skills"] = [s for s in manifest["skills"] if s.get("name") != "job-search"]

# Add new entry
manifest["skills"].insert(0, {
    "skillId": "skill_jobsearch_user",
    "name": name,
    "description": description,
    "creatorType": "user",
    "updatedAt": datetime.utcnow().isoformat() + "Z",
    "enabled": True
})

manifest["lastUpdated"] = int(datetime.utcnow().timestamp() * 1000)

with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print("✓ Skill installed")
PYEOF
else
    echo "Claude Desktop skills folder not found."
    echo "Install skill manually: drag job-search.skill into Claude Desktop settings."
fi

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. RESTART YOUR TERMINAL (or run: source ~/.zshrc)"
echo "2. RESTART CLAUDE DESKTOP"
echo "3. TELL CLAUDE: \"search for jobs\""
echo ""
