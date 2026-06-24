from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_STATS_FILE = Path.home() / ".config/opencode/api-stats.json"


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
    """Legacy stats store — OpenCode MTD is computed live from opencode.db."""

    stats_file: Path = DEFAULT_STATS_FILE
    last_interaction: LastInteraction | None = None
    mtd: MtdStats = field(default_factory=MtdStats)

    def load(self) -> None:
        self.mtd = MtdStats(month=datetime.now().strftime("%Y-%m"))

    def save(self) -> None:
        return

    def snapshot(self) -> tuple[LastInteraction | None, MtdStats]:
        return self.last_interaction, self.mtd