"""Deprecated: OpenCode stats are read live from ~/.local/share/opencode/opencode.db."""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "opencode-merge-stats is no longer required — llmwatch reads OpenCode stats "
        "directly from ~/.local/share/opencode/opencode.db",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())