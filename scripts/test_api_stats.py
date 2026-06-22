#!/usr/bin/env python3
import json
import tempfile
import time
from pathlib import Path

from llmwatch.collectors.api_sessions import ApiSessionMonitor
from llmwatch.collectors.api_stats_store import ApiStatsStore
import llmwatch.collectors.api_sessions as api_mod


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        sessions = base / "sessions"
        sessions.mkdir()
        stats_file = base / "api-stats.json"

        analytics = sessions / "100.analytics.jsonl"
        analytics.write_text(
            json.dumps(
                {
                    "event": "message_send",
                    "properties": {
                        "prompt_tokens": "100",
                        "completion_tokens": "50",
                        "cost": "0.01",
                        "total_cost": "0.01",
                        "main_model": "xai/grok-code-fast-1",
                    },
                    "time": time.time(),
                }
            )
            + "\n"
            + json.dumps(
                {
                    "event": "message_send",
                    "properties": {
                        "prompt_tokens": "200",
                        "completion_tokens": "80",
                        "cost": "0.02",
                        "total_cost": "0.03",
                        "main_model": "xai/grok-code-fast-1",
                    },
                    "time": time.time(),
                }
            )
            + "\n"
        )

        store = ApiStatsStore(stats_file=stats_file)
        store.load()
        store.ingest_analytics_file(
            analytics, model="xai/grok-code-fast-1", backend="xAI", repo="/tmp"
        )
        store.save()
        store.load()
        store.ingest_analytics_file(
            analytics, model="xai/grok-code-fast-1", backend="xAI", repo="/tmp"
        )
        assert store.mtd.messages == 2
        assert store.mtd.tokens_sent == 300
        assert store.last_interaction.tokens_received == 80

        store.load()
        store.ingest_analytics_file(
            analytics, model="xai/grok-code-fast-1", backend="xAI", repo="/tmp"
        )
        assert store.mtd.messages == 2

        orig = api_mod.ApiSessionMonitor._pid_alive
        api_mod.ApiSessionMonitor._pid_alive = lambda self, p: False
        dash = ApiSessionMonitor(
            session_dir=sessions, stats_store=ApiStatsStore(stats_file=stats_file)
        ).collect()
        api_mod.ApiSessionMonitor._pid_alive = orig
        assert dash.mtd.messages == 2
        assert dash.last_interaction is not None
        print("stats persistence: OK")


if __name__ == "__main__":
    main()