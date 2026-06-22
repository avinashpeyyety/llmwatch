from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import psutil
import requests

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_LOG = Path("/opt/homebrew/var/log/ollama.log")

TG_RE = re.compile(r"n_decoded\s*=\s*(\d+),\s*tg\s*=\s*([\d.]+)\s*t/s")
PROMPT_CTX_RE = re.compile(
    r"n_ctx_slot\s*=\s*(\d+).*?task\.n_tokens\s*=\s*(\d+)"
)
PROMPT_TPS_RE = re.compile(
    r"prompt eval time\s*=.*?([\d.]+)\s*tokens per second"
)
EVAL_TPS_RE = re.compile(r"eval time\s*=.*?([\d.]+)\s*tokens per second")
TOTAL_TOKENS_RE = re.compile(r"eval time\s*=.*?/\s*(\d+)\s*tokens")
IDLE_RE = re.compile(r"all slots are idle")


@dataclass
class LlmRuntime:
    model: str = ""
    status: str = "idle"
    context_max: int = 0
    context_active: int = 0
    prompt_tokens: int = 0
    decoded_tokens: int = 0
    gen_tps: float = 0.0
    prompt_tps: float = 0.0
    last_gen_tps: float = 0.0
    ram_bytes: int = 0
    expires_at: str = ""
    runner_pid: int = 0
    runner_cpu: float = 0.0
    source: str = "ollama"


@dataclass
class OllamaMonitor:
    host: str = DEFAULT_HOST
    log_path: Path = DEFAULT_LOG
    _log_offset: int = 0
    _runtime: LlmRuntime = field(default_factory=LlmRuntime)
    _seen_log: bool = False

    def _ensure_log_offset(self) -> None:
        if self._seen_log or not self.log_path.exists():
            return
        self._log_offset = self.log_path.stat().st_size
        self._seen_log = True

    def _poll_log(self) -> None:
        self._ensure_log_offset()
        if not self.log_path.exists():
            return
        with self.log_path.open("r", errors="replace") as handle:
            handle.seek(self._log_offset)
            chunk = handle.read()
            self._log_offset = handle.tell()

        for line in chunk.splitlines():
            if IDLE_RE.search(line):
                self._runtime.status = "idle"
                self._runtime.gen_tps = 0.0
                continue

            match = TG_RE.search(line)
            if match:
                self._runtime.status = "generating"
                self._runtime.decoded_tokens = int(match.group(1))
                self._runtime.gen_tps = float(match.group(2))
                continue

            match = PROMPT_CTX_RE.search(line)
            if match:
                self._runtime.context_active = int(match.group(1))
                self._runtime.prompt_tokens = int(match.group(2))
                self._runtime.status = "generating"
                continue

            match = PROMPT_TPS_RE.search(line)
            if match:
                self._runtime.prompt_tps = float(match.group(1))
                continue

            match = EVAL_TPS_RE.search(line)
            if match:
                self._runtime.last_gen_tps = float(match.group(1))
                self._runtime.status = "idle"
                self._runtime.gen_tps = 0.0
                continue

            match = TOTAL_TOKENS_RE.search(line)
            if match:
                self._runtime.decoded_tokens = int(match.group(1))

    def _fetch_ps(self) -> list[dict]:
        try:
            response = requests.get(f"{self.host}/api/ps", timeout=0.4)
            response.raise_for_status()
            return response.json().get("models", [])
        except requests.RequestException:
            return []

    def _runner_processes(self) -> list[psutil.Process]:
        runners: list[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
                if "llama-server" in name or "llama-server" in cmd:
                    runners.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return runners

    def collect(self) -> list[LlmRuntime]:
        self._poll_log()
        models = self._fetch_ps()
        runners = self._runner_processes()

        if not models and self._runtime.gen_tps <= 0 and self._runtime.status == "idle":
            if not runners:
                return []
            runtime = LlmRuntime(
                model="llama-server",
                status=self._runtime.status,
                gen_tps=self._runtime.gen_tps,
                prompt_tps=self._runtime.prompt_tps,
                last_gen_tps=self._runtime.last_gen_tps,
                decoded_tokens=self._runtime.decoded_tokens,
                prompt_tokens=self._runtime.prompt_tokens,
                context_active=self._runtime.context_active,
                source="runner",
            )
            if runners:
                proc = runners[0]
                runtime.runner_pid = proc.pid
                try:
                    runtime.runner_cpu = proc.cpu_percent(None)
                    runtime.ram_bytes = proc.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return [runtime]

        results: list[LlmRuntime] = []
        for index, model in enumerate(models):
            runtime = LlmRuntime(
                model=model.get("name") or model.get("model") or "unknown",
                status=self._runtime.status,
                context_max=int(model.get("context_length") or 0),
                context_active=self._runtime.context_active or int(model.get("context_length") or 0),
                prompt_tokens=self._runtime.prompt_tokens,
                decoded_tokens=self._runtime.decoded_tokens,
                gen_tps=self._runtime.gen_tps,
                prompt_tps=self._runtime.prompt_tps,
                last_gen_tps=self._runtime.last_gen_tps,
                ram_bytes=int(model.get("size_vram") or model.get("size") or 0),
                expires_at=model.get("expires_at") or "",
                source="ollama",
            )
            if index < len(runners):
                proc = runners[index]
                runtime.runner_pid = proc.pid
                try:
                    runtime.runner_cpu = proc.cpu_percent(None)
                    cmd = proc.cmdline()
                    for i, arg in enumerate(cmd):
                        if arg == "-c" and i + 1 < len(cmd):
                            runtime.context_max = max(runtime.context_max, int(cmd[i + 1]))
                except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
                    pass
            results.append(runtime)
        return results