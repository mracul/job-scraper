"""
Run state management utilities.
"""

import json
from datetime import datetime
from pathlib import Path

from ui.constants import RUN_STATE_FILE


def _read_run_state_raw() -> dict | None:
    """Read persisted run state without validating PID liveness."""
    if not RUN_STATE_FILE.exists():
        return None
    try:
        with open(RUN_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_run_state(pid: int, log_file: str) -> None:
    """Persist running process info to disk."""
    RUN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    create_time = None
    cmdline: list[str] | None = None
    try:
        import psutil

        proc = psutil.Process(pid)
        try:
            create_time = float(proc.create_time())
        except Exception:
            create_time = None
        try:
            cmdline = [str(x) for x in (proc.cmdline() or [])]
        except Exception:
            cmdline = None
    except Exception:
        create_time = None
        cmdline = None

    payload = {
        "pid": pid,
        "log_file": log_file,
        "started": datetime.now().isoformat(),
        "create_time": create_time,
        "cmd": cmdline,
    }
    with open(RUN_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def clear_run_state() -> None:
    """Remove persisted run state."""
    if RUN_STATE_FILE.exists():
        RUN_STATE_FILE.unlink(missing_ok=True)


def load_run_state() -> dict | None:
    """Load persisted run state and verify process is still running."""
    data = _read_run_state_raw()
    if not data:
        return None
    pid = data.get("pid")
    if pid:
        import psutil
        if psutil.pid_exists(pid):
            # Protect against PID reuse by verifying create_time when available.
            try:
                proc = psutil.Process(int(pid))
                stored_ct = data.get("create_time")
                if stored_ct is not None:
                    try:
                        stored_ct_f = float(stored_ct)
                        live_ct_f = float(proc.create_time())
                        # create_time is in seconds since epoch; allow small clock/float tolerance.
                        if abs(live_ct_f - stored_ct_f) > 2.0:
                            return None
                    except Exception:
                        # If parsing fails, fall back to liveness only.
                        pass
            except Exception:
                # If we can't inspect the process, fall back to liveness only.
                pass

            return data
    return None