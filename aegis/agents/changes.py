"""Change agent: asks "what changed just before this started?" and names the main suspect."""

from pydantic import BaseModel, Field

from ..connectors import get_connector
from .base import brain, pace, say

PROMPT = (
    "You are the change agent. From the list of recent changes, pick the one most likely to have caused the "
    "incident on the named service, or none. A change to the same service shortly before the alert is the "
    "strongest suspect. Give the id of the change exactly as listed."
)
LABELS = {"feature_flag": "Feature flag", "deploy": "Release", "config": "Config change"}


class ChangeReport(BaseModel):
    suspect_id: str = Field(description="id of the suspected change, or an empty string if none stands out")
    headline: str = Field(description="one sentence naming the suspect and when it happened")


def describe(change: dict) -> str:
    label = LABELS.get(change.get("type", ""), "Change")
    when = f"{change['minutes_before_alert']} minutes before the alert"
    return f"{label} {change['target']}: {change['detail']}, {when} (by {change.get('by', 'unknown')})."


def offline(context: dict) -> ChangeReport:
    recent = sorted((c for c in context["changes"] if c["minutes_before_alert"] <= 30), key=lambda c: c["minutes_before_alert"])
    same_service = [c for c in recent if c.get("service") == context["service"]]
    suspect = (same_service or recent or [None])[0]
    if suspect is None:
        return ChangeReport(suspect_id="", headline="Nothing changed in the 30 minutes before the alert.")
    return ChangeReport(suspect_id=suspect["id"], headline=describe(suspect))


def run(state: dict) -> dict:
    service = state["triage"]["service"]
    try:
        changes = get_connector().changes(service)
    except Exception as err:  # noqa: BLE001 - not being able to list changes is itself worth telling the room
        say(state, "changes", f"I could not read the change history: {err}", "error")
        return {"findings": [{"agent": "changes", "headline": "Change history could not be read.", "suspect": None}]}

    answer, source = brain(state).ask(PROMPT, ChangeReport, {"service": service, "changes": changes}, offline)
    suspect = next((c for c in changes if c["id"] == answer.suspect_id), None)  # only a change that really exists counts
    pace()
    say(state, "changes", answer.headline, data={"suspect": suspect, "changes_checked": len(changes), "answered_by": source})
    return {"findings": [{"agent": "changes", "headline": answer.headline, "suspect": suspect}]}
