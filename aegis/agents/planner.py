"""Planner agent: turns the findings into a root cause and ONE proposed action.

The planner cannot invent an action. Its answer must pick from the actions
that config/policy.yaml has enabled, so "delete the namespace" is not a
sentence it is able to say.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ..security import policy
from .base import brain, pace, say

PROMPT = (
    "You are the planner agent. Using the findings, state the most likely root cause and choose ONE action from "
    "the allowed list. Choose 'escalate' when no allowed action clearly fixes the cause or when you are unsure. "
    "Only switch off a feature flag that the findings name as the suspect; never a different flag. If the suspect "
    "is a release or deployment, choose 'escalate': agents are not allowed to roll back. "
    "For set_feature_flag, target is the flag name and value is 'off'. For escalate, leave target and value "
    "empty. If defender_feedback is present, your previous plan was blocked for those reasons: do not propose it "
    "again. Confidence is a number between 0 and 1."
)


def plan_schema() -> type[BaseModel]:
    Action = Enum("Action", {name: name for name in policy.enabled_actions()}, type=str)

    class Plan(BaseModel):
        model_config = ConfigDict(use_enum_values=True)
        root_cause: str = Field(description="one or two plain sentences")
        action: Action  # type: ignore[valid-type]
        target: str
        value: str
        reason: str = Field(description="why this action fixes the root cause")
        undo: str = Field(description="how to undo the action if it makes things worse")
        confidence: float

    return Plan


def offline(context: dict) -> BaseModel:
    Plan = plan_schema()
    suspect = context.get("suspect")
    flags = policy.load()["actions"]["set_feature_flag"]
    escalate = {"action": "escalate", "target": "", "value": "", "undo": "Nothing to undo. No change is made."}

    if context.get("defender_feedback"):
        return Plan(
            root_cause=context["previous_root_cause"],
            confidence=0.5,
            **escalate,
            reason="The defender blocked my first plan and I have no other safe action, so a human should take over.",
        )
    if suspect and suspect["type"] == "feature_flag" and flags["enabled"] and suspect["target"] in flags["targets"]:
        flag = suspect["target"]
        return Plan(
            root_cause=f"The feature flag {flag} was switched on shortly before the trouble started, "
            "and the signals match what that flag does.",
            action="set_feature_flag",
            target=flag,
            value="off",
            confidence=0.85,
            reason="Switching the flag off removes the failure at its source and takes effect in seconds.",
            undo=f"Switch {flag} back to its earlier setting.",
        )
    if suspect and suspect["type"] == "deploy":
        return Plan(
            root_cause=f"A release lines up with the start of the errors: {suspect['detail']}.",
            confidence=0.8,
            **escalate,
            reason="The fix is a rollback. Agents are not allowed to roll back a release, so a human must do it.",
        )
    return Plan(
        root_cause="No single cause stands out from the evidence.",
        confidence=0.3,
        **escalate,
        reason="I do not have a safe, clearly correct action to propose.",
    )


def run(state: dict) -> dict:
    actions = policy.load()["actions"]
    blocked = state.get("defender", {}).get("verdict") == "block"
    context = {
        "incident": state["triage"],
        "findings": [{k: v for k, v in f.items() if k != "metrics"} for f in state["findings"]],
        "suspect": next((f["suspect"] for f in state["findings"] if f.get("suspect")), None),
        "allowed_actions": {
            name: {"description": actions[name]["description"], "targets": actions[name]["targets"]}
            for name in policy.enabled_actions()
        },
    }
    if blocked:
        context["defender_feedback"] = [c for c in state["defender"]["checks"] if not c["ok"]]
        context["previous_root_cause"] = state["plan"]["root_cause"]

    answer, source = brain(state).ask(PROMPT, plan_schema(), context, offline)
    plan = answer.model_dump()
    plan["confidence"] = min(max(float(plan["confidence"]), 0.0), 1.0)
    pace()
    say(
        state,
        "planner",
        f"Root cause: {plan['root_cause']} I propose to {policy.describe(plan)}. {plan['reason']}",
        data={"plan": plan, "answered_by": source},
    )
    return {"plan": plan}
