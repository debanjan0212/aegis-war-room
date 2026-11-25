"""OpenTelemetry for the war room, in the GenAI conventions, so the agents that answer incidents can be watched
like any other agents (by Themis, Tempo, Jaeger or anything that reads OTLP).

Off until OTEL_EXPORTER_OTLP_ENDPOINT is set. The standard OTEL_* variables do the rest:

    OTEL_EXPORTER_OTLP_ENDPOINT=http://themis:8600
    OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20<ingest key>
    OTEL_SERVICE_NAME=aegis-war-room        (the default)

What is recorded, per incident:

    incident <id>: investigate        one trace from the alert to the go / no-go question
      invoke_agent triage, signals, changes, runbook, planner, defender
        chat <model>                  each question to a model; failures are errors, offline rules are not models
    incident <id>: act                one trace from the human's answer to the postmortem
      execute_tool <action>           the approved change, marked approved_by_human; a no-go is denied_by_human
      invoke_agent executor, verifier, scribe

Both traces carry session.id = the incident id, so they read as one incident. Prompts and model answers are never
recorded: they can hold whatever an attacker wrote into a log line.
"""

from __future__ import annotations

import atexit
import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

TRACER = trace.get_tracer("aegis")


def setup() -> bool:
    """Send spans over OTLP/HTTP when OTEL_EXPORTER_OTLP_ENDPOINT is set. Safe to call more than once."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") and not os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        return False
    if not isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
        return True  # someone (a test, an auto-instrumentation agent) set one up already: use theirs
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    name = os.getenv("OTEL_SERVICE_NAME", "aegis-war-room")
    provider = TracerProvider(resource=Resource.create({"service.name": name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)  # `aegis demo` ends in seconds: send what is queued before it exits
    return True


@contextmanager
def incident_trace(incident_id: str, part: str):
    """The root of one trace: part is "investigate" or "act"."""
    attributes = {"themis.journey.name": "incident " + part, "session.id": incident_id, "aegis.incident.id": incident_id}
    with TRACER.start_as_current_span(f"incident {incident_id}: {part}", attributes=attributes) as span:
        yield span


@contextmanager
def agent_span(name: str):
    attributes = {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": name}
    with TRACER.start_as_current_span("invoke_agent " + name, attributes=attributes) as span:
        yield span


@contextmanager
def model_span(provider: str, model: str):
    attributes = {"gen_ai.operation.name": "chat", "gen_ai.provider.name": provider, "gen_ai.request.model": model}
    with TRACER.start_as_current_span("chat " + model, attributes=attributes) as span:
        yield span


def record_usage(span, message) -> None:
    """Token counts from a LangChain message, when the provider reports them."""
    usage = getattr(message, "usage_metadata", None) or {}
    if "input_tokens" in usage:
        span.set_attribute("gen_ai.usage.input_tokens", int(usage["input_tokens"]))
    if "output_tokens" in usage:
        span.set_attribute("gen_ai.usage.output_tokens", int(usage["output_tokens"]))


def failed(span, err: BaseException | str, error_type: str = "") -> None:
    span.set_status(Status(StatusCode.ERROR, str(err)[:200]))
    span.set_attribute("error.type", error_type or type(err).__name__)


def human_decision(plan: dict, decision: str):
    """The approved (or refused) change as a tool span. Returns a context manager; the executor runs inside it."""
    attributes = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": plan["action"],
        "aegis.action.target": str(plan.get("target", "")),
        "themis.action.risk": "high",
        "themis.gate.decision": "approved_by_human" if decision == "go" else "denied_by_human",
    }
    return TRACER.start_as_current_span("execute_tool " + plan["action"], attributes=attributes)
