"""Talking to Aegis: what you say becomes one command, and facts come from the record."""

import time

import pytest
from fastapi.testclient import TestClient

from aegis import assistant, flow, store
from aegis.connectors import get_connector
from aegis.server import app

client = TestClient(app)


def ask(text: str) -> dict:
    reply = client.post("/api/assistant", json={"text": text})
    assert reply.status_code == 200
    return reply.json()


@pytest.mark.parametrize(
    ("said", "intent", "extra"),
    [
        ("run the payment drill", "start_drill", {"scenario": "payment-failure"}),
        ("customers can't pay, show me", "start_drill", {"scenario": "payment-failure"}),
        ("simulate slow product pages", "start_drill", {"scenario": "recommendation-slow"}),
        ("a release broke checkout, try that one", "start_drill", {"scenario": "bad-deploy"}),
        ("attack your defences", "security_drill", {}),
        ("scan the code for vulnerabilities", "security_scan", {}),
        ("check the audit log", "audit", {}),
        ("who is working right now?", "status", {}),
        ("what does the defender do", "explain", {"agent": "defender"}),
        ("what is this?", "help", {}),
        ("good evening", "chat", {}),
    ],
)
def test_plain_words_become_one_command(said, intent, extra):
    answer = ask(said)
    assert answer["intent"] == intent
    for key, value in extra.items():
        assert answer[key] == value
    assert answer["reply"]


def test_a_drill_without_a_name_asks_which_one():
    answer = ask("run a drill")
    assert answer["intent"] == "chat" and "Which drill?" in answer["reply"]


def test_go_and_no_go_are_never_commands_here():
    for said in ("go", "approve the plan", "no-go"):
        assert ask(said)["intent"] not in {"start_drill", "security_scan", "security_drill", "scan_live"}


def test_status_says_who_worked_and_who_slept():
    assert assistant.crew_status() == "The whole crew is asleep. Nothing is broken right now."
    incident = flow.start(get_connector().trigger("payment-failure"), "offline", wait=True)
    assert assistant.crew_status().startswith("Everyone is waiting on you. The plan is to switch the feature flag paymentFailure")
    flow.decide(incident.id, "no-go", incident.gate["plan_hash"], wait=True)
    status = assistant.crew_status()
    assert "ended with your no-go" in status and "Executor and Verifier slept through it" in status


def test_agents_show_as_working_only_while_their_step_runs(monkeypatch):
    seen = []
    real = store.start_work

    def spy(incident_id, agent):
        real(incident_id, agent)
        seen.append(list(store.INCIDENTS[incident_id].working))

    monkeypatch.setattr(store, "start_work", spy)
    incident = flow.start(get_connector().trigger("payment-failure"), "offline", wait=True)
    assert ["triage"] in seen and any("planner" in now for now in seen)
    assert incident.working == []  # nobody is working while the room waits for you


def test_a_model_that_names_a_drill_that_does_not_exist_falls_back_to_the_words(monkeypatch):
    class Confused:
        def ask(self, prompt, schema, context, fallback):
            return schema(intent="start_drill", scenario="made-up", reply="Sure!"), "local"

    monkeypatch.setattr(assistant, "get_brain", lambda _model: Confused())
    answer = assistant.answer("run the payment one", "local")
    assert answer["intent"] == "start_drill" and answer["scenario"] == "payment-failure"
    assert answer["reply"] == "Waking the crew. Drill: customers cannot pay."


def test_the_model_never_writes_the_facts(monkeypatch):
    class Chatty:
        def ask(self, prompt, schema, context, fallback):
            return schema(intent="status", reply="Everyone fixed everything!"), "local"

    monkeypatch.setattr(assistant, "get_brain", lambda _model: Chatty())
    assert assistant.answer("status?", "local")["reply"] == "The whole crew is asleep. Nothing is broken right now."


def test_config_names_the_operator(monkeypatch):
    monkeypatch.setenv("AEGIS_OPERATOR_NAME", "Debanjan")
    assert client.get("/api/config").json()["operator"] == "Debanjan"


def test_the_live_feed_carries_who_is_working():
    incident = flow.start(get_connector().trigger("payment-failure"), "offline", wait=True)
    flow.decide(incident.id, "no-go", incident.gate["plan_hash"], wait=True)
    time.sleep(0.05)
    with client.stream("GET", f"/api/incidents/{incident.id}/stream") as feed:
        body = "".join(feed.iter_text())
    assert '"working": []' in body and "event: status" in body
