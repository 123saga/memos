#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────────────────────
#  MemOS Setup Script
#  Works on macOS (Intel + Apple Silicon) and Linux
# ─────────────────────────────────────────────────────────────────────────────

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

MEMOS_DIR="$HOME/.memos"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${BOLD}MemOS Setup${RESET}"
echo "──────────────────────────────────────────"

# ── Step 1: Detect OS and architecture ────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
echo -e "  OS:   $OS"
echo -e "  Arch: $ARCH"
echo ""

# ── Step 2: Find Python 3.10+ ─────────────────────────────────────────────────
echo -e "${BOLD}[1/4] Finding Python 3.10+...${RESET}"
PYTHON=""

if [[ "$OS" == "Darwin" ]]; then
    CANDIDATES=(
        "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
        "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
        "/opt/homebrew/bin/python3"
        "/usr/local/bin/python3"
        "python3"
    )
elif [[ "$OS" == "Linux" ]]; then
    CANDIDATES=(python3.12 python3.11 python3.10 python3)
fi

for candidate in "${CANDIDATES[@]}"; do
    if command -v "$candidate" &>/dev/null || [ -f "$candidate" ]; then
        VERSION=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}  Error: Python 3.10+ not found.${RESET}"
    echo "  Install via Homebrew: brew install python@3.12"
    echo "  Or from: https://python.org"
    exit 1
fi

echo -e "  ${GREEN}Found: $PYTHON ($($PYTHON --version))${RESET}"

# ── Step 3: Create virtual environment ────────────────────────────────────────
echo ""
echo -e "${BOLD}[2/4] Creating virtual environment...${RESET}"

if [ -d "$PROJECT_DIR/.venv" ]; then
    echo -e "  ${YELLOW}Existing .venv found — recreating${RESET}"
    rm -rf "$PROJECT_DIR/.venv"
fi

USE_ARCH=false
if [[ "$OS" == "Darwin" ]]; then
    FILE_OUTPUT=$(file "$PYTHON" 2>/dev/null || echo "")
    if echo "$FILE_OUTPUT" | grep -q "universal binary"; then
        arch -arm64 "$PYTHON" -m venv "$PROJECT_DIR/.venv"
        USE_ARCH=true
    else
        "$PYTHON" -m venv "$PROJECT_DIR/.venv"
    fi
else
    "$PYTHON" -m venv "$PROJECT_DIR/.venv"
fi

echo -e "  ${GREEN}Virtual environment created${RESET}"

# ── Step 4: Install dependencies ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}[3/4] Installing dependencies...${RESET}"

PIP="$PROJECT_DIR/.venv/bin/pip"
if [ "$USE_ARCH" = true ]; then
    arch -arm64 "$PIP" install -r "$PROJECT_DIR/requirements.txt" --quiet
else
    "$PIP" install -r "$PROJECT_DIR/requirements.txt" --quiet
fi

echo -e "  ${GREEN}Dependencies installed${RESET}"

# ── Step 5: Create data directory and runner script ───────────────────────────
echo ""
echo -e "${BOLD}[4/4] Finalizing setup...${RESET}"

mkdir -p "$MEMOS_DIR/packs"
echo -e "  ${GREEN}Created ~/.memos/${RESET}"

if [ "$USE_ARCH" = true ]; then
    cat > "$PROJECT_DIR/memos.sh" << EOF
#!/bin/bash
arch -arm64 "$PROJECT_DIR/.venv/bin/python3" "$PROJECT_DIR/memos.py" "\$@"
EOF
else
    cat > "$PROJECT_DIR/memos.sh" << EOF
#!/bin/bash
"$PROJECT_DIR/.venv/bin/python3" "$PROJECT_DIR/memos.py" "\$@"
EOF
fi
chmod +x "$PROJECT_DIR/memos.sh"
echo -e "  ${GREEN}Created memos.sh runner${RESET}"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}MemOS is ready!${RESET}"
echo ""
echo "──────────────────────────────────────────"
echo -e "${BOLD}Next steps:${RESET}"
echo ""
echo "  1. Import your memories:"
echo "     ./memos.sh import --source chatgpt --input ~/Downloads/memories.json"
echo "     ./memos.sh import --source claude  --input ~/Downloads/memory.json"
echo "     ./memos.sh import --source gemini  --input ~/Downloads/gemini_memories.json"
echo ""
echo "  2. Explore your store:"
echo "     ./memos.sh stats"
echo "     ./memos.sh health"
echo "     ./memos.sh search \"your query\""
echo ""
echo "  3. Connect to Claude Desktop:"
echo "     Add to: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo ""
echo '     {'
echo '       "mcpServers": {'
echo '         "memos": {'
echo '           "command": "'"$PROJECT_DIR/memos.sh"'",'
echo '           "args": ["serve"]'
echo '         }'
echo '       }'
echo '     }'
echo ""
echo "  4. Restart Claude Desktop and ask: \"What do you know about me?\""
echo ""
echo "  Run ./memos.sh --help for all commands."
echo "──────────────────────────────────────────"
