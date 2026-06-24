from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import psutil

from llmwatch.collectors.api_stats_store import LastInteraction, MtdStats

DEFAULT_OPENCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
ACTIVE_GRACE_SECONDS = 300


def parse_model_field(raw: str) -> tuple[str, str]:
    if not raw:
        return "unknown", "API"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw, "API"

    model_id = str(data.get("id") or data.get("modelID") or "unknown")
    provider = str(data.get("providerID") or "")
    display = f"{provider}/{model_id}" if provider else model_id

    backends = {
        "xai": "xAI",
        "ollama": "Ollama",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Gemini",
        "opencode": "OpenCode",
    }
    return display, backends.get(provider, provider or "API")


def is_cloud_provider(provider: str) -> bool:
    return provider not in {"", "ollama"}


@dataclass
class ApiSession:
    pid: int = 0
    model: str = ""
    backend: str = "API"
    repo: str = ""
    status: str = "idle"
    tokens_sent: int = 0
    tokens_received: int = 0
    session_cost: float = 0.0
    last_message_cost: float = 0.0
    started_at: float = 0.0
    last_activity: float = 0.0
    stats_available: bool = True
    source: str = "opencode"
    session_id: str = ""


@dataclass
class ApiDashboard:
    sessions: list[ApiSession] = field(default_factory=list)
    last_interaction: LastInteraction | None = None
    mtd: MtdStats = field(default_factory=MtdStats)


