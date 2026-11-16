"""Small helpers every agent shares."""

import time

from .. import store
from ..brain import Brain, get_brain
from ..settings import env


def say(state: dict, agent: str, text: str, kind: str = "say", data: dict | None = None) -> None:
    """Speak in the war room: shows on the timeline and goes to the audit log."""
    store.emit(state["incident_id"], agent, text, kind, data)


def brain(state: dict) -> Brain:
    return get_brain(state.get("model", "offline"))


def pace() -> None:
    """A short pause so a person can follow the conversation on screen. Set AEGIS_PACE=0 to switch it off."""
    delay = float(env("AEGIS_PACE", "0.8"))
    if delay:
        time.sleep(delay)
