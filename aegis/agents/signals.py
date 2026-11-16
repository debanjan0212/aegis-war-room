"""Signals agent: looks at metrics, logs and traces and says what is abnormal."""

from pydantic import BaseModel, Field

from ..connectors import get_connector
from ..security import injection
from .base import brain, pace, say

PROMPT = (
    "You are the signals agent. From the metrics, log lines and traces of one service, say in one sentence what "
    "is wrong, then list up to four concrete abnormal facts with their numbers."
)


class Signals(BaseModel):
    headline: str = Field(description="one sentence: what is wrong")
    abnormal: list[str] = Field(description="up to four abnormal facts, with numbers")


def offline(context: dict) -> Signals:
    metrics, facts = context["metrics"], []
    if "error_rate" in metrics:
        normal = f" (normal {metrics['baseline_error_rate']:.1%})" if "baseline_error_rate" in metrics else ""
        facts.append(f"error rate {metrics['error_rate']:.1%}{normal}")
    if "p95_ms" in metrics:
        normal = f" (normal {metrics['baseline_p95_ms']:.0f} ms)" if "baseline_p95_ms" in metrics else ""
        facts.append(f"p95 latency {metrics['p95_ms']:.0f} ms{normal}")
    if "memory_mb" in metrics:
        facts.append(f"memory {metrics['memory_mb']:.0f} MB")
    problems = [line for line in context["logs"] if line.startswith(("ERROR", "WARN"))]
    if problems:
        facts.append(f"log: {problems[0]}")
    if context["traces"]:
        facts.append(f"trace: {context['traces'][0]}")
    if not facts:
        return Signals(headline=f"I found no data for {context['service']}.", abnormal=[])
    return Signals(headline=f"{context['service']} is unhealthy: {', '.join(facts[:2])}.", abnormal=facts[:4])


def run(state: dict) -> dict:
    service = state["triage"]["service"]
    try:
        raw = get_connector().signals(service)
    except Exception as err:  # noqa: BLE001 - a monitoring outage is a finding, not a crash
        say(state, "signals", f"I could not read the monitoring data: {err}", "error")
        return {
            "findings": [{"agent": "signals", "headline": "Monitoring data could not be read.", "abnormal": [], "metrics": {}}]
        }

    logs, flagged = injection.quarantine(raw["logs"])
    if flagged:
        say(
            state,
            "signals",
            f"I quarantined {len(flagged)} log line{'s' if len(flagged) > 1 else ''} written to look like instructions "
            "for an AI. No agent will act on that text.",
            "warn",
            {"quarantined": flagged},
        )
    context = {"service": service, "metrics": raw["metrics"], "logs": logs[:30], "traces": raw["traces"][:10]}
    answer, source = brain(state).ask(PROMPT, Signals, context, offline)
    pace()
    say(state, "signals", answer.headline, data={"abnormal": answer.abnormal, "metrics": raw["metrics"], "answered_by": source})
    finding = {"agent": "signals", "headline": answer.headline, "abnormal": answer.abnormal[:4], "metrics": raw["metrics"]}
    return {"findings": [finding], "quarantined": [{**item, "source": "log line"} for item in flagged]}
