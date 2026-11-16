"""The rules every plan must pass, read from config/policy.yaml.

Used three times on purpose: the planner builds its list of choices from it,
the defender checks the plan against it, and the executor checks once more
right before acting.
"""

from __future__ import annotations

import hashlib
import json

import yaml

from ..settings import ROOT


def load() -> dict:
    return yaml.safe_load((ROOT / "config" / "policy.yaml").read_text())


def enabled_actions() -> list[str]:
    return [name for name, rule in load()["actions"].items() if rule.get("enabled")]


def plan_hash(plan: dict) -> str:
    """A fingerprint of exactly what would run. The human approves this fingerprint, not a description."""
    core = {key: plan.get(key, "") for key in ("action", "target", "value")}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def describe(plan: dict) -> str:
    """The plan in plain words, for the screen and the voice."""
    action, target, value = plan.get("action"), plan.get("target", ""), plan.get("value", "")
    if action == "set_feature_flag":
        return f"switch the feature flag {target} to {value}"
    if action == "restart_service":
        return f"restart the {target} service"
    if action == "rollback_deployment":
        return f"roll the {target} service back to its previous version"
    if action == "escalate":
        return "page the on-call engineer and change nothing"
    return f"{action} {target} {value}".strip()


def check(plan: dict) -> list[dict]:
    """Hard checks. If any is not ok, the plan must not run."""
    policy = load()
    action, target, value = str(plan.get("action", "")), str(plan.get("target", "")), str(plan.get("value", ""))
    rule = policy["actions"].get(action)
    checks = [
        {
            "check": "The action is on the allowed list",
            "ok": bool(rule and rule.get("enabled")),
            "detail": action if rule else f"'{action}' is not a known action",
        }
    ]
    if not rule:
        return checks
    checks += [
        {
            "check": "The target is one this action may touch",
            "ok": target in rule.get("targets", []),
            "detail": target or "(none)",
        },
        {"check": "The value is one this action may set", "ok": value in rule.get("values", []), "detail": value or "(none)"},
        {
            "check": "The target is not protected",
            "ok": target not in policy.get("protected_targets", []),
            "detail": target or "(none)",
        },
    ]
    return checks


def risk_of(plan: dict) -> str:
    return load()["actions"].get(plan.get("action", ""), {}).get("risk", "high")
