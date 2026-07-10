#!/usr/bin/env bash
set -euo pipefail

SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_ROOT="${HOME}/.local/share/llmwatch"
VENV="$INSTALL_ROOT/.venv"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "$INSTALL_ROOT"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
# Editable install keeps ~/.local/bin/llmwatch in sync with source changes.
"$VENV/bin/pip" install -e "$SOURCE"

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/llmwatch" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/llmwatch" "\$@"
EOF
chmod +x "$BIN_DIR/llmwatch"
rm -f "$BIN_DIR/aider-merge-stats"

if ! "$BIN_DIR/llmwatch" --version >/dev/null 2>&1; then
  echo "Install failed: llmwatch --version did not run." >&2
  exit 1
fi

echo "Installed llmwatch -> $BIN_DIR/llmwatch"
echo "Runtime: $VENV"
echo "Run: llmwatch"