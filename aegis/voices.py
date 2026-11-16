"""The voice toggle. Every folder in voices/ is one voice the assistant can speak in.

Two kinds of voice:

    engine: browser   a stock voice that ships with the browser. Free, works today.
    engine: clone     a real person's voice made from their own recording (sample.wav).
                      Needs a consent line in voice.yaml, and the cloning engine, which
                      is the next step in docs/PLAN.md.

To add a voice, copy voices/_template, rename the folder, edit voice.yaml.
"""

from __future__ import annotations

import re

import yaml

from .settings import ROOT

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


def list_voices() -> list[dict]:
    voices = []
    for folder in sorted((ROOT / "voices").iterdir()):
        config = folder / "voice.yaml"
        if not folder.is_dir() or folder.name.startswith("_") or not config.exists() or not _SAFE_ID.fullmatch(folder.name):
            continue
        voice = {"id": folder.name, "engine": "browser", **yaml.safe_load(config.read_text())}
        voice["ready"], voice["problem"] = True, ""
        if voice["engine"] == "clone":
            if not str(voice.get("consent", "")).strip():
                voice["ready"], voice["problem"] = False, "voice.yaml has no consent line from the speaker"
            elif not (folder / str(voice.get("sample", "sample.wav"))).exists():
                voice["ready"], voice["problem"] = False, "the recording (sample.wav) is missing"
            else:
                voice["ready"], voice["problem"] = False, "the cloning engine is not installed yet (see docs/PLAN.md)"
        voices.append(voice)
    return voices
