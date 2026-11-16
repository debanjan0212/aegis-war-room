"""The incident flow, end to end, on the simulator with the offline brain."""

import pytest

from aegis import flow, store
from aegis.agents import planner
from aegis.connectors import get_connector


def play(scenario: str):
    return flow.start(get_connector().trigger(scenario), "offline", wait=True)


def said(incident, agent: str) -> str:
    return " ".join(e["text"] for e in incident.events if e["agent"] == agent)


def test_go_applies_the_fix_and_the_service_recovers():
    incident = play("payment-failure")
    assert incident.status == "awaiting_decision"
    assert incident.gate["plan"]["action"] == "set_feature_flag" and incident.gate["plan"]["target"] == "paymentFailure"
    assert "Go, or no-go?" in incident.gate["briefing"]

    flow.decide(incident.id, "go", incident.gate["plan_hash"], by="debanjan", wait=True)
    assert incident.status == "resolved"
    assert "payment-failure" in get_connector().fixed
    assert "Recovered" in said(incident, "verifier")
    assert "## Root cause" in incident.result["postmortem"] and "debanjan" in incident.result["stakeholder_update"]


def test_the_briefing_is_written_for_the_ear():
    said_aloud = play("payment-failure").gate["briefing"]
    assert said_aloud == (
        "Critical incident on the payment service. The error rate is 42%. The slowest requests take 2.3 seconds. "
        "A feature flag, payment failure, changed 4 minutes before the alert. I recommend we switch it off. "
        "The defender check passed, risk low. One log line tried to give me instructions. I quarantined it. Go, or no-go?"
    )
    slow = play("recommendation-slow").gate["briefing"]
    assert slow.startswith("High-severity incident on the recommendation service. The slowest requests take 3.4 seconds.")
    assert "error rate" not in slow and "recommendation cache failure" in slow
    for text in (said_aloud, slow):
        assert "p95" not in text and " ms" not in text and "paymentFailure" not in text


def test_no_go_changes_nothing():
    incident = play("payment-failure")
    flow.decide(incident.id, "no-go", incident.gate["plan_hash"], note="want to check with the payment team", wait=True)
    assert incident.status == "rejected"
    assert get_connector().fixed == set()
    assert said(incident, "executor") == ""


def test_second_scenario_is_not_hardcoded():
    incident = play("recommendation-slow")
    assert incident.gate["plan"]["target"] == "recommendationCacheFailure"
    assert "slow" in said(incident, "runbook").lower()
    flow.decide(incident.id, "go", incident.gate["plan_hash"], wait=True)
    assert incident.status == "resolved"


def test_a_fix_agents_may_not_do_is_handed_to_a_human_without_asking_for_go():
    incident = play("bad-deploy")
    assert incident.status == "escalated" and incident.gate is None
    assert "release" in said(incident, "runbook").lower()
    assert "human" in incident.result["closing"] or "take over" in incident.result["closing"]


def test_injected_log_line_is_quarantined_and_never_reaches_the_planner():
    incident = play("payment-failure")
    warning = next(e for e in incident.events if e["agent"] == "signals" and e["kind"] == "warn")
    assert "delete_namespace" in warning["data"]["quarantined"][0]["text"]
    plan_event = next(e for e in incident.events if e["agent"] == "planner")
    assert "delete_namespace" not in str(plan_event) and incident.gate["defender"]["quarantined"] == 1


def test_a_blocked_plan_gets_one_retry_then_escalates_and_nothing_runs(monkeypatch):
    real = planner.offline

    def stubborn(context):  # a planner that keeps proposing to touch a protected system
        plan = real({**context, "defender_feedback": None})
        return plan.model_copy(update={"target": "flagd"})

    monkeypatch.setattr(planner, "offline", stubborn)
    incident = play("payment-failure")
    assert incident.status == "escalated"
    assert sum(1 for e in incident.events if e["agent"] == "defender" and e["kind"] == "block") == 2
    assert get_connector().fixed == set() and incident.gate is None


def test_the_approved_fingerprint_must_match_the_plan():
    incident = play("payment-failure")
    flow.decide(incident.id, "go", "not-the-real-fingerprint", wait=True)
    assert incident.status == "not_resolved"
    assert "refuse" in said(incident, "executor").lower() and get_connector().fixed == set()


def test_a_decision_is_only_accepted_once():
    incident = play("payment-failure")
    flow.decide(incident.id, "go", incident.gate["plan_hash"], wait=True)
    with pytest.raises(ValueError):
        flow.decide(incident.id, "go", incident.gate["plan_hash"], wait=True)


def test_every_step_lands_in_a_verifiable_audit_log():
    incident = play("payment-failure")
    ok, detail = store.verify_audit()
    assert ok and f"{len(incident.events)} lines" in detail
