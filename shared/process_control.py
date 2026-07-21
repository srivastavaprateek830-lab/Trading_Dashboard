"""
shared/process_control.py
Starts/stops alert_daemon.py as a background OS process from the dashboard,
so a non-technical user doesn't need a terminal for day-to-day use.
For serious 24/7 production use, running alert_daemon.py under systemd
instead (see README) is more robust - this is the convenient default.
"""

import subprocess
import sys
import os
import signal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PID_FILE = BASE_DIR / "daemon.pid"


def is_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # signal 0 = just check it exists, doesn't actually kill
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def start_daemon():
    if is_running():
        return
    log_path = BASE_DIR / "daemon.log"
    with open(log_path, "a") as log_file:
        proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "alert_daemon.py")],
            cwd=str(BASE_DIR),
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,  # survives the Streamlit process restarting
        )
    PID_FILE.write_text(str(proc.pid))


def stop_daemon():
    if not PID_FILE.exists():
        return
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except (ValueError, ProcessLookupError, PermissionError):
        pass
    finally:
        PID_FILE.unlink(missing_ok=True)
