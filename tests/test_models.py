"""The model toggle's local entry, `aegis models` and reading .env."""

import httpx

from aegis import brain, cli


def test_a_local_model_says_exactly_what_is_missing(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")

    monkeypatch.setattr(brain.importlib.util, "find_spec", lambda _name: None)  # library not installed
    local = next(m for m in brain.models() if m["id"] == "local")
    assert local["missing"] == ['the model libraries (pip install -e ".[local]")']

    monkeypatch.setattr(brain.importlib.util, "find_spec", lambda _name: object())  # library installed

    def not_running(*_a, **_k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(brain.httpx, "get", not_running)
    local = next(m for m in brain.models() if m["id"] == "local")
    assert not local["ready"] and "Ollama app running" in local["missing"][0]

    pulled = httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}]})
    monkeypatch.setattr(brain.httpx, "get", lambda *_a, **_k: pulled)
    local = next(m for m in brain.models() if m["id"] == "local")
    assert local["missing"] == ["the model on this machine (run: ollama pull qwen2.5:7b)"]

    pulled = httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
    monkeypatch.setattr(brain.httpx, "get", lambda *_a, **_k: pulled)
    assert next(m for m in brain.models() if m["id"] == "local")["ready"]


def test_settings_keep_their_type_and_read_the_environment(monkeypatch):
    monkeypatch.setenv("SOME_DEPLOYMENT", "gpt-x")
    assert brain._setting("${SOME_DEPLOYMENT}") == "gpt-x"
    assert brain._setting(8192) == 8192 and brain._setting(0) == 0 and brain._setting({"timeout": 120}) == {"timeout": 120}


def test_models_command_lists_without_calling_anything(capsys):
    class Args:
        test = False

    assert cli._models(Args()) == 0
    out = capsys.readouterr().out
    assert "READY       Offline rules" in out and "--test" in out


def test_dotenv_is_read_but_the_terminal_wins(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "# a comment\nexport AEGIS_ASSISTANT_NAME='Jarvis'\nOLLAMA_MODEL=qwen2.5:7b   # the model\nAEGIS_PORT=9000\n"
    )
    monkeypatch.setattr("aegis.settings.ROOT", tmp_path)
    monkeypatch.delenv("AEGIS_ASSISTANT_NAME", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("AEGIS_PORT", "8000")
    cli._load_env()
    import os

    assert os.environ["AEGIS_ASSISTANT_NAME"] == "Jarvis"
    assert os.environ["OLLAMA_MODEL"] == "qwen2.5:7b"
    assert os.environ["AEGIS_PORT"] == "8000"
