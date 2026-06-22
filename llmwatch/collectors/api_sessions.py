from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from llmwatch.collectors.api_stats_store import (
    ApiStatsStore,
    LastInteraction,
    MtdStats,
)

DEFAULT_SESSION_DIR = Path.home() / ".config" / "aider" / "sessions"
ARCHIVE_DIR_NAME = "archive"


def is_api_model(model: str) -> bool:
    if not model:
        return False
    if model.startswith(("ollama_chat/", "ollama/")):
        return False
    return True


def backend_from_model(model: str) -> str:
    if model.startswith("xai/"):
        return "xAI"
    if model.startswith("openai/"):
        return "OpenAI"
    if model.startswith("anthropic/"):
        return "Anthropic"
    if model.startswith("gemini/"):
        return "Gemini"
    return "API"


def model_from_cmdline(cmdline: list[str]) -> str:
    for index, arg in enumerate(cmdline):
        if arg == "--model" and index + 1 < len(cmdline):
            return cmdline[index + 1]
    return ""


def analytics_log_from_cmdline(cmdline: list[str]) -> Path | None:
    for index, arg in enumerate(cmdline):
        if arg == "--analytics-log" and index + 1 < len(cmdline):
            return Path(cmdline[index + 1]).expanduser()
    return None


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
    stats_available: bool = False
    source: str = "aider"


@dataclass
class ApiDashboard:
    sessions: list[ApiSession] = field(default_factory=list)
    last_interaction: LastInteraction | None = None
    mtd: MtdStats = field(default_factory=MtdStats)


