"""
shared/alerts_store.py
Simple append-only JSONL log for alerts, plus a heartbeat file so the
dashboard can show "is the bot actually running/checking the market".
No database server needed - just files, easy to inspect by hand too.
"""

import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ALERTS_PATH = BASE_DIR / "alerts_log.jsonl"
HEARTBEAT_PATH = BASE_DIR / "heartbeat.json"


def append_alert(alert: dict):
    alert["logged_at"] = time.time()
    with open(ALERTS_PATH, "a") as f:
        f.write(json.dumps(alert) + "\n")


def read_alerts(limit: int = 100) -> list:
    if not ALERTS_PATH.exists():
        return []
    with open(ALERTS_PATH, "r") as f:
        lines = f.readlines()
    alerts = [json.loads(line) for line in lines[-limit:]]
    alerts.reverse()  # newest first
    return alerts


def write_heartbeat(status: str, detail: str = ""):
    with open(HEARTBEAT_PATH, "w") as f:
        json.dump({"status": status, "detail": detail, "timestamp": time.time()}, f)


def read_heartbeat() -> dict:
    if not HEARTBEAT_PATH.exists():
        return {"status": "never_started", "detail": "", "timestamp": 0}
    with open(HEARTBEAT_PATH, "r") as f:
        return json.load(f)
