from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

DEFAULT_STATS_FILE = Path.home() / ".config" / "aider" / "api-stats.json"


@dataclass
class LastInteraction:
    model: str = ""
    backend: str = "API"
    repo: str = ""
    tokens_sent: int = 0
    tokens_received: int = 0
    message_cost: float = 0.0
    session_cost: float = 0.0
    at: float = 0.0


@dataclass
class MtdStats:
    month: str = ""
    tokens_sent: int = 0
    tokens_received: int = 0
    total_cost: float = 0.0
    messages: int = 0


@dataclass
class ApiStatsStore:
    stats_file: Path = DEFAULT_STATS_FILE
    last_interaction: LastInteraction | None = None
    mtd: MtdStats = field(default_factory=MtdStats)
    _processed_offsets: dict[str, int] = field(default_factory=dict)

    def _month_key(self, ts: float | None = None) -> str:
        when = datetime.fromtimestamp(ts) if ts is not None else datetime.now()
        return when.strftime("%Y-%m")

    def load(self) -> None:
        if not self.stats_file.exists():
            self.mtd = MtdStats(month=self._month_key())
            return
        try:
            data = json.loads(self.stats_file.read_text())
        except (json.JSONDecodeError, OSError):
            self.mtd = MtdStats(month=self._month_key())
            return

        last = data.get("last_interaction")
        if last:
            self.last_interaction = LastInteraction(**last)

        mtd = data.get("mtd") or data.get("today") or {}
        current_month = self._month_key()
        stored_month = mtd.get("month") or self._month_from_legacy_date(mtd.get("date"))
        if stored_month == current_month:
            self.mtd = MtdStats(
                month=stored_month,
                tokens_sent=int(mtd.get("tokens_sent") or 0),
                tokens_received=int(mtd.get("tokens_received") or 0),
                total_cost=float(mtd.get("total_cost") or 0.0),
                messages=int(mtd.get("messages") or 0),
            )
            self._processed_offsets = {
                str(key): int(value)
                for key, value in (data.get("processed_offsets") or {}).items()
            }
        else:
            self.mtd = MtdStats(month=current_month)
            self._processed_offsets = {}

    def _month_from_legacy_date(self, value: str | None) -> str:
        if not value:
            return ""
        try:
            return date.fromisoformat(value).strftime("%Y-%m")
        except ValueError:
            return ""

    def save(self) -> None:
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_interaction": asdict(self.last_interaction) if self.last_interaction else None,
            "mtd": asdict(self.mtd),
            "processed_offsets": self._processed_offsets,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.stats_file.write_text(json.dumps(payload, indent=2))

    def ingest_analytics_file(
        self,
        analytics_path: Path,
        *,
        model: str = "",
        backend: str = "API",
        repo: str = "",
    ) -> None:
        if not analytics_path.exists():
            return

        key = str(analytics_path.resolve())
        offset = self._processed_offsets.get(key, 0)
        try:
            size = analytics_path.stat().st_size
            if size < offset:
                offset = 0
            with analytics_path.open("r", errors="replace") as handle:
                handle.seek(offset)
                chunk = handle.read()
                self._processed_offsets[key] = handle.tell()
        except OSError:
            return

        if not chunk.strip():
            return

        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event") != "message_send":
                continue

            props = entry.get("properties") or {}
            ts = float(entry.get("time") or datetime.now().timestamp())
            prompt_tokens = int(props.get("prompt_tokens") or 0)
            completion_tokens = int(props.get("completion_tokens") or 0)
            message_cost = float(props.get("cost") or 0.0)
            session_cost = float(props.get("total_cost") or 0.0)
            event_model = str(props.get("main_model") or model or "unknown")

            self._record_message(
                model=event_model,
                backend=backend,
                repo=repo,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                message_cost=message_cost,
                session_cost=session_cost,
                at=ts,
            )

    def _record_message(
        self,
        *,
        model: str,
        backend: str,
        repo: str,
        prompt_tokens: int,
        completion_tokens: int,
        message_cost: float,
        session_cost: float,
        at: float,
    ) -> None:
        self.last_interaction = LastInteraction(
            model=model,
            backend=backend,
            repo=repo,
            tokens_sent=prompt_tokens,
            tokens_received=completion_tokens,
            message_cost=message_cost,
            session_cost=session_cost,
            at=at,
        )

        current_month = self._month_key()
        event_month = self._month_key(at)
        if event_month != current_month:
            return

        if self.mtd.month != current_month:
            self.mtd = MtdStats(month=current_month)

        self.mtd.tokens_sent += prompt_tokens
        self.mtd.tokens_received += completion_tokens
        self.mtd.total_cost += message_cost
        self.mtd.messages += 1

    def snapshot(self) -> tuple[LastInteraction | None, MtdStats]:
        return self.last_interaction, self.mtd