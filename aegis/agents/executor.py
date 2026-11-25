"""Executor agent: runs the approved action, and only the approved action."""

from .. import telemetry
from ..connectors import get_connector
from ..security import policy
from .base import pace, say


class Refused(Exception):
    """The executor will not act. The message says why."""


def execute(plan: dict, decision: dict, connector) -> str:
    """Three locks before anything runs. All three must open."""
    if decision.get("decision") != "go":
        raise Refused("there is no human go on record")
    if decision.get("plan_hash") != policy.plan_hash(plan):
        raise Refused("the plan about to run is not the plan the human approved")
    failed = [c["check"] for c in policy.check(plan) if not c["ok"]]
    if failed:
        raise Refused(f"the plan fails policy: {'; '.join(failed)}")
    return connector.apply(plan["action"], plan["target"], plan["value"])


def run(state: dict) -> dict:
    plan = state["plan"]
    with telemetry.human_decision(plan, state["decision"].get("decision", "")) as span:
        try:
            outcome = execute(plan, state["decision"], get_connector())
        except Refused as err:
            telemetry.failed(span, err, "refused")
            say(state, "executor", f"I refuse to act: {err}.", "block")
            return {"execution": {"ok": False, "detail": f"Refused: {err}"}}
        except Exception as err:  # noqa: BLE001 - a failed action must be reported, not hidden
            telemetry.failed(span, err)
            say(state, "executor", f"The action failed: {err}", "error")
            return {"execution": {"ok": False, "detail": f"Failed: {err}"}}
    pace()
    say(state, "executor", f"Done as approved: {outcome}.", "action", {"plan_hash": policy.plan_hash(plan)})
    return {"execution": {"ok": True, "detail": outcome}}
