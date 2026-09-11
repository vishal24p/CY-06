"""Small environment loader for local development."""

from __future__ import annotations

import os
from pathlib import Path


def load_project_env(path: Path | None = None) -> None:
    """Load missing values from the project .env without replacing process env."""
    env_file = path or Path(__file__).resolve().parents[2] / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or name in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[name] = value
