#!/usr/bin/env python3
"""Capture a live llmwatch dashboard preview for the GitHub Pages site."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from llmwatch.collectors.ollama import OllamaMonitor
from llmwatch.collectors.processes import ProcessSampler
from llmwatch.collectors.system import collect_disk, collect_memory
from llmwatch.tui import render_dashboard

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    mem = collect_memory()
    disks = collect_disk()
    processes = ProcessSampler().collect(8)
    runtimes = OllamaMonitor().collect()

    console = Console(record=True, width=96)
    console.print(render_dashboard(mem, disks, processes, runtimes, True, 1.0))
    console.save_html(DOCS / "preview.html", clear=False)

    dark = (DOCS / "preview.html").read_text()
    dark = dark.replace(
        "body {\n    color: #000000;\n    background-color: #ffffff;\n}",
        "body {\n    color: #e8ecf4;\n    background-color: #0d1117;\n    margin: 0;\n    padding: 12px 14px;\n    overflow: hidden;\n}",
    )
    (DOCS / "preview-dark.html").write_text(dark)
    (DOCS / "preview.txt").write_text(console.export_text())
    print(f"Wrote {DOCS / 'preview.html'}")
    print(f"Wrote {DOCS / 'preview-dark.html'}")


if __name__ == "__main__":
    main()