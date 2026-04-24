from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

_MAX_PROCS = 20


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _cpu() -> str:
    import psutil
    overall = psutil.cpu_percent(interval=0.5)
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    freq = psutil.cpu_freq()
    cores = f"logical={psutil.cpu_count()} physical={psutil.cpu_count(logical=False)}"
    freq_str = f"{freq.current:.0f}MHz (max {freq.max:.0f}MHz)" if freq else "unknown"
    core_str = "  ".join(f"core{i}:{p}%" for i, p in enumerate(per_core))
    return f"CPU: {overall}% overall | {cores} | freq {freq_str}\n{core_str}"


def _memory() -> str:
    import psutil
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return (
        f"RAM:  total={_human(vm.total)}  used={_human(vm.used)}  free={_human(vm.available)}  {vm.percent}%\n"
        f"Swap: total={_human(sw.total)}  used={_human(sw.used)}  free={_human(sw.free)}  {sw.percent}%"
    )


def _disk(path: str) -> str:
    import psutil
    try:
        usage = psutil.disk_usage(path)
    except Exception as e:
        return f"disk error: {e}"
    parts = psutil.disk_partitions()
    lines = [f"Disk ({path}): total={_human(usage.total)}  used={_human(usage.used)}  free={_human(usage.free)}  {usage.percent}%"]
    lines.append("Partitions:")
    for p in parts:
        lines.append(f"  {p.device} → {p.mountpoint} [{p.fstype}]")
    return "\n".join(lines)


def _processes(limit: int) -> str:
    import psutil
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
    lines = [f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'STATUS':<12} NAME"]
    for p in procs[:limit]:
        lines.append(
            f"{p['pid']:<8} {(p['cpu_percent'] or 0):<8.1f} {(p['memory_percent'] or 0):<8.2f} "
            f"{(p['status'] or ''):<12} {p['name'] or ''}"
        )
    return "\n".join(lines)


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    metric = call.args.get("metric", "all").strip().lower()
    path = call.args.get("path", "/") or "/"
    limit = int(call.args.get("limit", _MAX_PROCS))

    try:
        import psutil  # noqa: F401
    except ImportError:
        return _result(call.id, error="psutil is not installed — run: pip install psutil", start=start)

    try:
        if metric == "cpu":
            output = _cpu()
        elif metric == "memory":
            output = _memory()
        elif metric == "disk":
            output = _disk(path)
        elif metric == "processes":
            output = _processes(limit)
        else:
            output = "\n\n".join([_cpu(), _memory(), _disk(path), _processes(limit)])
    except Exception as e:
        return _result(call.id, error=str(e), start=start)

    return _result(call.id, output=output, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "system.info"
DESCRIPTION = "Query system metrics. metric can be: cpu, memory, disk, processes, or all (default). Use to monitor system health or diagnose performance issues."
PARAMETERS = {
    "metric":  {"type": "string",  "required": False, "default": "all"},
    "path":    {"type": "string",  "required": False, "default": "/"},
    "limit":   {"type": "integer", "required": False, "default": 20},
}
