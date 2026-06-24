#!/usr/bin/env python3
import json
import sqlite3
import tempfile
import time
from pathlib import Path

from llmwatch.collectors.api_sessions import ApiSessionMonitor


def _create_db(path: Path) -> None:
    now_ms = int(time.time() * 1000)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE session (
          id TEXT PRIMARY KEY,
          model TEXT,
          directory TEXT,
          cost REAL,
          tokens_input INTEGER,
          tokens_output INTEGER,
          time_created INTEGER,
          time_updated INTEGER
        );
        CREATE TABLE event (
          id TEXT PRIMARY KEY,
          aggregate_id TEXT,
          seq INTEGER,
          type TEXT,
          data TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ses_test1",
            json.dumps({"id": "grok-build-0.1", "providerID": "xai"}),
            "/tmp/project",
            0.05,
            1000,
            200,
            now_ms - 60_000,
            now_ms,
        ),
    )
    conn.execute(
        """
        INSERT INTO event VALUES (?, ?, ?, ?, ?)
        """,
        (
            "evt1",
            "ses_test1",
            1,
            "message.updated.1",
            json.dumps(
                {
                    "info": {
                        "role": "assistant",
                        "time": {"created": now_ms - 1000, "completed": now_ms},
                        "cost": 0.01,
                    }
                }
            ),
        ),
    )
    conn.commit()
    conn.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "opencode.db"
        _create_db(db_path)

        dash = ApiSessionMonitor(db_path=db_path).collect()
        assert dash.sessions, "expected active session"
        session = dash.sessions[0]
        assert session.model == "xai/grok-build-0.1"
        assert session.backend == "xAI"
        assert session.tokens_sent == 1000
        assert session.session_cost == 0.05
        assert dash.mtd.messages >= 1
        assert dash.mtd.total_cost >= 0.05
        print("opencode session tracking: OK")


if __name__ == "__main__":
    main()