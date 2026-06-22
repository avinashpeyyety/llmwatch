from __future__ import annotations

from datetime import datetime

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from llmwatch.collectors.ollama import LlmRuntime
from llmwatch.formatters import bar, bytes_human, rate_human


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
        render_process_panel(processes),
    )