@dataclass
class ApiSessionMonitor:
    db_path: Path = DEFAULT_OPENCODE_DB

    def _month_bounds_ms(self, ts: float | None = None) -> tuple[str, int, int]:
        when = datetime.fromtimestamp(ts) if ts is not None else datetime.now()
        month_key = when.strftime("%Y-%m")
        start = datetime(when.year, when.month, 1)
        if when.month == 12:
            end = datetime(when.year + 1, 1, 1)
        else:
            end = datetime(when.year, when.month + 1, 1)
        return month_key, int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    def _connect(self) -> sqlite3.Connection | None:
        if not self.db_path.exists():
            return None
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error:
            return None

    def _opencode_pids(self) -> list[int]:
        pids: list[int] = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "status"]):
            try:
                status = proc.info.get("status")
                if status in (
                    psutil.STATUS_ZOMBIE,
                    psutil.STATUS_DEAD,
                    psutil.STATUS_STOPPED,
                ):
                    continue
                name = (proc.info.get("name") or "").lower()
                cmdline = proc.info.get("cmdline") or []
                joined = " ".join(cmdline).lower()
                if "opencode" in name or "opencode" in joined:
                    pids.append(int(proc.info["pid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return pids

    def _session_status(self, conn: sqlite3.Connection, session_id: str) -> str:
        try:
            rows = conn.execute(
                """
                SELECT data FROM event
                WHERE aggregate_id = ? AND type LIKE 'message.updated%'
                ORDER BY seq DESC
                LIMIT 12
                """,
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            return "idle"

        for row in rows:
            try:
                payload = json.loads(row["data"])
            except json.JSONDecodeError:
                continue
            info = payload.get("info") or {}
            if info.get("role") != "assistant":
                continue
            time_info = info.get("time") or {}
            if not time_info.get("completed"):
                return "generating"
            break
        return "idle"

    def _last_message_cost(self, conn: sqlite3.Connection, session_id: str) -> float:
        try:
            rows = conn.execute(
                """
                SELECT data FROM event
                WHERE aggregate_id = ? AND type LIKE 'message.updated%'
                ORDER BY seq DESC
                LIMIT 20
                """,
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            return 0.0

        for row in rows:
            try:
                payload = json.loads(row["data"])
            except json.JSONDecodeError:
                continue
            info = payload.get("info") or {}
            if info.get("role") != "assistant":
                continue
            return float(info.get("cost") or 0.0)
        return 0.0

    def _session_from_row(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        pid: int = 0,
        force_active: bool = False,
    ) -> ApiSession:
        model, backend = parse_model_field(str(row["model"] or ""))
        updated_ms = int(row["time_updated"] or 0)
        updated_at = updated_ms / 1000 if updated_ms else 0.0
        created_ms = int(row["time_created"] or 0)
        created_at = created_ms / 1000 if created_ms else updated_at
        session_id = str(row["id"] or "")

        status = self._session_status(conn, session_id)
        if force_active and status == "idle":
            status = "active"

        return ApiSession(
            pid=pid,
            model=model,
            backend=backend,
            repo=str(row["directory"] or ""),
            status=status,
            tokens_sent=int(row["tokens_input"] or 0),
            tokens_received=int(row["tokens_output"] or 0),
            session_cost=float(row["cost"] or 0.0),
            last_message_cost=self._last_message_cost(conn, session_id),
            started_at=created_at,
            last_activity=updated_at,
            stats_available=True,
            source="opencode",
            session_id=session_id,
        )

    def _active_session(self, conn: sqlite3.Connection, pids: list[int]) -> ApiSession | None:
        try:
            row = conn.execute(
                """
                SELECT id, model, directory, cost, tokens_input, tokens_output,
                       time_created, time_updated
                FROM session
                ORDER BY time_updated DESC
                LIMIT 1
                """
            ).fetchone()
        except sqlite3.Error:
            return None

        if row is None:
            return None

        updated_ms = int(row["time_updated"] or 0)
        updated_at = updated_ms / 1000 if updated_ms else 0.0
        recently_active = (time.time() - updated_at) <= ACTIVE_GRACE_SECONDS
        if not pids and not recently_active:
            return None

        pid = pids[0] if pids else 0
        return self._session_from_row(
            conn,
            row,
            pid=pid,
            force_active=bool(pids),
        )

    def _mtd_stats(self, conn: sqlite3.Connection) -> MtdStats:
        month_key, start_ms, end_ms = self._month_bounds_ms()
        try:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(tokens_input), 0) AS tokens_sent,
                    COALESCE(SUM(tokens_output), 0) AS tokens_received,
                    COALESCE(SUM(cost), 0.0) AS total_cost,
                    COUNT(*) AS sessions
                FROM session
                WHERE time_updated >= ? AND time_updated < ?
                  AND (tokens_input > 0 OR tokens_output > 0 OR cost > 0)
                """,
                (start_ms, end_ms),
            ).fetchone()
            messages = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM event
                    WHERE type LIKE 'message.updated%'
                      AND CAST(json_extract(data, '$.info.role') AS TEXT) = 'assistant'
                      AND CAST(json_extract(data, '$.info.time.completed') AS INTEGER) IS NOT NULL
                      AND CAST(json_extract(data, '$.info.time.completed') AS INTEGER) >= ?
                      AND CAST(json_extract(data, '$.info.time.completed') AS INTEGER) < ?
                    """,
                    (start_ms, end_ms),
                ).fetchone()[0]
            )
        except sqlite3.Error:
            return MtdStats(month=month_key)

        if row is None:
            return MtdStats(month=month_key)

        return MtdStats(
            month=month_key,
            tokens_sent=int(row["tokens_sent"] or 0),
            tokens_received=int(row["tokens_received"] or 0),
            total_cost=float(row["total_cost"] or 0.0),
            messages=messages,
        )

    def _last_interaction(self, conn: sqlite3.Connection) -> LastInteraction | None:
        try:
            row = conn.execute(
                """
                SELECT id, model, directory, cost, tokens_input, tokens_output,
                       time_created, time_updated
                FROM session
                WHERE tokens_input > 0 OR tokens_output > 0 OR cost > 0
                ORDER BY time_updated DESC
                LIMIT 1
                """
            ).fetchone()
        except sqlite3.Error:
            return None

        if row is None:
            return None

        model, backend = parse_model_field(str(row["model"] or ""))
        updated_ms = int(row["time_updated"] or 0)
        session = self._session_from_row(conn, row)
        return LastInteraction(
            model=model,
            backend=backend,
            repo=str(row["directory"] or ""),
            tokens_sent=session.tokens_sent,
            tokens_received=session.tokens_received,
            message_cost=session.last_message_cost,
            session_cost=session.session_cost,
            at=updated_ms / 1000 if updated_ms else 0.0,
        )

    def collect(self) -> ApiDashboard:
        conn = self._connect()
        if conn is None:
            month_key, _, _ = self._month_bounds_ms()
            return ApiDashboard(mtd=MtdStats(month=month_key))

        try:
            pids = self._opencode_pids()
            session = self._active_session(conn, pids)
            sessions = [session] if session is not None else []
            return ApiDashboard(
                sessions=sessions,
                last_interaction=self._last_interaction(conn),
                mtd=self._mtd_stats(conn),
            )
        finally:
            conn.close()