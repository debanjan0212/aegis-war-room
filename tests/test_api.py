"""The web API and the live connector."""

import json
import time

import httpx
from fastapi.testclient import TestClient

from aegis import store
from aegis.connectors.otel_demo import OtelDemo
from aegis.server import app

client = TestClient(app)


def wait_for(incident_id: str, *statuses: str) -> dict:
    for _ in range(100):
        body = client.get(f"/api/incidents/{incident_id}").json()
        if body["status"] in statuses:
            return body
        time.sleep(0.05)
    raise AssertionError(f"incident stuck in {body['status']}")


def test_config_lists_models_scenarios_and_voices():
    body = client.get("/api/config").json()
    assert body["source"] == "simulator" and len(body["scenarios"]) == 3
    assert {v["id"] for v in body["voices"]} == {"aria", "butler"} and body["models"][0]["id"] == "offline"


def test_full_incident_over_http_and_the_live_feed():
    incident_id = client.post("/api/incidents/trigger", json={"scenario": "payment-failure"}).json()["id"]
    waiting = wait_for(incident_id, "awaiting_decision")
    done = client.post(
        f"/api/incidents/{incident_id}/decision",
        json={"decision": "go", "plan_hash": waiting["gate"]["plan_hash"], "by": "tester"},
    )
    assert done.status_code == 200
    assert wait_for(incident_id, "resolved")["result"]["outcome"] == "resolved"
    assert client.post(f"/api/incidents/{incident_id}/decision", json={"decision": "go", "plan_hash": "x"}).status_code == 409

    feed = client.get(f"/api/incidents/{incident_id}/stream").text
    assert feed.count("event: step") == len(store.INCIDENTS[incident_id].events) and '"status": "resolved"' in feed
    resumed = client.get(f"/api/incidents/{incident_id}/stream", headers={"last-event-id": "3"}).text
    assert resumed.count("event: step") == len(store.INCIDENTS[incident_id].events) - 4
    odd = client.get(f"/api/incidents/{incident_id}/stream", headers={"last-event-id": "not-a-number"})
    assert odd.status_code == 200 and odd.text.count("event: step") == len(store.INCIDENTS[incident_id].events)


def test_webhook_accepts_alertmanager_shape_and_ignores_repeats():
    alert = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighErrors", "service_name": "cart", "severity": "high"},
                "annotations": {"summary": "cart is failing"},
            }
        ]
    }
    first = client.post("/api/alerts", json=alert).json()["ids"]
    again = client.post("/api/alerts", json=alert).json()["ids"]
    assert len(first) == 1 and (again == first or store.INCIDENTS[first[0]].status not in store.OPEN)
    assert store.INCIDENTS[first[0]].alert["service"] == "cart"
    # nothing is known about "cart" in the simulator, so the agents must hand over instead of guessing
    assert wait_for(first[0], "escalated")["gate"] is None


def test_a_malformed_webhook_is_ignored_not_a_crash():
    for body in (
        {"alerts": "not a list"},
        {"alerts": ["text", 7, None]},
        {"alerts": [{"labels": "x", "annotations": 3, "status": "resolved"}]},
    ):
        reply = client.post("/api/alerts", json=body)
        assert reply.status_code == 200 and reply.json() == {"ids": []}
    assert client.get("/api/incidents").json() == []


def test_bad_requests_are_rejected():
    assert client.post("/api/incidents/trigger", json={"scenario": "nope"}).status_code == 404
    assert client.post("/api/incidents/trigger", json={"scenario": "payment-failure", "model": "azure"}).status_code == 400
    assert client.get("/api/incidents/unknown").status_code == 404
    assert client.post("/api/alerts", content="x" * 70_000, headers={"content-type": "application/json"}).status_code == 413


def test_api_token_protects_everything_that_changes_state(monkeypatch):
    monkeypatch.setenv("AEGIS_API_TOKEN", "s3cret-for-this-test")
    assert client.post("/api/incidents/trigger", json={"scenario": "payment-failure"}).status_code == 401
    assert client.post("/api/security/drill").status_code == 401
    ok = client.post("/api/security/drill", headers={"Authorization": "Bearer s3cret-for-this-test"})
    assert ok.status_code == 200 and all(r["held"] for r in ok.json())


def test_security_headers_are_set():
    headers = client.get("/api/config").headers
    assert headers["x-frame-options"] == "DENY" and "default-src 'self'" in headers["content-security-policy"]


# --- the live connector, against recorded-shape Prometheus answers and a real flag file ---
def prometheus(request: httpx.Request) -> httpx.Response:
    query = request.url.params["query"]
    if "sum by (service_name)" in query:
        result = [
            {"metric": {"service_name": "payment"}, "value": [0, "0.48"]},
            {"metric": {"service_name": "cart"}, "value": [0, "0.01"]},
            {"metric": {"service_name": "idle"}, "value": [0, "NaN"]},
        ]
    elif "histogram_quantile" in query:
        result = [{"metric": {}, "value": [0, "2100.5"]}]
    else:
        assert 'service_name="payment"' in query
        result = [{"metric": {}, "value": [0, "0.48"]}]
    return httpx.Response(200, json={"status": "success", "data": {"result": result}})


def test_live_connector_reads_metrics_flags_and_switches_a_flag_off(tmp_path, monkeypatch):
    flags = tmp_path / "demo.flagd.json"
    flags.write_text(
        json.dumps(
            {
                "flags": {
                    "paymentFailure": {"defaultVariant": "50%", "variants": {"50%": 0.5, "off": 0}},
                    "cartFailure": {"defaultVariant": "off", "variants": {"on": True, "off": False}},
                }
            }
        )
    )
    monkeypatch.setenv("OTEL_DEMO_FLAG_FILE", str(flags))
    demo = OtelDemo(httpx.Client(transport=httpx.MockTransport(prometheus)))

    assert demo.signals("payment")["metrics"] == {"error_rate": 0.48, "p95_ms": 2100.5, "requests_per_min": 0.48}
    assert demo.detect() == [
        {
            "name": "HighErrorRate",
            "service": "payment",
            "severity": "critical",
            "summary": "payment is failing 48% of its requests.",
        }
    ]
    assert [c["target"] for c in demo.changes("payment")] == ["paymentFailure"]

    assert demo.apply("set_feature_flag", "paymentFailure", "off") == "flag paymentFailure is now off"
    assert json.loads(flags.read_text())["flags"]["paymentFailure"]["defaultVariant"] == "off"
    assert demo.changes("payment") == []
    for bad in (("set_feature_flag", "paymentFailure", "banana"), ("restart_service", "payment", "")):
        try:
            demo.apply(*bad)
            raise AssertionError("should have refused")
        except RuntimeError:
            pass
