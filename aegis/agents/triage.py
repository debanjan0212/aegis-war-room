"""Triage agent: reads the alert, says how bad it is and which service is hurt."""

from typing import Literal

from pydantic import BaseModel, Field

from ..connectors import safe_name
from ..security import injection
from .base import brain, pace, say

PROMPT = (
    "You are the triage agent. From the alert, decide the severity, name the affected service exactly as the "
    "alert names it, and write one plain sentence a manager would understand."
)
LEVELS = ("critical", "high", "medium", "low")


class Triage(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    service: str = Field(description="the affected service, exactly as named in the alert")
    summary: str = Field(description="one plain sentence")


def offline(context: dict) -> Triage:
    alert = context["alert"]
    severity = alert.get("severity") if alert.get("severity") in LEVELS else "high"
    return Triage(
        severity=severity, service=alert.get("service", ""), summary=alert.get("summary") or f"{alert.get('name')} is firing."
    )


def run(state: dict) -> dict:
    alert = dict(state["alert"])
    quarantined = []
    reasons = injection.scan(alert.get("summary", ""))
    if reasons:  # alert text is written by someone else too
        quarantined = [{"text": alert["summary"], "reasons": reasons, "source": "alert text"}]
        alert["summary"] = ""
        say(
            state,
            "triage",
            "The alert text looks like it carries instructions for an AI. I set it aside and used the labels only.",
            "warn",
        )

    answer, source = brain(state).ask(PROMPT, Triage, {"alert": alert}, offline)
    try:  # the alert's own label wins; a model's guess is only used when the alert has none
        service = safe_name(alert.get("service") or answer.service)
    except ValueError:
        service = "unknown"
    pace()
    say(state, "triage", f"{answer.severity.capitalize()} incident on {service}. {answer.summary}", data={"answered_by": source})
    return {"triage": {"severity": answer.severity, "service": service, "summary": answer.summary}, "quarantined": quarantined}
