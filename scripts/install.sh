#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
BIN_DIR="${HOME}/.local/bin"

python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -e "$ROOT"

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
echo "Run: llmwatch"