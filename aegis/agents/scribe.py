"""Scribe agent: closes the incident with a postmortem draft and a message for the team.

A model may write the postmortem's story, but what was done, and the message that leaves the room, come from the
record only. A real 7B model once told the team a fix had been applied when the defender had blocked it.
"""

import re
import time

from pydantic import BaseModel, Field

from .. import store
from ..security import policy
from .base import brain, pace, say

PROMPT = (
    "You are the scribe agent. Write a short postmortem in Markdown with the headings Summary, Timeline, "
    "Root cause, What was done and Follow-ups. Under What was done, copy what_was_done exactly. "
    "Use only facts from the data. Do not invent numbers, names, times or actions."
)

WHAT_WAS_DONE = {
    "resolved": "{by} approved the plan. Aegis did exactly that and nothing else: {action}. The verifier then confirmed the service recovered.",
    "not_resolved": "{by} approved the plan and it was applied ({action}), but the service did not recover. The incident needs a human owner.",
    "rejected": "{by} said no-go, so nothing was changed. Note left with the decision: {note}",
    "escalated": "Aegis changed nothing. {reason} The on-call engineer should take it from here.",
}
UPDATE = {
    "resolved": "Update on {title}: the {service} service has recovered. Cause: {root} Fix: we chose to {action}, approved by {by}. A postmortem draft is ready.",
    "not_resolved": "Update on {title}: a fix was applied to {service} but it has not recovered yet. An engineer is taking over. Next update in 15 minutes.",
    "rejected": "Update on {title}: the proposed fix for {service} was not approved, so nothing was changed. An engineer is investigating by hand. Next update in 15 minutes.",
    "escalated": "Update on {title}: {service} is still affected. Likely cause: {root} The fix needs a change only a human may make. The on-call engineer has been paged.",
}
CLOSING = {  # what the voice says at the end
    "resolved": "Fix applied and verified. The {service} service has recovered. I have drafted the update for the team.",
    "not_resolved": "I applied the fix, but the {service} service has not recovered. Please take over. The details are on screen.",
    "rejected": "Understood. Nothing was changed. I have written up what we know for whoever picks this up.",
    "escalated": "This needs a change I am not allowed to make, so I have changed nothing. Please take over. My findings are on screen.",
}
FOLLOW_UPS = {
    "feature_flag": [
        "Find out who or what switched the flag on, and why nothing stopped it.",
        "Add an alert for failure flags being switched on in this environment.",
    ],
    "deploy": ["Find out why the release passed its checks.", "Add this failure to the release tests."],
}


class Report(BaseModel):
    postmortem: str = Field(description="Markdown with the headings Summary, Timeline, Root cause, What was done, Follow-ups")


def outcome_of(state: dict) -> str:
    if state.get("decision", {}).get("decision") == "no-go":
        return "rejected"
    if state["defender"]["verdict"] == "block" or state["plan"]["action"] == "escalate":
        return "escalated"
    return "resolved" if state.get("verification", {}).get("recovered") else "not_resolved"


def _fill(template: str, context: dict) -> str:
    plan, decision = context["plan"], context.get("decision") or {}
    root = plan["root_cause"].strip()
    root = root if root.endswith((".", "!", "?")) else f"{root}."  # models do not always end with a full stop
    reason = plan["reason"]
    if context.get("blocked_because"):  # the plan's own reason argues for a fix that never ran; say why it did not
        reason = f"The defender blocked the proposed fix ({policy.describe(plan)}): {'; '.join(context['blocked_because'])}."
    return template.format(
        title=context["title"],
        service=context["incident"]["service"],
        root=root,
        reason=reason,
        action=policy.describe(plan),
        by=decision.get("by") or "The approver",
        note=decision.get("note") or "(none)",
    )


def offline(context: dict) -> Report:
    outcome = context["outcome"]
    follow_ups = FOLLOW_UPS.get((context.get("suspect") or {}).get("type", ""), ["Review this incident with the service owner."])
    postmortem = "\n".join(
        [
            f"# Postmortem draft: {context['title']}",
            "",
            "## Summary",
            f"{context['incident']['summary']} Outcome: {outcome.replace('_', ' ')}.",
            "",
            "## Timeline",
            *context["timeline"],
            "",
            "## Root cause",
            context["plan"]["root_cause"],
            "",
            "## What was done",
            _fill(WHAT_WAS_DONE[outcome], context),
            "",
            "## Follow-ups",
            *[f"- {item}" for item in follow_ups],
        ]
    )
    return Report(postmortem=postmortem)


def pin_what_was_done(postmortem: str, facts: str) -> str:
    """Replace whatever the model wrote under "What was done" with the record. Add the section if it is missing."""
    section = re.compile(r"^(#+[ \t]*What was done[ \t]*)$.*?(?=^#+[ \t]|\Z)", re.M | re.S | re.I)
    if section.search(postmortem):
        return section.sub(lambda m: f"{m.group(1)}\n{facts}\n\n", postmortem, count=1).rstrip() + "\n"
    return f"{postmortem.rstrip()}\n\n## What was done\n{facts}\n"


def run(state: dict) -> dict:
    incident = store.INCIDENTS[state["incident_id"]]
    outcome = outcome_of(state)
    context = {
        "title": incident.title,
        "outcome": outcome,
        "incident": state["triage"],
        "plan": state["plan"],
        "defender": state["defender"]["verdict"],
        "decision": state.get("decision"),
        "execution": state.get("execution"),
        "verification": state.get("verification"),
        "suspect": next((f["suspect"] for f in state["findings"] if f.get("suspect")), None),
        "blocked_because": [c["check"] for c in state["defender"]["checks"] if not c["ok"]]
        if state["defender"]["verdict"] == "block"
        else [],
        "timeline": [
            f"- {time.strftime('%H:%M:%S', time.localtime(e['ts']))} {e['agent']}: {e['text']}" for e in incident.events
        ],
    }
    context["what_was_done"] = _fill(WHAT_WAS_DONE[outcome], context)
    answer, source = brain(state).ask(PROMPT, Report, context, offline)
    report = {
        "outcome": outcome,
        "postmortem": pin_what_was_done(answer.postmortem, context["what_was_done"]),
        "stakeholder_update": _fill(UPDATE[outcome], context),  # leaves the room, so it states only what the record shows
        "closing": CLOSING[outcome].format(service=state["triage"]["service"].replace("-", " ")),
    }
    pace()
    say(
        state,
        "scribe",
        f"Incident closed: {outcome.replace('_', ' ')}. Postmortem draft and team update are ready.",
        "done",
        {"answered_by": source},
    )
    store.finish(incident.id, outcome, report)
    return {"report": report}
