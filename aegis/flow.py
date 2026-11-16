"""The war room flow: which agent speaks after which, and where the human decides.

    alert -> triage -> signals + changes (side by side) -> runbook -> planner -> defender
          -> human go / no-go -> executor -> verifier -> scribe

Built with LangGraph. The go / no-go is a real pause: the flow stops at
interrupt() and only continues when a decision arrives through decide().
"""

from __future__ import annotations

import operator
import threading
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import store
from .agents import changes, defender, executor, planner, runbook, scribe, signals, triage, verifier
from .security import policy


class State(TypedDict, total=False):
    incident_id: str
    model: str
    alert: dict
    triage: dict
    findings: Annotated[list, operator.add]  # each investigator adds its finding
    quarantined: Annotated[list, operator.add]  # text that looked like an attack on the AI
    plan: dict
    defender: dict
    replans: int
    gate: dict
    decision: dict
    execution: dict
    verification: dict
    report: dict


def brief(state: State) -> dict:
    """Prepare what the human sees and hears at the go / no-go moment."""
    plan, check = state["plan"], state["defender"]
    headlines = " ".join(f["headline"] for f in state["findings"] if f["agent"] in ("signals", "changes"))
    spoken = (
        f"{state['triage']['severity'].capitalize()} incident on the {state['triage']['service']} service. {headlines} "
        f"I recommend we {policy.describe(plan)}. The defender check came back {check['verdict']}, risk {check['risk']}. "
        + ("One log line tried to give me instructions. I quarantined it. " if check["quarantined"] else "")
        + "Go, or no-go?"
    )
    gate = {
        "plan": plan,
        "plan_text": policy.describe(plan),
        "plan_hash": check["plan_hash"],
        "defender": check,
        "briefing": spoken,
    }
    store.ask(state["incident_id"], gate, f"Waiting for a human: go or no-go on the plan to {policy.describe(plan)}?")
    return {"gate": gate}


def gate(state: State) -> dict:
    return {"decision": interrupt(state["gate"]["plan_hash"])}  # the flow sleeps here until a human answers


def after_defender(state: State) -> str:
    if state["defender"]["verdict"] == "block":
        return "replan" if state["replans"] <= policy.load()["limits"]["max_replans"] else "close"
    return "close" if state["plan"]["action"] == "escalate" else "ask"


def build() -> StateGraph:
    graph = StateGraph(State)
    for name, step in [
        ("triage", triage.run),
        ("signals", signals.run),
        ("changes", changes.run),
        ("runbook", runbook.run),
        ("planner", planner.run),
        ("defender", defender.run),
        ("brief", brief),
        ("gate", gate),
        ("executor", executor.run),
        ("verifier", verifier.run),
        ("scribe", scribe.run),
    ]:
        graph.add_node(name, step)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "signals")
    graph.add_edge("triage", "changes")
    graph.add_edge(["signals", "changes"], "runbook")
    graph.add_edge("runbook", "planner")
    graph.add_edge("planner", "defender")
    graph.add_conditional_edges("defender", after_defender, {"replan": "planner", "ask": "brief", "close": "scribe"})
    graph.add_edge("brief", "gate")
    graph.add_conditional_edges(
        "gate", lambda s: "go" if s["decision"]["decision"] == "go" else "stop", {"go": "executor", "stop": "scribe"}
    )
    graph.add_edge("executor", "verifier")
    graph.add_edge("verifier", "scribe")
    graph.add_edge("scribe", END)
    return graph


GRAPH = build().compile(checkpointer=InMemorySaver())
_lock = threading.Lock()


def _run(incident_id: str, payload) -> None:
    try:
        GRAPH.invoke(payload, {"configurable": {"thread_id": incident_id}})
    except Exception as err:  # noqa: BLE001 - whatever breaks, the room must be told and the incident must not hang
        store.emit(incident_id, "aegis", f"The flow stopped with an error: {err}", "error")
        store.finish(
            incident_id, "failed", {"outcome": "failed", "closing": "Something went wrong on my side. Please take over."}
        )


def _go(incident_id: str, payload, wait: bool) -> None:
    if wait:
        _run(incident_id, payload)
    else:
        threading.Thread(target=_run, args=(incident_id, payload), daemon=True).start()


def start(alert: dict, model: str, wait: bool = False) -> store.Incident:
    """Open an incident and let the agents work until they need a human (or finish)."""
    incident = store.create(alert, model)
    _go(
        incident.id,
        {"incident_id": incident.id, "model": model, "alert": alert, "findings": [], "quarantined": [], "replans": 0},
        wait,
    )
    return incident


def decide(incident_id: str, decision: str, plan_hash: str, by: str = "", note: str = "", wait: bool = False) -> None:
    """Record the human's go / no-go and let the flow continue."""
    if decision not in ("go", "no-go"):
        raise ValueError("decision must be 'go' or 'no-go'")
    with _lock:  # two clicks at once must not run the action twice
        incident = store.INCIDENTS[incident_id]
        if incident.status != "awaiting_decision":
            raise ValueError("this incident is not waiting for a decision")
        incident.status = "executing"
    answer = {"decision": decision, "plan_hash": plan_hash, "by": by or "operator", "note": note}
    store.emit(
        incident_id, "human", f"{answer['by']} said {decision.upper()}." + (f" Note: {note}" if note else ""), "decision", answer
    )
    _go(incident_id, Command(resume=answer), wait)
