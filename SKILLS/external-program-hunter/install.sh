#!/usr/bin/env bash
# Install external-program-hunter into ~/.claude/skills/
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HOME}/.claude/skills/external-program-hunter"

mkdir -p "$DEST"
cp -R "$SRC/SKILL.md" "$SRC/scripts" "$SRC/references" "$DEST/"
chmod +x "$DEST/scripts/merge_programs.py" 2>/dev/null || true

echo "Installed external-program-hunter -> $DEST"
echo "Output file will be written to: ${HOME}/ClientExternal.md"
echo "Invoke it in Claude Code with:  /external-program-hunter"
