"""
Deterministic trip sanity checks (put this file at travel_agent/tools/validation.py).

The router LLM only EXTRACTS facts (cities, dates, activities, a travel-time estimate).
This module DECIDES, because Python is exact at date maths and the LLM is not.
validate_trip returns a user-facing reason string if the trip is invalid, else None.
"""

import math
import re
from datetime import date
from typing import Optional

# A round trip must leave at least this many hours at the destination.
MIN_HOURS_AT_DESTINATION = 12

_NOISE_WORDS = {"junction", "jn", "station", "city", "railway", "terminus"}


def _parse_iso(value: str) -> Optional[date]:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None  # unknown or malformed: skip date checks instead of crashing


def _norm_place(place: str) -> str:
    words = re.findall(r"[a-z0-9]+", (place or "").lower())
    return "".join(w for w in words if w not in _NOISE_WORDS)


def _pretty(d: date) -> str:
    return f"{d.day} {d:%B %Y}"


def validate_trip(decision, today: date) -> Optional[str]:
    """Checks, in order: same place, past dates, end before start,
    time feasibility, then activity conflicts reported by the router."""
    origin = getattr(decision, "origin", "") or ""
    destination = getattr(decision, "destination", "") or ""
    start = _parse_iso(getattr(decision, "start_date", ""))
    end = _parse_iso(getattr(decision, "end_date", ""))

    # 1. Origin and destination are the same place
    if origin and destination and _norm_place(origin) == _norm_place(destination):
        return f"Your starting point and destination are the same place ({destination.strip()})."

    # 2. Trip in the past
    for label, d in (("starts", start), ("ends", end)):
        if d is not None and d < today:
            return (f"Your trip {label} on {_pretty(d)}, which is in the past "
                    f"(today is {_pretty(today)}). Please give me upcoming dates.")

    # 3. Return before departure
    if start and end and end < start:
        return (f"Your return date ({_pretty(end)}) is before your departure date "
                f"({_pretty(start)}).")

    # 4. Round trip that does not fit the travel time
    one_way = float(getattr(decision, "estimated_one_way_train_hours", 0) or 0)
    if getattr(decision, "is_round_trip", False) and start and end and one_way > 0:
        days_given = (end - start).days + 1
        available = days_given * 24
        needed = 2 * one_way + MIN_HOURS_AT_DESTINATION
        if needed > available:
            min_days = math.ceil(needed / 24)
            same_day = "a same-day return is not possible. " if start == end else ""
            return (f"{origin.strip() or 'The origin'} to {destination.strip() or 'the destination'} "
                    f"takes about {one_way:g} hours one way by train, so {same_day}"
                    f"a round trip needs at least {min_days} days and you gave {days_given}. "
                    f"Please extend your dates or choose a closer destination.")

    # 5. Activity that cannot be done at the destination (judged by the router LLM)
    conflict = (getattr(decision, "activity_conflicts", "") or "").strip()
    if conflict:
        return conflict

    return None