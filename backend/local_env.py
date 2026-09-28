"""Read optional local settings without overriding the process environment."""

import os
from pathlib import Path


def load_local_env():
    env_file = Path(__file__).with_name(".env")
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.isidentifier():
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)
