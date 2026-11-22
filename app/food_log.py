"""In-memory food discovery records; no Tk, clock reads, or file I/O.

Schema: runtime['food_log'][member_id][food_id] =
    {'outcome': 'favourite|normal|disliked', 'first_fed': epoch_seconds}

Only an accepted feed may call record(). Full refusal and invalid food requests
must not call it. The caller owns persistence and must not claim a durable
unlock until its save succeeds. Legacy feed_count is never used for migration.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from app.engine.contracts import MEMBER_KEYS
from app.foods import FOOD_ITEMS

FOOD_LOG_VERSION = 1
ALLOWED_OUTCOMES = frozenset({'favourite', 'normal', 'disliked'})
_MEMBERS = frozenset(MEMBER_KEYS)
_FOODS = frozenset(food['id'] for food in FOOD_ITEMS)


def _valid_timestamp(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return value >= 0 and math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _clean_log(raw: object) -> dict[str, dict[str, dict[str, Any]]]:
    """Copy valid records, dropping malformed rows without losing valid peers."""
    clean: dict[str, dict[str, dict[str, Any]]] = {}
    if not isinstance(raw, Mapping):
        return clean
    for member, foods in raw.items():
        if member not in _MEMBERS or not isinstance(foods, Mapping):
            continue
        entries = {}
        for food_id, entry in foods.items():
            if food_id not in _FOODS or not isinstance(entry, Mapping):
                continue
            outcome = entry.get('outcome')
            timestamp = entry.get('first_fed')
            if not isinstance(outcome, str) or outcome not in ALLOWED_OUTCOMES:
                continue
            if not _valid_timestamp(timestamp):
                continue
            entries[food_id] = {'outcome': outcome, 'first_fed': timestamp}
        if entries:
            clean[member] = entries
    return clean


def normalize(runtime: dict[str, Any]) -> bool:
    """Clean food_log in place after load; return whether its value changed.

    A missing field becomes an empty log. Invalid/unknown members, food IDs,
    outcomes, and timestamps are discarded per record. Unrelated runtime keys
    remain untouched. The version constant describes this API; no disk envelope
    or migration is written here.
    """
    clean = _clean_log(runtime.get('food_log'))
    changed = 'food_log' not in runtime or runtime['food_log'] != clean
    runtime['food_log'] = clean
    return changed


def record(runtime: dict[str, Any], member: str, food_id: str,
           outcome: str, ts: int | float) -> bool:
    """Record the first accepted feed; return True only for a new discovery.

    Invalid arguments return False without touching runtime. A previously valid
    discovery keeps its original outcome and first_fed timestamp. Prefer the
    underlying favourite/normal outcome for a full drink. Display-only results
    such as drink_full/refused_full are not discoveries. No preferences are
    inferred here: the feeding coordinator supplies the actual outcome.
    """
    if (not isinstance(member, str) or member not in _MEMBERS
            or not isinstance(food_id, str) or food_id not in _FOODS
            or not isinstance(outcome, str) or outcome not in ALLOWED_OUTCOMES
            or not _valid_timestamp(ts)):
        return False
    normalize(runtime)
    foods = runtime['food_log'].setdefault(member, {})
    if food_id in foods:
        return False
    foods[food_id] = {'outcome': outcome, 'first_fed': ts}
    return True


def outcomes(runtime: Mapping[str, Any], member: str) -> dict[str, str]:
    """Return a detached, filtered food_id -> outcome view, without mutation."""
    if not isinstance(member, str) or member not in _MEMBERS:
        return {}
    entries = _clean_log(runtime.get('food_log')).get(member, {})
    return {food_id: entry['outcome'] for food_id, entry in entries.items()}
