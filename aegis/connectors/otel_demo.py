"""The real thing: the OpenTelemetry Demo shop (https://opentelemetry.io/docs/demo/).

Reads live numbers from the demo's Prometheus, reads which failure flags are
on from the demo's flag file, and fixes an incident by switching a flag off in
that same file (the demo's flag service reloads it by itself).

Settings are in config/otel-demo.yaml. Logs and traces are not wired yet, see
docs/PLAN.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from string import Template

import httpx
import yaml

from ..settings import ROOT, env
from . import safe_name


class OtelDemo:
    name = "otel-demo"

    def __init__(self, client: httpx.Client | None = None):
        self.cfg = yaml.safe_load((ROOT / "config" / "otel-demo.yaml").read_text())
        self.prometheus = env("PROMETHEUS_URL") or self.cfg["prometheus_url"]
        self.http = client or httpx.Client(timeout=10)

    # --- reading -----------------------------------------------------------
    def _query(self, promql: str) -> list[dict]:
        reply = self.http.get(f"{self.prometheus}/api/v1/query", params={"query": promql})
        reply.raise_for_status()
        return reply.json()["data"]["result"]

    def signals(self, service: str) -> dict:
        service = safe_name(service)
        metrics = {}
        for name, template in self.cfg["queries"].items():
            rows = self._query(Template(template).substitute(service=service))
            value = float(rows[0]["value"][1]) if rows else float("nan")
            if value == value:  # no rows, or NaN (no traffic): leave it out. No data must never read as "healthy"
                metrics[name] = round(value, 4)
        return {"metrics": metrics, "logs": [], "traces": []}

    def _flag_file(self) -> Path:
        path = env("OTEL_DEMO_FLAG_FILE") or self.cfg.get("flag_file", "")
        if not path:
            raise RuntimeError("Set OTEL_DEMO_FLAG_FILE to the demo's src/flagd/demo.flagd.json")
        return Path(path)

    def changes(self, service: str) -> list[dict]:
        """Every failure flag that is switched on right now, newest first as far as the file can tell."""
        path = self._flag_file()
        minutes = int((time.time() - path.stat().st_mtime) / 60)
        owners = self.cfg.get("flag_services", {})
        return [
            {
                "id": f"flag-{name}",
                "type": "feature_flag",
                "target": name,
                "service": owners.get(name, ""),
                "detail": f"is switched to {flag['defaultVariant']}",
                "minutes_before_alert": minutes,
                "by": "flag service",
            }
            for name, flag in json.loads(path.read_text())["flags"].items()
            if flag.get("defaultVariant") != "off"
        ]

    def detect(self) -> list[dict]:
        """One alert for the unhealthiest service, if any is over the threshold."""
        threshold = float(self.cfg["detect_threshold"])
        rows = [(float(r["value"][1]), r["metric"].get("service_name", "")) for r in self._query(self.cfg["detect_query"])]
        rows = [(rate, service) for rate, service in rows if rate == rate and rate > threshold and service]
        if not rows:
            return []
        rate, service = max(rows)
        return [
            {
                "name": "HighErrorRate",
                "service": service,
                "severity": "critical" if rate > 0.25 else "high",
                "summary": f"{service} is failing {rate:.0%} of its requests.",
            }
        ]

    # --- acting ------------------------------------------------------------
    def apply(self, action: str, target: str, value: str) -> str:
        if action != "set_feature_flag":
            raise RuntimeError(f"the otel-demo connector cannot do '{action}' yet")
        path = self._flag_file()
        data = json.loads(path.read_text())
        flag = data["flags"][safe_name(target)]
        if value not in flag["variants"]:
            raise RuntimeError(f"{target} has no setting called {value!r}")
        flag["defaultVariant"] = value
        # Written in place (not swapped for a new file) so the flag service's file watcher keeps following it.
        path.write_text(json.dumps(data, indent=2) + "\n")
        return f"flag {target} is now {value}"
