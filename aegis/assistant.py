"""Aegis itself: you talk to it in your own words, and it works out what you want.

The model only does two things here: pick which one of a fixed list of commands you meant, and write small talk.
Everything factual it says (who is working, what an agent does, what a drill is) is built from the record.
It can start drills and checks. It can never approve or reject a fix: go and no-go are matched word for word
by the screen, never interpreted by a model.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from . import store
from .brain import get_brain
from .connectors import get_connector

PROMPT = (
    "You are Aegis, the assistant in an AI incident war room. The operator talks to you in their own words. "
    "Work out which ONE command they want from the commands list, and write a reply of one or two short, warm "
    "sentences, as you would say it out loud. If they name a drill, give its id exactly as listed in scenarios. "
    "If they ask about one agent, give its id exactly as listed in agents. You cannot approve or reject a fix: if "
    "they say go or no-go, choose chat and tell them to use the go or no-go buttons."
)

COMMANDS = {
    "start_drill": "run one of the simulated incidents (scenarios)",
    "scan_live": "look at the live system for anything unhealthy now",
    "security_scan": "scan this code for vulnerabilities (the Code Guard agent)",
    "security_drill": "attack Aegis's own defences to show they hold",
    "audit": "check the audit log has not been tampered with",
    "status": "say which agents are working, which have reported and which are asleep",
    "brief": "read out the briefing for the decision that is waiting",
    "explain": "explain what one agent does",
    "help": "say what Aegis is and what it can do",
    "chat": "small talk, thanks, greetings, or anything else",
}

# The crew, in the order they work. "You" is not here: you are the human at the go / no-go.
CREW = {
    "triage": ("Triage", "decides how bad the incident is and which service is hurt"),
    "signals": ("Signals", "reads the metrics, logs and traces, and quarantines any log line that tries to give the AI orders"),
    "changes": ("Changes", "finds what changed just before the trouble started"),
    "runbook": ("Runbook", "finds the team's written procedure that fits"),
    "planner": ("Planner", "names the root cause and proposes one fix, chosen from an allowed list"),
    "defender": ("Defender", "checks every plan against fixed rules. It uses no AI, so it cannot be talked into anything"),
    "executor": ("Executor", "carries out the fix you approved, and nothing else"),
    "verifier": ("Verifier", "checks the numbers again after the fix, because applied is not the same as worked"),
    "scribe": ("Scribe", "writes the postmortem and the message for the team, from the record"),
    "codeguard": ("Code Guard", "scans this code for vulnerabilities and leaked secrets"),
}
INCIDENT_CREW = [agent for agent in CREW if agent != "codeguard"]

HELP = (
    "I'm Aegis, your incident room. When something breaks, I wake a crew of nine agents. They investigate, "
    "a defender checks their plan, and nothing is changed until you say go. Ask me to run a drill, scan the code, "
    "attack my own defences, or tell you who is working."
)
NOT_SURE = (
    "I didn't catch what you want me to do. I can run a drill, scan the code, attack my own defences, or tell you who is working."
)
ENDED = {
    "resolved": "was resolved",
    "not_resolved": "was fixed but did not recover",
    "rejected": "ended with your no-go, so nothing was changed",
    "escalated": "was handed to a human, with nothing changed",
    "failed": "stopped with an error",
}

Intent = Enum("Intent", {name: name for name in COMMANDS}, type=str)


class Command(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    intent: Intent  # type: ignore[valid-type]
    scenario: str = Field("", description="the scenario id when the command is start_drill, otherwise empty")
    agent: str = Field("", description="the agent id when the command is explain, otherwise empty")
    reply: str = Field(description="one or two short sentences to say out loud")


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _names(agents: list[str]) -> str:
    return _join([CREW[agent][0] for agent in agents])


def crew_status() -> str:
    """Who is working, who has reported and who is asleep, from the latest incident."""
    if not store.INCIDENTS:
        return "The whole crew is asleep. Nothing is broken right now."
    latest = max(store.INCIDENTS.values(), key=lambda incident: incident.created)
    spoke = {event["agent"] for event in latest.events}
    if latest.status == "awaiting_decision" and latest.gate:
        return f"Everyone is waiting on you. The plan is to {latest.gate['plan_text']}. Say go or no-go."
    if latest.status in store.OPEN:
        working = [a for a in INCIDENT_CREW if a in latest.working]
        reported = [a for a in INCIDENT_CREW if a in spoke and a not in latest.working]
        asleep = [a for a in INCIDENT_CREW if a not in spoke and a not in latest.working]
        parts = []
        if working:
            parts.append(f"{_names(working)} {'is' if len(working) == 1 else 'are'} working")
        if reported:
            parts.append(f"{_names(reported)} {'has' if len(reported) == 1 else 'have'} reported")
        if asleep:
            parts.append(f"{_names(asleep)} {'is' if len(asleep) == 1 else 'are'} asleep until called")
        return (". ".join(parts) or "The crew is getting started") + "."
    worked = [a for a in INCIDENT_CREW if a in spoke]
    slept = [a for a in INCIDENT_CREW if a not in spoke]
    line = f"The last incident, {latest.title}, {ENDED.get(latest.status, 'is closed')}. {_names(worked)} worked on it."
    if slept:
        line += f" {_names(slept)} slept through it: {'it was' if len(slept) == 1 else 'they were'} not needed."
    return line


def _scenarios() -> list[dict]:
    connector = get_connector()
    if connector.name != "simulator":
        return []
    return [{"id": s["id"], "title": s["title"], "story": s["story"]} for s in connector.scenarios()]


# Words that point at one drill. Checked in this order, so "release broke checkout" is the release drill.
DRILL_WORDS = {
    "bad-deploy": r"releas|deploy|roll ?back|version",
    "payment-failure": r"\bpay|charge|card|money|can'?t pay|cannot pay",
    "recommendation-slow": r"slow|latenc|recommend|product page",
}


def offline(context: dict) -> Command:
    """The same job without a model: keyword rules, checked from the most specific to the least."""
    said = context["said"].lower()
    ids = {s["id"] for s in context["scenarios"]}

    def command(intent: str, **extra) -> Command:
        return Command(intent=intent, reply=extra.pop("reply", ""), **extra)

    if re.search(r"attack|defen[cs]e|red ?team|pen ?test|security drill", said):
        return command("security_drill")
    if re.search(r"scan|check", said) and re.search(r"code|repo|vulnerab|secur|secret", said):
        return command("security_scan")
    if re.search(r"audit|tamper", said):
        return command("audit")
    if re.search(r"scan|check|look", said) and re.search(r"live|shop|system|real", said):
        return command("scan_live")
    for agent, (name, _) in CREW.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", said) and re.search(r"what|who|explain|tell|does|\bdo\b", said):
            return command("explain", agent=agent)
    for scenario, words in DRILL_WORDS.items():
        if scenario in ids and re.search(words, said):
            return command("start_drill", scenario=scenario)
    if re.search(r"\b(drill|simulat|incident|break something|test)\b", said):
        return command("chat", reply="Which drill? Customers cannot pay, slow product pages, or a release that broke checkout.")
    if re.search(r"status|who('?s| is| are)|working|sleep|busy|happening|going on|update", said):
        return command("status")
    if re.search(r"brief|recap|the plan", said):
        return command("brief")
    if re.search(r"what (is|are) (this|you)|what can you|help|how (does|do)|who are you", said):
        return command("help")
    if re.search(r"^(hi|hello|hey|good (morning|afternoon|evening|night))\b", said):
        return command("chat", reply="Hello. Everything is quiet. Shall I run a drill?")
    if re.search(r"thank", said):
        return command("chat", reply="Any time.")
    return command("chat", reply=NOT_SURE)


def answer(said: str, model: str) -> dict:
    """Work out what was meant, and reply. Replies about facts are built here, never taken from the model."""
    scenarios = _scenarios()
    context = {
        "said": said,
        "commands": COMMANDS,
        "scenarios": scenarios,
        "agents": {agent: job for agent, (_, job) in CREW.items()},
        "situation": crew_status(),
    }
    command, source = get_brain(model).ask(PROMPT, Command, context, offline)
    intent, scenario, agent, reply = command.intent, command.scenario, command.agent, command.reply.strip()
    titles = {s["id"]: s["title"] for s in scenarios}

    if intent == "start_drill" and scenario not in titles:
        guess = offline(context)  # the model picked a drill that does not exist; fall back to the words used
        intent, scenario, reply = guess.intent, guess.scenario, guess.reply
    if intent == "explain" and agent not in CREW:
        intent = "help"

    if intent == "start_drill":
        reply = f"Waking the crew. Drill: {titles[scenario].lower()}."
    elif intent == "scan_live" and get_connector().name == "simulator":
        intent, reply = "chat", "I'm on the simulator right now, so there is no live system to scan. Try a drill instead."
    elif intent == "scan_live":
        reply = "Looking at the live system now."
    elif intent == "security_scan":
        reply = "Code Guard is scanning this code for vulnerabilities. It takes up to a minute."
    elif intent == "security_drill":
        reply = "Attacking my own defences. Let's see if they hold."
    elif intent == "audit":
        reply = "Checking the audit log for tampering."
    elif intent == "status":
        reply = crew_status()
    elif intent == "brief":
        reply = "Here is the briefing." if any(i.status == "awaiting_decision" for i in store.INCIDENTS.values()) else ""
        reply = reply or "There is nothing waiting for your decision right now."
    elif intent == "explain":
        name, job = CREW[agent]
        reply = f"{name} {job}."
    elif intent == "help":
        reply = HELP
    elif not reply:
        reply = offline(context).reply
    return {"intent": intent, "scenario": scenario, "agent": agent, "reply": reply, "answered_by": source}
