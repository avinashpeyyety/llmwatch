from __future__ import annotations

import time
from datetime import datetime

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from llmwatch.collectors.api_sessions import ApiDashboard, ApiSession
from llmwatch.collectors.api_stats_store import LastInteraction, MtdStats
from llmwatch.collectors.ollama import LlmRuntime
from llmwatch.formatters import bar, bytes_human, rate_human, short_path


def _status_text(status: str) -> Text:
    if status == "generating":
        return Text("● generating", style="bold green")
    return Text("○ idle", style="dim")


def render_memory_panel(mem: dict) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column()
    table.add_column(justify="right")
    table.add_row(
        "RAM",
        f"{bytes_human(mem['used'])} / {bytes_human(mem['total'])}  ({mem['percent']:.0f}%)",
    )
    table.add_row("", bar(mem["percent"], 30))
    if mem["swap_total"]:
        table.add_row(
            "Swap",
            f"{bytes_human(mem['swap_used'])} / {bytes_human(mem['swap_total'])}  ({mem['swap_percent']:.0f}%)",
        )
        table.add_row("", bar(mem["swap_percent"], 30))
    return Panel(table, title="Memory", border_style="cyan", box=box.ROUNDED)


def render_disk_panel(disks: list[dict]) -> Panel:
    table = Table(show_header=True, header_style="bold", box=box.SIMPLE_HEAVY, expand=True)
    table.add_column("Mount", style="cyan", no_wrap=True)
    table.add_column("Used", justify="right")
    table.add_column("Free", justify="right")
    table.add_column("Use%", justify="right")
    table.add_column("Bar", min_width=18)

    for disk in disks:
        table.add_row(
            disk["mount"],
            bytes_human(disk["used"]),
            bytes_human(disk["free"]),
            f"{disk['percent']:.0f}%",
            bar(disk["percent"], 16),
        )
    return Panel(table, title="Storage", border_style="blue", box=box.ROUNDED)


def render_process_panel(processes: list[dict]) -> Panel:
    table = Table(show_header=True, header_style="bold", box=box.SIMPLE_HEAVY, expand=True)
    table.add_column("PID", justify="right", style="dim", width=7)
    table.add_column("Process")
    table.add_column("RAM", justify="right", width=9)
    table.add_column("CPU", justify="right", width=6)
    table.add_column("Disk R", justify="right", width=9)
    table.add_column("Disk W", justify="right", width=9)

    for proc in processes:
        style = "bold yellow" if proc["llm"] else ""
        table.add_row(
            str(proc["pid"]),
            Text(proc["label"], style=style, overflow="ellipsis"),
            bytes_human(proc["rss"]),
            f"{proc['cpu']:.0f}%",
            rate_human(proc["read_bps"]) if proc["read_bps"] else "—",
            rate_human(proc["write_bps"]) if proc["write_bps"] else "—",
        )
    return Panel(
        table,
        title="Top processes (RAM + disk I/O)",
        border_style="magenta",
        box=box.ROUNDED,
    )


def _time_ago(ts: float) -> str:
    if ts <= 0:
        return "—"
    delta = max(0.0, time.time() - ts)
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _render_last_interaction(last: LastInteraction | None) -> RenderableType:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold yellow")
    table.add_column()
    table.add_row("Section", Text("Last interaction", style="bold yellow"))

    if not last:
        table.add_row("Info", Text("No API messages recorded yet", style="dim"))
        return table

    table.add_row("When", _time_ago(last.at))
    table.add_row("Backend", last.backend)
    table.add_row("Model", last.model)
    table.add_row(
        "Tokens",
        f"{last.tokens_sent:,} sent · {last.tokens_received:,} received",
    )
    table.add_row(
        "Cost",
        f"${last.message_cost:.4f} message · ${last.session_cost:.4f} session",
    )
    if last.repo:
        table.add_row("Repo", short_path(last.repo, 48))
    return table


def _render_mtd_stats(mtd: MtdStats) -> RenderableType:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold yellow")
    table.add_column()
    label = mtd.month or datetime.now().strftime("%Y-%m")
    table.add_row("Section", Text(f"Month to date ({label})", style="bold yellow"))
    table.add_row("Messages", f"{mtd.messages:,}")
    table.add_row(
        "Tokens",
        f"{mtd.tokens_sent:,} sent · {mtd.tokens_received:,} received",
    )
    table.add_row("Cost", f"${mtd.total_cost:.4f}")
    return table


