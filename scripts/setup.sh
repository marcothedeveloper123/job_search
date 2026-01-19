#!/bin/bash

# Job Search Assistant Setup
# Designed to work on a fresh Mac with minimal user interaction

cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}Warning:${NC} $1"; }
error() { echo -e "${RED}Error:${NC} $1"; exit 1; }

echo ""
echo "=========================================="
echo "  Job Search Assistant Setup"
echo "=========================================="
echo ""

# --- Homebrew ---
info "Checking Homebrew..."
if ! command -v brew &> /dev/null; then
    info "Installing Homebrew (you may need to enter your password)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || error "Homebrew installation failed"

    # Add to PATH for this session
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi
echo "  ✓ Homebrew"

# --- Python 3.12 (required - pydantic doesn't support 3.14 yet) ---
info "Checking Python 3.12..."
if ! brew list python@3.12 &> /dev/null; then
    info "Installing Python 3.12..."
    brew install python@3.12 || error "Failed to install Python 3.12"
fi
PYTHON312="$(brew --prefix python@3.12)/bin/python3.12"
if [[ ! -f "$PYTHON312" ]]; then
    error "Python 3.12 not found at $PYTHON312"
fi
echo "  ✓ Python 3.12"

# --- Node.js ---
info "Checking Node.js..."
if ! command -v node &> /dev/null; then
    info "Installing Node.js..."
    brew install node || error "Failed to install Node.js"
fi
echo "  ✓ Node.js $(node --version)"

# --- Poetry ---
info "Checking Poetry..."
if ! command -v poetry &> /dev/null; then
    info "Installing Poetry..."
    brew install poetry || error "Failed to install Poetry"
fi
echo "  ✓ Poetry"

# --- Backend dependencies ---
info "Installing backend dependencies..."

# Clean up any stale virtualenv from failed installs
if poetry env info -p &> /dev/null; then
    EXISTING_ENV=$(poetry env info -p 2>/dev/null)
    EXISTING_PYTHON=$(poetry run python --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [[ "$EXISTING_PYTHON" != "3.12" ]]; then
        warn "Removing incompatible virtualenv (Python $EXISTING_PYTHON)"
        poetry env remove --all 2>/dev/null || true
    fi
fi

# Ensure poetry uses Python 3.12
poetry env use "$PYTHON312" || error "Failed to configure Python 3.12 for poetry"
poetry install || error "Failed to install Python dependencies"
echo "  ✓ Backend dependencies"

# --- Playwright browsers ---
info "Installing Playwright browser..."
poetry run playwright install chromium || error "Failed to install Playwright browser"
echo "  ✓ Playwright browser"

# --- Frontend ---
info "Building frontend..."
cd frontend
npm install || error "Failed to install frontend dependencies"
npm run build || error "Failed to build frontend"
cd ..
echo "  ✓ Frontend"

# --- Skill package ---
info "Packaging skill..."
rm -f skill.skill job-search.skill
(cd skill && zip -rq ../job-search.skill . -x "*.DS_Store") || error "Failed to package skill"
echo "  ✓ Skill package"

# --- CLI command ---
info "Installing jbs CLI..."
mkdir -p ~/bin

POETRY_PATH=$(which poetry)
if [[ -z "$POETRY_PATH" ]]; then
    error "Poetry not found in PATH"
fi

cat > ~/bin/jbs << SCRIPT
#!/bin/bash
cd "$PROJECT_DIR" && "$POETRY_PATH" run python -m job_search.cli "\$@"
SCRIPT
chmod +x ~/bin/jbs

# Add ~/bin to PATH if not already there
if ! echo "$PATH" | grep -q "$HOME/bin"; then
    # Create shell config files if they don't exist
    touch ~/.zshrc ~/.zshenv ~/.bash_profile 2>/dev/null || true

    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshenv
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bash_profile
fi
echo "  ✓ CLI command (jbs)"

# --- Claude Desktop ---
echo ""
info "Configuring Claude Desktop..."

CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

if [[ ! -f "$CLAUDE_CONFIG" ]]; then
    warn "Claude Desktop config not found."
    echo "  Install Claude Desktop from: https://claude.ai/download"
    echo "  Then run this script again."
else
    # Check for required MCPs using Python 3.12 (not system python3 which might be 3.14)
    MISSING=$("$PYTHON312" << 'PYEOF'
import json, os
config_path = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
try:
    with open(config_path) as f:
        servers = json.load(f).get("mcpServers", {})
    missing = []
    if "desktop-commander" not in servers:
        missing.append("desktop-commander")
    if "playwright" not in servers:
        missing.append("playwright")
    print(" ".join(missing))
except:
    print("desktop-commander playwright")
PYEOF
)

    if [[ -z "$MISSING" ]]; then
        echo "  ✓ MCP servers configured"
    else
        if [[ "$MISSING" == *"desktop-commander"* ]]; then
            info "Installing Desktop Commander MCP..."
            npx -y @wonderwhy-er/desktop-commander@latest setup || warn "Desktop Commander setup failed - you may need to configure it manually"
        fi

        if [[ "$MISSING" == *"playwright"* ]]; then
            info "Adding Playwright MCP..."
            "$PYTHON312" << 'PYEOF'
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
PYEOF
            echo "  ✓ Playwright MCP added"
        fi
    fi
fi

# --- Skill installation ---
info "Installing skill to Claude Desktop..."

SKILLS_MANIFEST=$(find "$HOME/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin" -name "manifest.json" 2>/dev/null | head -1)

if [[ -n "$SKILLS_MANIFEST" ]]; then
    SKILLS_DIR=$(dirname "$SKILLS_MANIFEST")/skills

    rm -rf "$SKILLS_DIR/job-search"
    unzip -q job-search.skill -d "$SKILLS_DIR/job-search" || error "Failed to extract skill"

    "$PYTHON312" << PYEOF
import json, re
from datetime import datetime

manifest_path = "$SKILLS_MANIFEST"
with open(manifest_path) as f:
    manifest = json.load(f)

skill_md_path = "$SKILLS_DIR/job-search/SKILL.md"
with open(skill_md_path) as f:
    content = f.read()

frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if frontmatter_match:
    fm = frontmatter_match.group(1)
    name_match = re.search(r'^name:\s*["\']?(.+?)["\']?\s*\$', fm, re.MULTILINE)
    desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*\$', fm, re.MULTILINE)
    name = name_match.group(1) if name_match else "job-search"
    description = desc_match.group(1) if desc_match else ""
else:
    name = "job-search"
    description = ""

manifest["skills"] = [s for s in manifest["skills"] if s.get("name") != "job-search"]
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
PYEOF
    echo "  ✓ Skill installed"
else
    warn "Claude Desktop skills folder not found."
    echo "  You may need to open Claude Desktop once first, then run this script again."
    echo "  Or install manually: drag job-search.skill into Claude Desktop settings."
fi

# --- Done ---
echo ""
echo "=========================================="
echo -e "  ${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "NEXT STEPS:"
echo ""
echo "  1. RESTART YOUR TERMINAL"
echo "     (or run: source ~/.zshrc)"
echo ""
echo "  2. RESTART CLAUDE DESKTOP"
echo ""
echo "  3. TELL CLAUDE: \"search for jobs\""
echo ""
