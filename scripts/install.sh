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

cat > "$BIN_DIR/aider-merge-stats" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" -m llmwatch.merge_stats "\$@"
EOF
chmod +x "$BIN_DIR/aider-merge-stats"

echo "Installed llmwatch -> $BIN_DIR/llmwatch"
echo "Installed aider-merge-stats -> $BIN_DIR/aider-merge-stats"
echo "Run: llmwatch"