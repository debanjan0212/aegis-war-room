"""A pretend production system, driven by the files in scenarios/.

It behaves like a real one for the demo: an incident starts when you trigger a
scenario, the numbers stay bad until the right fix is applied, and they recover
after it. The wrong fix changes nothing.
"""

import json

from ..settings import ROOT
from . import safe_name

_EMPTY = {"metrics": {}, "logs": [], "traces": []}


class Simulator:
    name = "simulator"

    def __init__(self):
        self.active: dict[str, dict] = {}  # service -> the scenario currently hurting it
        self.fixed: set[str] = set()  # scenario ids whose fix has been applied

    def scenarios(self) -> list[dict]:
        loaded = [json.loads(path.read_text()) for path in (ROOT / "scenarios").glob("*.json")]
        return sorted(loaded, key=lambda scenario: (scenario.get("order", 99), scenario["id"]))

    def trigger(self, scenario_id: str) -> dict:
        """Start an incident. Returns the alert a monitoring system would have sent."""
        scenario = next(s for s in self.scenarios() if s["id"] == scenario_id)
        self.fixed.discard(scenario_id)
        self.active[scenario["alert"]["service"]] = scenario
        return {**scenario["alert"], "scenario": scenario_id}

    def signals(self, service: str) -> dict:
        scenario = self.active.get(safe_name(service))
        if not scenario:
            return _EMPTY
        return scenario["after" if scenario["id"] in self.fixed else "during"]

    def changes(self, service: str) -> list[dict]:
        scenario = self.active.get(safe_name(service))
        return scenario["changes"] if scenario else []

    def apply(self, action: str, target: str, value: str) -> str:
        wanted = {"action": action, "target": target, "value": value}
        for scenario in self.active.values():
            if scenario.get("fix") == wanted:
                self.fixed.add(scenario["id"])
        return f"{action} done: {target} is now {value}" if value else f"{action} done on {target}"

    def detect(self) -> list[dict]:
        return []  # in the simulator, incidents start when you trigger a scenario
