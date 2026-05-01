"""Configuration management for Jira connections.

Stores named connection profiles (url, email, api_token) in ~/.jira-sync/config.json.
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".jira-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {"connections": {}}


def _save(data: dict):
    _ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def list_connections() -> list[str]:
    """Return names of all saved connections."""
    data = _load()
    return list(data.get("connections", {}).keys())


def get_connection(name: str) -> dict | None:
    """Get a connection profile by name, or None if not found."""
    data = _load()
    return data.get("connections", {}).get(name)


def save_connection(name: str, url: str, email: str, api_token: str):
    """Save (or update) a named connection profile."""
    data = _load()
    data.setdefault("connections", {})[name] = {
        "url": url.rstrip("/"),
        "email": email,
        "api_token": api_token,
    }
    _save(data)


def delete_connection(name: str) -> bool:
    """Delete a connection profile. Returns True if it existed."""
    data = _load()
    if name in data.get("connections", {}):
        del data["connections"][name]
        _save(data)
        return True
    return False
