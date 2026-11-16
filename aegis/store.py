"""Incidents, their live event feed, and the audit log.

Everything an agent says or does goes through emit(). It lands in two places:
the incident's event list (what the screen shows) and the audit log on disk.
Each audit line carries the hash of the line before it, so editing or deleting
a line later breaks the chain and verify_audit() reports it.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .settings import ROOT, env

OPEN = {"investigating", "awaiting_decision", "executing"}


@dataclass
class Incident:
    id: str
    title: str
    model: str
    alert: dict
    status: str = "investigating"
    created: float = field(default_factory=time.time)
    events: list = field(default_factory=list)
    gate: dict | None = None  # what the human is being asked to approve
    result: dict = field(default_factory=dict)
    working: list = field(default_factory=list)  # agents busy right now, so the screen can show who works and who sleeps

    def public(self) -> dict:
        return asdict(self)


INCIDENTS: dict[str, Incident] = {}
LISTENERS: list = []  # functions called with every new event (the terminal demo prints them)
_lock = threading.Lock()
_last_hash: dict[str, str] = {}


def start_work(incident_id: str, agent: str) -> None:
    with _lock:
        if agent not in INCIDENTS[incident_id].working:
            INCIDENTS[incident_id].working.append(agent)


def end_work(incident_id: str, agent: str) -> None:
    with _lock:
        if agent in INCIDENTS[incident_id].working:
            INCIDENTS[incident_id].working.remove(agent)


def create(alert: dict, model: str) -> Incident:
    incident = Incident(id=uuid.uuid4().hex[:8], title=alert.get("name", "Incident"), model=model, alert=alert)
    with _lock:
        INCIDENTS[incident.id] = incident
    emit(incident.id, "aegis", f"Incident opened for alert {incident.title}.", "open", {"alert": alert, "model": model})
    return incident


def emit(incident_id: str, agent: str, text: str, kind: str = "say", data: dict | None = None) -> None:
    """Record one step. kind is one of: open, say, warn, block, ask, decision, action, done, error."""
    with _lock:
        incident = INCIDENTS[incident_id]
        event = {"seq": len(incident.events), "ts": time.time(), "agent": agent, "kind": kind, "text": text, "data": data or {}}
        incident.events.append(event)
        _append_audit({"incident": incident_id, **event})
    for listener in LISTENERS:
        listener(event)


def ask(incident_id: str, gate: dict, text: str) -> None:
    """Put the incident on hold for the human: this is the go / no-go moment."""
    INCIDENTS[incident_id].gate = gate
    INCIDENTS[incident_id].status = "awaiting_decision"
    emit(incident_id, "aegis", text, "ask", gate)


def finish(incident_id: str, status: str, result: dict) -> None:
    INCIDENTS[incident_id].result = result
    INCIDENTS[incident_id].status = status


def audit_path() -> Path:
    return Path(env("AEGIS_AUDIT_LOG") or ROOT / "audit.log.jsonl")


def _digest(record: dict) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()


def _append_audit(record: dict, path: Path | None = None) -> None:
    path = path or audit_path()
    key = str(path)
    if key not in _last_hash:
        lines = path.read_text().splitlines() if path.exists() else []
        _last_hash[key] = json.loads(lines[-1])["hash"] if lines else "0" * 64
    body = {**record, "prev": _last_hash[key]}
    body["hash"] = _digest(body)
    with path.open("a") as handle:
        handle.write(json.dumps(body, sort_keys=True, default=str) + "\n")
    _last_hash[key] = body["hash"]


def verify_audit(path: Path | None = None) -> tuple[bool, str]:
    """Walk the audit log and confirm no line was changed, removed or reordered."""
    path = path or audit_path()
    if not path.exists():
        return True, "no audit log yet"
    prev = "0" * 64
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        record = json.loads(line)
        claimed = record.pop("hash")
        if record.get("prev") != prev or _digest(record) != claimed:
            return False, f"line {number} does not match the chain"
        prev = claimed
    return True, f"{number} lines verified" if prev != "0" * 64 else "empty log"
