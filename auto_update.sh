#!/bin/bash

# =====================================================================
# Free Claude Code — Auto-Update Script
# Runs daily to check for GitHub updates, pull them, and restart the proxy
# =====================================================================

# Dynamically find the project directory (where this script is located)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
LOG_FILE="$PROJECT_DIR/auto_update.log"

# Find 'uv' binary
UV_BIN=$(command -v uv)
if [ -z "$UV_BIN" ]; then
    if [ -f "$HOME/.local/bin/uv" ]; then
        UV_BIN="$HOME/.local/bin/uv"
    else
        echo "$(date): Error: 'uv' command not found." >> "$LOG_FILE"
        exit 1
    fi
fi

cd "$PROJECT_DIR" || exit 1

echo "========================================" >> "$LOG_FILE"
echo "Auto-Update Check at $(date)" >> "$LOG_FILE"

# Fetch latest changes from GitHub without merging
git fetch origin main

# Compare local code with GitHub code
HEADHASH=$(git rev-parse HEAD)
UPSTREAMHASH=$(git rev-parse origin/main)

if [ "$HEADHASH" != "$UPSTREAMHASH" ]; then
    echo "Updates detected! Pulling new code..." >> "$LOG_FILE"
    
    # Pull the code
    git pull origin main >> "$LOG_FILE" 2>&1
    
    # Sync dependencies
    echo "Syncing dependencies..." >> "$LOG_FILE"
    "$UV_BIN" sync --frozen >> "$LOG_FILE" 2>&1
    
    # Restart the background service
    echo "Restarting proxy service..." >> "$LOG_FILE"
    systemctl --user restart free-claude-code.service
    
    echo "✅ Update successfully applied!" >> "$LOG_FILE"
else
    echo "✅ Already up-to-date. No action needed." >> "$LOG_FILE"
fi
