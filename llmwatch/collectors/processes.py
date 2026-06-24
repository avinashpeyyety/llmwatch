from __future__ import annotations

import time
from dataclasses import dataclass, field

import psutil

from llmwatch.formatters import short_cmd


LLM_HINTS = (
    "ollama",
    "llama-server",
    "llama.cpp",
    "mlx",
    "lmstudio",
    "opencode",
    "node server",
    "control-server",
    "python",
)


@dataclass
class IoSample:
    read_bytes: int = 0
    write_bytes: int = 0
    at: float = field(default_factory=time.time)


class ProcessSampler:
    def __init__(self) -> None:
        self._io_prev: dict[int, IoSample] = {}
        self._cpu_ready = False

    def _prime_cpu(self) -> None:
        if self._cpu_ready:
            return
        for proc in psutil.process_iter():
            try:
                proc.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self._cpu_ready = True

    def collect(self, top_n: int = 12, interval: float = 1.0) -> list[dict]:
        self._prime_cpu()
        now = time.time()
        rows: list[dict] = []

        for proc in psutil.process_iter(["pid", "name", "username", "memory_info", "cmdline"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                if not mem:
                    continue
                rss = mem.rss
                if rss < 8 * 1024 * 1024:
                    continue

                read_bps = write_bps = 0.0
                try:
                    io = proc.io_counters()
                    prev = self._io_prev.get(proc.pid)
                    if prev:
                        dt = max(now - prev.at, 0.001)
                        read_bps = max(0, io.read_bytes - prev.read_bytes) / dt
                        write_bps = max(0, io.write_bytes - prev.write_bytes) / dt
                    self._io_prev[proc.pid] = IoSample(io.read_bytes, io.write_bytes, now)
                except (psutil.AccessDenied, AttributeError, psutil.NoSuchProcess):
                    pass

                cpu = proc.cpu_percent(None)
                cmdline = info.get("cmdline") or []
                name = info.get("name") or ""
                label = short_cmd(cmdline, 56) or name
                llm_related = any(h in label.lower() or h in name.lower() for h in LLM_HINTS)

                rows.append(
                    {
                        "pid": proc.pid,
                        "name": name,
                        "user": info.get("username") or "",
                        "rss": rss,
                        "cpu": cpu,
                        "read_bps": read_bps,
                        "write_bps": write_bps,
                        "label": label,
                        "llm": llm_related,
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        rows.sort(key=lambda r: r["rss"], reverse=True)
        return rows[:top_n]