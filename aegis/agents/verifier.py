"""Verifier agent: checks the numbers again after the fix. "Applied" is not "worked"."""

import time

from ..connectors import get_connector
from ..security import policy
from ..settings import env
from .base import pace, say


def healthy(metrics: dict) -> bool:
    limits = policy.load()["recovery"]
    if "error_rate" not in metrics:
        return False  # no data is not good news
    return metrics["error_rate"] < limits["error_rate_below"] and metrics.get("p95_ms", 0) < limits["p95_ms_below"]


def run(state: dict) -> dict:
    if not state["execution"]["ok"]:
        return {"verification": {"recovered": False, "metrics": {}}}
    service = state["triage"]["service"]
    # Real systems need a minute for the numbers to settle. Set AEGIS_VERIFY_TRIES and AEGIS_VERIFY_WAIT for live mode.
    tries, wait = int(env("AEGIS_VERIFY_TRIES", "1")), float(env("AEGIS_VERIFY_WAIT", "0"))
    metrics: dict = {}
    for _ in range(tries):
        time.sleep(wait)
        try:
            metrics = get_connector().signals(service)["metrics"]
        except Exception as err:  # noqa: BLE001 - keep trying; report below if it never works
            metrics = {"problem": str(err)}
        if healthy(metrics):
            break
    pace()
    if healthy(metrics):
        say(
            state,
            "verifier",
            f"Recovered. Error rate is {metrics['error_rate']:.1%} and p95 latency is {metrics.get('p95_ms', 0):.0f} ms.",
            data={"metrics": metrics},
        )
    else:
        say(
            state,
            "verifier",
            "Not recovered. The numbers are still outside the healthy range after the fix.",
            "warn",
            {"metrics": metrics},
        )
    return {"verification": {"recovered": healthy(metrics), "metrics": metrics}}