@dataclass
class ApiSessionMonitor:
    session_dir: Path = DEFAULT_SESSION_DIR
    stats_store: ApiStatsStore = field(default_factory=ApiStatsStore)
    _log_offsets: dict[Path, int] = field(default_factory=dict)

    @property
    def archive_dir(self) -> Path:
        return self.session_dir / ARCHIVE_DIR_NAME

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            proc = psutil.Process(pid)
            status = proc.status()
            if status in (
                psutil.STATUS_ZOMBIE,
                psutil.STATUS_DEAD,
                psutil.STATUS_STOPPED,
            ):
                return False
            name = (proc.name() or "").lower()
            cmd = " ".join(proc.cmdline()).lower()
            return "aider" in name or "aider" in cmd
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _archive_analytics(self, analytics_path: Path) -> None:
        if not analytics_path.exists():
            return
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        target = self.archive_dir / analytics_path.name
        if target.exists():
            target = self.archive_dir / f"{int(time.time())}-{analytics_path.name}"
        try:
            analytics_path.rename(target)
        except OSError:
            pass

    def _finalize_stale_session(self, manifest: Path) -> None:
        try:
            data = json.loads(manifest.read_text())
        except (json.JSONDecodeError, OSError):
            manifest.unlink(missing_ok=True)
            return

        analytics = manifest.with_suffix(".analytics.jsonl")
        self.stats_store.ingest_analytics_file(
            analytics,
            model=str(data.get("model") or ""),
            backend=str(data.get("backend") or "API"),
            repo=str(data.get("repo") or ""),
        )
        self._archive_analytics(analytics)
        manifest.unlink(missing_ok=True)

    def _cleanup_stale(self) -> None:
        if not self.session_dir.exists():
            return
        for manifest in list(self.session_dir.glob("*.json")):
            try:
                data = json.loads(manifest.read_text())
            except (json.JSONDecodeError, OSError):
                manifest.unlink(missing_ok=True)
                continue
            pid = int(data.get("pid") or 0)
            if not self._pid_alive(pid):
                self._finalize_stale_session(manifest)

    def _ingest_all_analytics(self) -> None:
        paths: list[tuple[Path, str, str, str]] = []

        if self.session_dir.exists():
            for manifest in self.session_dir.glob("*.json"):
                try:
                    data = json.loads(manifest.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                analytics = manifest.with_suffix(".analytics.jsonl")
                paths.append(
                    (
                        analytics,
                        str(data.get("model") or ""),
                        str(data.get("backend") or "API"),
                        str(data.get("repo") or ""),
                    )
                )

        if self.archive_dir.exists():
            for analytics in self.archive_dir.glob("*.analytics.jsonl"):
                paths.append((analytics, "", "API", ""))

        seen: set[Path] = set()
        for analytics, model, backend, repo in paths:
            resolved = analytics.resolve()
            if resolved in seen or not analytics.exists():
                continue
            seen.add(resolved)
            self.stats_store.ingest_analytics_file(
                analytics,
                model=model,
                backend=backend,
                repo=repo,
            )

    def _parse_analytics(self, analytics_path: Path, session: ApiSession) -> None:
        if not analytics_path.exists():
            return

        offset = self._log_offsets.get(analytics_path, 0)
        try:
            size = analytics_path.stat().st_size
            if size < offset:
                offset = 0
            with analytics_path.open("r", errors="replace") as handle:
                handle.seek(offset)
                chunk = handle.read()
                self._log_offsets[analytics_path] = handle.tell()
        except OSError:
            return

        if not chunk.strip():
            return

        session.stats_available = True
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = entry.get("event") or ""
            props = entry.get("properties") or {}
            ts = float(entry.get("time") or time.time())
            session.last_activity = max(session.last_activity, ts)

            if event == "message_send_starting":
                session.status = "generating"
                continue

            if event != "message_send":
                continue

            session.status = "idle"
            session.tokens_sent += int(props.get("prompt_tokens") or 0)
            session.tokens_received += int(props.get("completion_tokens") or 0)
            session.last_message_cost = float(props.get("cost") or 0.0)
            session.session_cost = float(props.get("total_cost") or session.session_cost)
            model = props.get("main_model")
            if model:
                session.model = str(model)

    def _session_from_manifest(self, manifest: Path) -> ApiSession | None:
        try:
            data = json.loads(manifest.read_text())
        except (json.JSONDecodeError, OSError):
            return None

        pid = int(data.get("pid") or 0)
        if not self._pid_alive(pid):
            return None

        session = ApiSession(
            pid=pid,
            model=str(data.get("model") or "unknown"),
            backend=str(data.get("backend") or "API"),
            repo=str(data.get("repo") or ""),
            started_at=float(data.get("started_at") or 0.0),
            last_activity=float(data.get("started_at") or 0.0),
        )
        self._parse_analytics(manifest.with_suffix(".analytics.jsonl"), session)
        return session

    def _discover_from_processes(self, known_pids: set[int]) -> list[ApiSession]:
        sessions: list[ApiSession] = []
        for proc in psutil.process_iter(["pid", "cmdline", "cwd", "status"]):
            try:
                pid = int(proc.info.get("pid") or 0)
                if pid in known_pids:
                    continue
                status = proc.info.get("status")
                if status in (
                    psutil.STATUS_ZOMBIE,
                    psutil.STATUS_DEAD,
                    psutil.STATUS_STOPPED,
                ):
                    continue
                cmdline = proc.info.get("cmdline") or []
                if not any("aider" in (part or "").lower() for part in cmdline):
                    continue

                model = model_from_cmdline(cmdline)
                if not is_api_model(model):
                    continue

                repo = ""
                try:
                    repo = proc.cwd() or ""
                except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                    pass

                session = ApiSession(
                    pid=pid,
                    model=model,
                    backend=backend_from_model(model),
                    repo=repo,
                    status="active",
                    started_at=time.time(),
                    last_activity=time.time(),
                )

                analytics_path = analytics_log_from_cmdline(cmdline)
                if analytics_path is None and self.session_dir.exists():
                    analytics_path = self.session_dir / f"{pid}.analytics.jsonl"
                if analytics_path is not None:
                    self._parse_analytics(analytics_path, session)
                if not session.stats_available:
                    session.status = "active"

                sessions.append(session)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return sessions

    def collect(self) -> ApiDashboard:
        self.stats_store.load()
        self._cleanup_stale()
        self._ingest_all_analytics()
        self.stats_store.save()

        sessions: list[ApiSession] = []
        known_pids: set[int] = set()

        if self.session_dir.exists():
            for manifest in sorted(self.session_dir.glob("*.json")):
                session = self._session_from_manifest(manifest)
                if session is None:
                    continue
                sessions.append(session)
                known_pids.add(session.pid)

        sessions.extend(self._discover_from_processes(known_pids))
        sessions.sort(
            key=lambda s: (
                s.status == "generating",
                s.last_activity,
                s.started_at,
            ),
            reverse=True,
        )
        if sessions:
            sessions = [sessions[0]]

        last_interaction, mtd = self.stats_store.snapshot()
        return ApiDashboard(
            sessions=sessions,
            last_interaction=last_interaction,
            mtd=mtd,
        )