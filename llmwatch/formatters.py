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


def short_path(path: str, limit: int = 42) -> str:
    if not path:
        return ""
    home = str(__import__("pathlib").Path.home())
    if path.startswith(home):
        path = "~" + path[len(home) :]
    if len(path) <= limit:
        return path
    return "…" + path[-(limit - 1) :]


def short_cmd(cmdline: list[str] | None, limit: int = 48) -> str:
    if not cmdline:
        return ""
    text = " ".join(cmdline)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _mac_app_name(parts: list[str]) -> str | None:
    import re

    for part in parts:
        match = re.search(r"/([^/]+)\.app(?:/|$)", part)
        if match:
            return match.group(1)
    return None


def _flag_value(parts: list[str], flag: str) -> str | None:
    for index, part in enumerate(parts):
        if part == flag and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith(f"{flag}="):
            return part.split("=", 1)[1]
    return None


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1] if path else ""


def _clean_process_name(name: str) -> str:
    for suffix in (
        " Helper (Renderer)",
        " Helper (GPU)",
        " Helper",
        " Renderer",
        " Plugin",
    ):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _short_model_ref(raw: str) -> str:
    if not raw:
        return ""
    base = _basename(raw)
    if base.startswith("sha256-"):
        return base[:18]
    if "/" in raw and "/" not in base:
        return base
    return base


def process_label(
    name: str,
    cmdline: list[str] | None,
    *,
    limit: int = 40,
) -> str:
    parts = [part for part in (cmdline or []) if part]
    proc_name = _clean_process_name(name or "")

    app_name = _mac_app_name(parts)
    if app_name:
        return _truncate(app_name, limit)

    if not parts:
        return _truncate(proc_name, limit)

    executable = _basename(parts[0]).lower()
    args = parts[1:]

    if executable == "opencode":
        model = _flag_value(parts, "-m")
        if model:
            return _truncate(f"opencode {_short_model_ref(model)}", limit)
        return "opencode"

    if executable == "llama-server":
        return "ollama runner"

    if executable == "ollama":
        if args and args[0] == "serve":
            return "ollama serve"
        if args:
            return _truncate(f"ollama {args[0]}", limit)
        return "ollama"

    if executable in {"python", "python3", "python3.12", "python3.14"}:
        if "-m" in args:
            module_index = args.index("-m")
            if module_index + 1 < len(args):
                return _truncate(f"python -m {args[module_index + 1]}", limit)
        for arg in args:
            if arg.startswith("-"):
                continue
            script = _basename(arg)
            if script.endswith(".py"):
                return _truncate(f"python {script[:-3]}", limit)
            return _truncate(f"python {script}", limit)
        return "python"

    if executable == "node":
        for arg in args:
            if arg.startswith("-"):
                continue
            script = _basename(arg)
            if script.endswith((".js", ".mjs", ".cjs")):
                return _truncate(f"node {script}", limit)
            return _truncate(f"node {script}", limit)
        return "node"

    if executable in {"hermes", "aider", "composer", "grok", "llmwatch"}:
        return executable

    if proc_name and proc_name.lower() != executable:
        cleaned = _clean_process_name(proc_name)
        if cleaned and cleaned.lower() != executable:
            return _truncate(cleaned, limit)

    if args:
        first_arg = next((arg for arg in args if not arg.startswith("-")), "")
        if first_arg:
            return _truncate(f"{executable} {_basename(first_arg)}", limit)

    return _truncate(executable or proc_name, limit)