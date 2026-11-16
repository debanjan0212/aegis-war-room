"""Runbook agent: finds the team's written procedure that best fits what the others found."""

import re

from pydantic import BaseModel, Field

from ..settings import ROOT
from .base import brain, pace, say

PROMPT = (
    "You are the runbook agent. From the list of runbooks, pick the one that best fits the incident. "
    "The suspected change matters most: pick the runbook written for that kind of change, even if another one "
    "shares more words with the alert. Give its file name exactly as listed, or an empty string if none fits."
)
SUSPECT_KIND = {
    "deploy": "a release (a new version was deployed)",
    "feature_flag": "a feature flag was switched",
    "config": "a config change",
}


class RunbookPick(BaseModel):
    file: str = Field(description="file name of the best runbook, or an empty string")


COMMON = {
    "service",
    "high",
    "above",
    "minute",
    "after",
    "that",
    "this",
    "with",
    "from",
    "when",
    "should",
}  # words that fit every incident


def _words(text: str) -> set[str]:
    return {word.rstrip("s") for word in re.findall(r"[a-z]{4,}", text.lower())} - COMMON


def library() -> list[dict]:
    books = []
    for path in sorted((ROOT / "runbooks").glob("*.md")):
        text = path.read_text()
        steps = [line.strip() for line in text.splitlines() if re.match(r"\s*\d+\.", line)]
        books.append({"file": path.name, "title": text.splitlines()[0].lstrip("# ").strip(), "steps": steps, "text": text})
    return books


def offline(context: dict) -> RunbookPick:
    """Pick the runbook that shares the most words with the incident. Words in the title count three times."""
    wanted = _words(context["incident"])
    scored = [(len(wanted & _words(b["title"])) * 3 + len(wanted & _words(b["text"])), b["file"]) for b in context["runbooks"]]
    score, file = max(scored, default=(0, ""))
    return RunbookPick(file=file if score else "")


def run(state: dict) -> dict:
    books = library()
    suspect = next((f["suspect"] for f in state["findings"] if f.get("suspect")), None)
    incident = " ".join(
        [
            re.sub(
                r"(?<=[a-z])(?=[A-Z])", " ", state["alert"].get("name", "")
            ),  # PaymentErrorRateHigh -> Payment Error Rate High
            state["triage"]["summary"],
            # what kind of change the change agent suspects is the strongest hint for which procedure applies
            {"deploy": "release rollback version", "feature_flag": "feature flag switch"}.get(
                (suspect or {}).get("type", ""), ""
            ),
        ]
    )
    context = {
        "incident": incident,
        "suspected_change": SUSPECT_KIND.get((suspect or {}).get("type", ""), "nothing stands out"),
        "runbooks": [{"file": b["file"], "title": b["title"], "text": b["text"]} for b in books],
    }
    answer, source = brain(state).ask(PROMPT, RunbookPick, context, offline)
    book = next((b for b in books if b["file"] == answer.file), None)
    pace()
    if book is None:
        say(state, "runbook", "No written runbook fits this incident.", data={"answered_by": source})
        return {"findings": [{"agent": "runbook", "headline": "No runbook fits.", "steps": []}]}
    say(
        state,
        "runbook",
        f"Closest runbook: “{book['title']}”.",
        data={"file": book["file"], "steps": book["steps"], "answered_by": source},
    )
    return {"findings": [{"agent": "runbook", "headline": f"Runbook “{book['title']}” applies.", "steps": book["steps"]}]}
