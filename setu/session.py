"""In-memory per-user session store (resets when the process restarts)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_SESSIONS: dict[str, dict[str, Any]] = {}


def default_session() -> dict[str, Any]:
    return {
        "phase": "welcome_language",
        "language": None,
        "journey_id": None,
        "slots": {},
        "matched_schemes": [],
        "selected_scheme_sn": None,
        "pending_help": False,
        "last_prompt": None,
        "path": None,
        "category_id": None,
        "state_scope": None,
        "hub_screen": 1,
        "pension_slice": False,
        "cat_q_index": 0,
    }


def get_session(user_id: str) -> dict[str, Any]:
    if user_id not in _SESSIONS:
        _SESSIONS[user_id] = default_session()
    return _SESSIONS[user_id]


def reset_session(user_id: str) -> dict[str, Any]:
    _SESSIONS[user_id] = default_session()
    return _SESSIONS[user_id]


def snapshot(user_id: str) -> dict[str, Any]:
    return deepcopy(get_session(user_id))
