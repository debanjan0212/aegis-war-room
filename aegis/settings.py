"""Where things live, and the one helper every module uses to read a setting."""

import os
from pathlib import Path

# The repo folder. config/, scenarios/, runbooks/ and voices/ are read from here.
ROOT = Path(os.getenv("AEGIS_HOME") or Path(__file__).resolve().parent.parent)


def env(name: str, default: str = "") -> str:
    """Read a setting from the environment at the moment it is needed."""
    return os.getenv(name, default)
