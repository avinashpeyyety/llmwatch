def bytes_human(n: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def rate_human(n: float) -> str:
    return f"{bytes_human(n)}/s"


def bar(pct: float, width: int = 24) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round((pct / 100) * width))
    return "█" * filled + "░" * (width - filled)


def short_cmd(cmdline: list[str] | None, limit: int = 48) -> str:
    if not cmdline:
        return ""
    text = " ".join(cmdline)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"