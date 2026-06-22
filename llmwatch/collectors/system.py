from __future__ import annotations

import psutil

from llmwatch.formatters import bytes_human


def collect_memory() -> dict:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": vm.total,
        "used": vm.used,
        "available": vm.available,
        "percent": vm.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent,
    }


def collect_disk() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint in seen:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue
        seen.add(part.mountpoint)
        rows.append(
            {
                "device": part.device,
                "mount": part.mountpoint,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        )
    rows.sort(key=lambda r: r["used"], reverse=True)
    return rows[:4]