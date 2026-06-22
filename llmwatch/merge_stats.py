from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from llmwatch.collectors.api_stats_store import ApiStatsStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge Aider API analytics into persisted stats.")
    parser.add_argument("analytics", type=Path, help="Path to .analytics.jsonl file")
    parser.add_argument("manifest", type=Path, nargs="?", help="Optional session manifest JSON")
    args = parser.parse_args(argv)

    model = backend = repo = ""
    if args.manifest and args.manifest.exists():
        try:
            data = json.loads(args.manifest.read_text())
            model = str(data.get("model") or "")
            backend = str(data.get("backend") or "API")
            repo = str(data.get("repo") or "")
        except (json.JSONDecodeError, OSError):
            pass

    store = ApiStatsStore()
    store.load()
    store.ingest_analytics_file(args.analytics, model=model, backend=backend, repo=repo)
    store.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())