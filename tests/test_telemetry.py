"""What the war room tells an OpenTelemetry backend (Themis, Tempo, Jaeger) about its own agents."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from aegis import flow
from aegis.connectors import get_connector

SPANS = InMemorySpanExporter()
if isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(SPANS))
    trace.set_tracer_provider(provider)


@pytest.fixture(autouse=True)
def clean():
    SPANS.clear()
    yield


def play_and_answer(answer: str):
    incident = flow.start(get_connector().trigger("payment-failure"), "offline", wait=True)
    flow.decide(incident.id, answer, incident.gate["plan_hash"], by="debanjan", wait=True)
    spans = SPANS.get_finished_spans()
    roots = {s.attributes["themis.journey.name"]: s for s in spans if s.parent is None}
    return incident, spans, roots


def children(spans, parent):
    return [s for s in spans if s.parent and s.parent.span_id == parent.context.span_id]


def test_an_incident_is_two_traces_one_session_and_every_agent_is_a_span():
    incident, spans, roots = play_and_answer("go")
    assert set(roots) == {"incident investigate", "incident act"}
    assert {r.attributes["session.id"] for r in roots.values()} == {incident.id}
    assert {r.attributes["themis.journey.outcome"] for r in roots.values()} == {"success"}
    agents = {s.attributes["gen_ai.agent.name"]: s for s in spans if s.attributes.get("gen_ai.operation.name") == "invoke_agent"}
    assert set(agents) == {"triage", "signals", "changes", "runbook", "planner", "defender", "executor", "verifier", "scribe"}
    investigate = roots["incident investigate"].context.trace_id
    # the two investigators run side by side in other threads, and still land in the incident's trace
    assert agents["signals"].context.trace_id == agents["changes"].context.trace_id == investigate
    assert agents["executor"].context.trace_id == roots["incident act"].context.trace_id


def test_the_approved_change_is_a_tool_call_a_human_approved():
    _, spans, _ = play_and_answer("go")
    (executor,) = [s for s in spans if s.name == "invoke_agent executor"]
    (change,) = children(spans, executor)
    assert change.name == "execute_tool set_feature_flag" and change.status.is_ok
    assert change.attributes["themis.gate.decision"] == "approved_by_human"
    assert change.attributes["themis.action.risk"] == "high"


def test_a_no_go_is_recorded_as_refused_and_the_incident_as_handed_to_a_person():
    _, spans, roots = play_and_answer("no-go")
    refused = [s for s in spans if s.attributes.get("themis.gate.decision") == "denied_by_human"]
    assert [s.name for s in refused] == ["execute_tool set_feature_flag"]
    assert roots["incident act"].attributes["themis.journey.outcome"] == "blocked"
    assert not [s for s in spans if s.name == "invoke_agent executor"]


def test_offline_rules_are_not_reported_as_a_model():
    _, spans, _ = play_and_answer("go")
    assert not [s for s in spans if s.attributes.get("gen_ai.operation.name") == "chat"]


def test_a_failing_model_is_an_error_span_and_the_incident_goes_on():
    from aegis.agents import triage
    from aegis.brain import Brain

    class Down:
        def with_structured_output(self, _schema, **_):
            raise ConnectionError("no network")

    brain = Brain("offline")
    brain.model_id, brain.provider, brain.model_name, brain._llm = "azure", "azure_openai", "gpt-4o", Down()
    answer, source = brain.ask("prompt", triage.Triage, {"alert": {"service": "payment"}}, triage.offline)
    (chat,) = SPANS.get_finished_spans()
    assert chat.name == "chat gpt-4o" and chat.attributes["gen_ai.provider.name"] == "azure_openai"
    assert not chat.status.is_ok and chat.attributes["error.type"] == "ConnectionError"
    assert "azure failed" in source and answer.service == "payment"


def test_token_counts_come_from_the_model_reply():
    from aegis.agents import triage
    from aegis.brain import Brain

    class Raw:
        usage_metadata = {"input_tokens": 120, "output_tokens": 30}

    class Up:
        def with_structured_output(self, schema, include_raw=False):
            assert include_raw

            class Runnable:
                def invoke(self, _messages):
                    return {
                        "raw": Raw(),
                        "parsed": schema(severity="high", service="payment", summary="x"),
                        "parsing_error": None,
                    }

            return Runnable()

    brain = Brain("offline")
    brain.model_id, brain.provider, brain.model_name, brain._llm = "local", "ollama", "qwen3", Up()
    answer, source = brain.ask("prompt", triage.Triage, {"alert": {}}, triage.offline)
    (chat,) = SPANS.get_finished_spans()
    assert source == "local" and answer.severity == "high"
    assert chat.attributes["gen_ai.usage.input_tokens"] == 120 and chat.attributes["gen_ai.usage.output_tokens"] == 30
