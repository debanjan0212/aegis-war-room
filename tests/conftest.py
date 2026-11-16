import os

import pytest

os.environ["AEGIS_PACE"] = "0"  # no dramatic pauses in tests


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """Every test gets its own audit log, an empty incident list and a fresh simulator."""
    from aegis import store
    from aegis.connectors import get_connector

    monkeypatch.setenv("AEGIS_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.delenv("AEGIS_API_TOKEN", raising=False)
    monkeypatch.delenv("AEGIS_SOURCE", raising=False)
    store.INCIDENTS.clear()
    get_connector.cache_clear()
    yield