def _render_active_session(session: ApiSession) -> RenderableType:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()

    table.add_row("Section", Text("Active session", style="bold yellow"))
    table.add_row("Backend", session.backend)
    table.add_row("Model", session.model)
    if session.status == "active":
        table.add_row("Status", Text("● active", style="bold cyan"))
    else:
        table.add_row("Status", _status_text(session.status))
    if session.stats_available:
        table.add_row(
            "Tokens",
            f"{session.tokens_sent:,} sent · {session.tokens_received:,} received",
        )
        if session.session_cost > 0 or session.last_message_cost > 0:
            table.add_row(
                "Cost",
                f"${session.last_message_cost:.4f} last · ${session.session_cost:.4f} session",
            )
    else:
        table.add_row(
            "Stats",
            Text("restart via aider-xai for live token/cost tracking", style="dim"),
        )
    if session.repo:
        table.add_row("Repo", short_path(session.repo, 48))
    table.add_row("PID", str(session.pid))
    return table


def render_api_panel(dashboard: ApiDashboard) -> Panel:
    sections: list[RenderableType] = []

    if dashboard.sessions:
        for session in dashboard.sessions:
            sections.append(_render_active_session(session))
            sections.append(Text(""))
    else:
        sections.append(Text("No active API session", style="dim"))
        sections.append(Text(""))

    sections.append(_render_last_interaction(dashboard.last_interaction))
    sections.append(Text(""))
    sections.append(_render_mtd_stats(dashboard.mtd))

    return Panel(
        Group(*sections),
        title="API sessions (Aider)",
        border_style="yellow",
        box=box.ROUNDED,
    )


def render_llm_panel(runtimes: list[LlmRuntime], ollama_up: bool) -> Panel:
    if not ollama_up and not runtimes:
        body = Text("Ollama not reachable. Start with: brew services start ollama", style="yellow")
        return Panel(body, title="Local LLMs", border_style="green", box=box.ROUNDED)

    if not runtimes:
        body = Text("No models loaded in memory. Run a model to see context and tok/s.", style="dim")
        return Panel(body, title="Local LLMs", border_style="green", box=box.ROUNDED)

    tables: list[RenderableType] = []
    for runtime in runtimes:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()

        table.add_row("Model", runtime.model)
        table.add_row("Status", _status_text(runtime.status))
        table.add_row(
            "Context",
            f"{runtime.prompt_tokens:,} prompt tok / {runtime.context_active:,} active / {runtime.context_max:,} max",
        )
        if runtime.status == "generating":
            table.add_row("Live gen", f"{runtime.gen_tps:.2f} tok/s  ({runtime.decoded_tokens:,} decoded)")
            if runtime.prompt_tps:
                table.add_row("Prompt speed", f"{runtime.prompt_tps:.2f} tok/s")
        elif runtime.last_gen_tps:
            table.add_row("Last gen", f"{runtime.last_gen_tps:.2f} tok/s")
        if runtime.ram_bytes:
            table.add_row("Model RAM", bytes_human(runtime.ram_bytes))
        if runtime.runner_pid:
            table.add_row("Runner", f"pid {runtime.runner_pid} · CPU {runtime.runner_cpu:.0f}%")
        if runtime.expires_at:
            table.add_row("Unloads", runtime.expires_at.replace("T", " ")[:19])

        tables.append(table)

    return Panel(
        Group(*tables),
        title="Local LLMs (Ollama)",
        border_style="green",
        box=box.ROUNDED,
    )


def render_dashboard(
    mem: dict,
    disks: list[dict],
    processes: list[dict],
    runtimes: list[LlmRuntime],
    api_dashboard: ApiDashboard,
    ollama_up: bool,
    refresh_s: float,
) -> Group:
    header = Text.assemble(
        ("llmwatch", "bold white"),
        "  ",
        (datetime.now().strftime("%H:%M:%S"), "dim"),
        "  ",
        (f"refresh {refresh_s:.1f}s", "dim"),
        "  ",
        ("q", "bold"),
        (" quit", "dim"),
    )
    return Group(
        header,
        "",
        render_memory_panel(mem),
        render_disk_panel(disks),
        render_llm_panel(runtimes, ollama_up),
        render_api_panel(api_dashboard),
        render_process_panel(processes),
    )