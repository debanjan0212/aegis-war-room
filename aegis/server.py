"""The web API the screen talks to. Also serves the built screen itself from web/dist."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assistant, flow, store
from .agents import codeguard
from .brain import default_model, models
from .connectors import get_connector
from .security import drill
from .settings import ROOT, env
from .voices import list_voices

_scan: dict = {"status": "never run", "report": None}
log = logging.getLogger("aegis")


def watch_every() -> float:
    """Live mode only: how often (seconds) to look at the real system by itself. 0 = only when someone presses scan."""
    every = float(env("AEGIS_WATCH_EVERY", "0") or 0)
    return every if every > 0 and get_connector().name != "simulator" else 0


def _recently_handled(service: str, quiet: float) -> bool:
    """After a no-go, or while the numbers settle after a fix, the same alert must not reopen the room every few seconds."""
    last = [i.events[-1]["ts"] if i.events else i.created for i in store.INCIDENTS.values() if i.alert.get("service") == service]
    return bool(last) and time.time() - max(last) < quiet


def watch_once(quiet: float) -> list[str]:
    """One look at the live system. Opens an incident for anything unhealthy that is not already being handled."""
    alerts = [a for a in get_connector().detect() if not _recently_handled(a["service"], quiet)]
    return [_open(alert, default_model()).id for alert in alerts]


def _watch(every: float) -> None:
    """Look at the live system every few seconds and open an incident by itself when something is unhealthy."""
    quiet = float(env("AEGIS_WATCH_QUIET", "180"))  # seconds after an incident's last step before the same service may reopen
    complained = False
    while True:
        time.sleep(every)
        try:
            watch_once(quiet)
            complained = False
        except Exception as err:  # noqa: BLE001 - the watcher must keep watching, and say once (not every tick) why it cannot
            if not complained:
                log.warning("watcher cannot read the live system: %s", err)
            complained = True


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if every := watch_every():
        threading.Thread(target=_watch, args=(every,), daemon=True).start()
    yield


app = FastAPI(title="Aegis War Room", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


def guard(authorization: str = Header("")) -> None:
    """If AEGIS_API_TOKEN is set, every request that changes something must carry it."""
    token = env("AEGIS_API_TOKEN")
    if token and not hmac.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(401, "missing or wrong API token")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if int(request.headers.get("content-length") or 0) > 64_000:
        return StreamingResponse(iter(["request too large"]), status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:"
    return response


# --- what the screen needs to draw itself ------------------------------------
@app.get("/api/config")
def config() -> dict:
    connector = get_connector()
    scenarios = (
        [{"id": s["id"], "title": s["title"], "story": s["story"]} for s in connector.scenarios()]
        if connector.name == "simulator"
        else []
    )
    return {
        "assistant": env("AEGIS_ASSISTANT_NAME", "Aegis"),
        "operator": env("AEGIS_OPERATOR_NAME"),  # who the assistant greets; the screen asks once if this is empty
        "source": connector.name,
        "models": models(),
        "default_model": default_model(),
        "scenarios": scenarios,
        "voices": list_voices(),
        "watch_every": watch_every(),
    }


# --- incidents ---------------------------------------------------------------
class Trigger(BaseModel):
    scenario: str = Field(max_length=60)
    model: str = Field("", max_length=40)


class Decision(BaseModel):
    decision: str = Field(pattern="^(go|no-go)$")
    plan_hash: str = Field(max_length=64)
    by: str = Field("", max_length=80)
    note: str = Field("", max_length=500)


class ModelChoice(BaseModel):
    model: str = Field("", max_length=40)


def _model(wanted: str) -> str:
    wanted = wanted or default_model()
    entry = next((m for m in models() if m["id"] == wanted), None)
    if entry is None:
        raise HTTPException(400, f"unknown model '{wanted}'")
    if not entry["ready"]:
        raise HTTPException(400, f"{entry['label']} is not ready. Missing: {', '.join(entry['missing'])}")
    return wanted


def _open(alert: dict, model: str) -> store.Incident:
    """Start an incident, unless one is already open for the same service (alerts repeat)."""
    for incident in store.INCIDENTS.values():
        if incident.status in store.OPEN and incident.alert.get("service") == alert.get("service"):
            return incident
    return flow.start(alert, model)


def _normalise(raw: dict) -> dict:
    """Accept our own simple alert shape and the Alertmanager / Grafana webhook shape."""
    labels = raw.get("labels") if isinstance(raw.get("labels"), dict) else {}
    notes = raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {}
    return {
        "name": str(raw.get("name") or labels.get("alertname") or "Alert")[:120],
        "service": str(raw.get("service") or labels.get("service") or labels.get("service_name") or labels.get("job") or "")[:60],
        "severity": str(raw.get("severity") or labels.get("severity") or "high")[:20],
        "summary": str(raw.get("summary") or notes.get("summary") or notes.get("description") or "")[:2000],
    }


@app.post("/api/incidents/trigger", dependencies=[Depends(guard)])
def trigger(body: Trigger) -> dict:
    connector = get_connector()
    if connector.name != "simulator":
        raise HTTPException(400, "scenarios only exist in the simulator")
    if body.scenario not in {s["id"] for s in connector.scenarios()}:
        raise HTTPException(404, "no such scenario")
    return {"id": _open(connector.trigger(body.scenario), _model(body.model)).id}


@app.post("/api/incidents/scan-live", dependencies=[Depends(guard)])
def scan_live(body: ModelChoice) -> dict:
    model = _model(body.model)
    try:
        alerts = get_connector().detect()
    except Exception as err:  # noqa: BLE001 - say what is wrong on screen instead of a bare 500
        raise HTTPException(502, f"Cannot read the live system. Is the demo shop running? ({type(err).__name__})") from err
    return {"ids": [_open(alert, model).id for alert in alerts]}


@app.post("/api/alerts", dependencies=[Depends(guard)])
def alerts(body: dict) -> dict:
    """Webhook for Alertmanager, Grafana or anything that can POST JSON."""
    sent = body.get("alerts", [body])
    firing = (
        [a for a in sent if isinstance(a, dict) and a.get("status", "firing") == "firing"][:5] if isinstance(sent, list) else []
    )
    model = _model("")
    return {"ids": [_open(_normalise(alert), model).id for alert in firing]}


@app.get("/api/incidents")
def incidents() -> list[dict]:
    rows = sorted(store.INCIDENTS.values(), key=lambda i: i.created, reverse=True)
    return [
        {"id": i.id, "title": i.title, "status": i.status, "created": i.created, "service": i.alert.get("service", "")}
        for i in rows
    ]


def _find(incident_id: str) -> store.Incident:
    if incident_id not in store.INCIDENTS:
        raise HTTPException(404, "no such incident")
    return store.INCIDENTS[incident_id]


@app.get("/api/incidents/{incident_id}")
def incident(incident_id: str) -> dict:
    return _find(incident_id).public()


@app.get("/api/incidents/{incident_id}/stream")
async def stream(incident_id: str, request: Request) -> StreamingResponse:
    """Live feed (server-sent events): one 'step' per agent message, 'status' whenever the state changes."""
    current = _find(incident_id)
    resume_after = request.headers.get("last-event-id", "")
    sent = int(resume_after) + 1 if resume_after.isdigit() else 0

    async def feed():
        nonlocal sent
        last = None
        while True:
            for event in current.events[sent:]:
                yield f"id: {event['seq']}\nevent: step\ndata: {json.dumps(event, default=str)}\n\n"
                sent += 1
            now = (current.status, tuple(current.working))
            if now != last:
                last = now
                snapshot = {"status": current.status, "gate": current.gate, "result": current.result, "working": list(now[1])}
                yield f"event: status\ndata: {json.dumps(snapshot)}\n\n"
            if current.status not in store.OPEN and sent >= len(current.events):
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(feed(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/incidents/{incident_id}/decision", dependencies=[Depends(guard)])
def decision(incident_id: str, body: Decision) -> dict:
    _find(incident_id)
    try:
        flow.decide(incident_id, body.decision, body.plan_hash, body.by, body.note)
    except ValueError as err:
        raise HTTPException(409, str(err)) from err
    return {"ok": True}


# --- talking to Aegis ----------------------------------------------------------
class Ask(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    model: str = Field("", max_length=40)


@app.post("/api/assistant", dependencies=[Depends(guard)])
def talk(body: Ask) -> dict:
    """What you said, in your own words, becomes one command and a reply. It can never approve or reject a fix."""
    wanted = body.model or default_model()
    ready = any(m["id"] == wanted and m["ready"] for m in models())
    return assistant.answer(body.text, wanted if ready else "offline")


# --- security ----------------------------------------------------------------
@app.post("/api/security/scan", dependencies=[Depends(guard)])
def security_scan(body: ModelChoice) -> dict:
    if _scan["status"] == "running":
        return {"status": "running"}
    model = _model(body.model)

    def work():
        try:
            _scan.update(status="done", report=codeguard.scan(model=model))
        except Exception as err:  # noqa: BLE001 - the screen must learn that the scan broke
            _scan.update(status=f"failed: {err}")

    _scan["status"] = "running"
    threading.Thread(target=work, daemon=True).start()
    return {"status": "running"}


@app.get("/api/security/report")
def security_report() -> dict:
    return _scan


@app.post("/api/security/drill", dependencies=[Depends(guard)])
def security_drill() -> list[dict]:
    return drill.run()


@app.get("/api/security/audit")
def security_audit() -> dict:
    ok, detail = store.verify_audit()
    return {"ok": ok, "detail": detail}


# --- the screen --------------------------------------------------------------
_dist = ROOT / "web" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
