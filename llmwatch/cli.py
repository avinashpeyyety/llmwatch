from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests
from rich.console import Console
from rich.live import Live

from llmwatch import __version__
from llmwatch.collectors.api_sessions import ApiSessionMonitor
from llmwatch.collectors.ollama import OllamaMonitor
from llmwatch.collectors.processes import ProcessSampler
from llmwatch.collectors.system import collect_disk, collect_memory
from llmwatch.tui import render_dashboard


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="llmwatch",
        description="Visual Mac terminal monitor for RAM, storage, and local LLM performance.",
    )
    parser.add_argument("--version", action="version", version=f"llmwatch {__version__}")
    parser.add_argument(
        "--refresh",
        type=float,
        default=1.0,
        help="Refresh interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--ollama-host",
        default=None,
        help="Ollama API base URL (default: $OLLAMA_HOST or http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--ollama-log",
        default="/opt/homebrew/var/log/ollama.log",
        help="Path to ollama serve log for live tok/s",
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=12,
        help="Number of top RAM processes to show",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print one snapshot and exit (no live TUI)",
    )
    parser.add_argument(
        "--no-screen",
        action="store_true",
        help="Disable full-screen TUI mode (use in embedded terminals)",
    )
    return parser.parse_args(argv)


def ollama_reachable(host: str) -> bool:
    try:
        requests.get(f"{host}/api/ps", timeout=0.4)
        return True
    except requests.RequestException:
        return False


def collect_snapshot(args: argparse.Namespace) -> tuple:
    host = args.ollama_host or OllamaMonitor().host
    sampler = ProcessSampler()
    ollama = OllamaMonitor(host=host, log_path=Path(args.ollama_log))
    api_sessions = ApiSessionMonitor()
    mem = collect_memory()
    disks = collect_disk()
    processes = sampler.collect(top_n=args.processes, interval=args.refresh)
    runtimes = ollama.collect()
    api_dashboard = api_sessions.collect()
    ollama_up = ollama_reachable(host)
    return mem, disks, processes, runtimes, api_dashboard, ollama_up


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console()
    use_screen = (
        not args.no_screen
        and sys.stdout.isatty()
        and sys.stdin.isatty()
        and not args.once
    )

    if args.once:
        try:
            mem, disks, processes, runtimes, api_dashboard, ollama_up = collect_snapshot(args)
        except Exception as exc:
            from llmwatch.collectors.api_sessions import ApiDashboard

            mem = collect_memory()
            disks = collect_disk()
            processes = []
            runtimes = []
            api_dashboard = ApiDashboard(error=str(exc))
            ollama_up = False
        console.print(
            render_dashboard(
                mem=mem,
                disks=disks,
                processes=processes,
                runtimes=runtimes,
                api_dashboard=api_dashboard,
                ollama_up=ollama_up,
                refresh_s=args.refresh,
            )
        )
        return 0

    if use_screen:
        console.print("[dim]Starting llmwatch...[/dim]")

    host = args.ollama_host or OllamaMonitor().host
    sampler = ProcessSampler()
    ollama = OllamaMonitor(host=host, log_path=Path(args.ollama_log))
    api_sessions = ApiSessionMonitor()

    try:
        with Live(
            console=console,
            refresh_per_second=4,
            screen=use_screen,
        ) as live:
            while True:
                try:
                    mem = collect_memory()
                    disks = collect_disk()
                    processes = sampler.collect(
                        top_n=args.processes,
                        interval=args.refresh,
                    )
                    runtimes = ollama.collect()
                    api_dashboard = api_sessions.collect()
                    ollama_up = ollama_reachable(host)
                except Exception as exc:
                    from llmwatch.collectors.api_sessions import ApiDashboard

                    mem = collect_memory()
                    disks = collect_disk()
                    processes = []
                    runtimes = []
                    api_dashboard = ApiDashboard(error=str(exc))
                    ollama_up = False

                live.update(
                    render_dashboard(
                        mem=mem,
                        disks=disks,
                        processes=processes,
                        runtimes=runtimes,
                        api_dashboard=api_dashboard,
                        ollama_up=ollama_up,
                        refresh_s=args.refresh,
                    )
                )
                time.sleep(max(args.refresh, 0.2))
    except KeyboardInterrupt:
        if use_screen:
            console.clear()
        console.print("[dim]llmwatch stopped[/dim]")
        return 0


if __name__ == "__main__":
    sys.exit(main())