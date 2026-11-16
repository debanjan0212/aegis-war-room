"""Defender agent: checks the plan before any human is asked to approve it.

The defender uses fixed rules, never an AI model. A guard that can be talked
into things is not a guard.
"""

from ..security import policy
from .base import pace, say

_STEP_UP = {"none": "none", "low": "medium", "medium": "high", "high": "high"}
# Which kind of change an action undoes. A flag plan needs a suspected flag, not a release that happens to share its name.
_UNDOES = {"set_feature_flag": "feature_flag", "rollback_deployment": "deploy"}


def review(plan: dict, findings: list[dict], quarantined: list[dict]) -> dict:
    kind = _UNDOES.get(plan["action"])
    suspects = {f["suspect"]["target"] for f in findings if f.get("suspect") and kind in (None, f["suspect"].get("type"))}
    minimum = policy.load()["limits"]["min_confidence"]
    # A change the evidence does not point at is blocked, not just flagged: a model can propose a plausible-sounding
    # fix to the wrong thing, and the human should never be asked to approve a change nobody can connect to the incident.
    hard = [
        *policy.check(plan),
        {
            "check": "The evidence points at the thing being changed",
            "ok": plan["action"] == "escalate" or plan["target"] in suspects,
            "detail": plan["target"] or "(nothing is changed)",
        },
    ]
    soft = [
        {"check": "The planner is confident enough", "ok": plan["confidence"] >= minimum, "detail": f"{plan['confidence']:.0%}"},
    ]
    if any(not c["ok"] for c in hard):
        verdict = "block"
    else:
        verdict = "caution" if any(not c["ok"] for c in soft) else "pass"
    risk = policy.risk_of(plan)
    return {
        "verdict": verdict,
        "risk": _STEP_UP[risk] if verdict == "caution" else risk,
        "checks": hard + soft,
        "plan_hash": policy.plan_hash(plan),
        "quarantined": len(quarantined),
    }


def run(state: dict) -> dict:
    result = review(state["plan"], state["findings"], state.get("quarantined", []))
    failed = [c["check"] for c in result["checks"] if not c["ok"]]
    pace()
    if result["verdict"] == "block":
        say(state, "defender", f"Blocked. This plan breaks the rules: {'; '.join(failed)}.", "block", result)
        return {"defender": result, "replans": state.get("replans", 0) + 1}
    count = result["quarantined"]
    note = f" Note: {count} injected line{'s were' if count > 1 else ' was'} removed before planning." if count else ""
    if result["verdict"] == "caution":
        say(
            state,
            "defender",
            f"Allowed with caution, risk {result['risk']}. Weak point: {'; '.join(failed)}.{note}",
            "warn",
            result,
        )
    else:
        say(
            state,
            "defender",
            f"Checked against policy: all {len(result['checks'])} checks pass, risk {result['risk']}.{note}",
            data=result,
        )
    return {"defender": result}
