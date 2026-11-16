"""Connectors: how the war room reads from, and acts on, the outside world.

Every connector offers the same four things, so agents never care which one is live:

    signals(service)              -> {"metrics": {...}, "logs": [...], "traces": [...]}
    changes(service)              -> recent changes: flags, deploys, config
    apply(action, target, value)  -> do one approved action, return what happened
    detect()                      -> alerts for anything unhealthy right now

Pick one with AEGIS_SOURCE: "simulator" (default, runs anywhere) or "otel-demo"
(the real OpenTelemetry Demo shop).
"""

import re
from functools import lru_cache

from ..settings import env

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,60}$")


def safe_name(name: str) -> str:
    """Service and flag names end up inside queries and file edits, so they must be plain names."""
    if not _SAFE_NAME.fullmatch(name or ""):
        raise ValueError(f"not a plain service or flag name: {name!r}")
    return name


@lru_cache
def get_connector():
    if env("AEGIS_SOURCE", "simulator") == "otel-demo":
        from .otel_demo import OtelDemo

        return OtelDemo()
    from .simulator import Simulator

    return Simulator()
