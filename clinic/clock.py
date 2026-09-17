"""
Simulated Clock and Time Management for the Clinic System.
Coordinates scheduled automated jobs (morning reminders, no-show auto-marking).
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union


def parse_datetime(val: Union[str, int, float, datetime]) -> datetime:
    """Robustly parse datetime from ISO string, timestamp, or datetime object."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val)
    if isinstance(val, str):
        val = val.strip()
        # Handle trailing Z
        if val.endswith("Z"):
            val = val[:-1]
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        # Fallback to fromisoformat
        try:
            return datetime.fromisoformat(val)
        except Exception as e:
            raise ValueError(f"Cannot parse datetime string: '{val}'") from e
    raise TypeError(f"Unsupported datetime type: {type(val)}")


class SystemClock:
    """
    Thread-safe simulated clock that triggers automated jobs on time advancements.
    """

    def __init__(self, initial_time: Optional[datetime] = None):
        self._lock = threading.RLock()
        self._current_time: datetime = initial_time if initial_time is not None else datetime.now()
        self._listeners: List[Callable[[datetime], None]] = []

    def get_time(self) -> datetime:
        with self._lock:
            return self._current_time

    def get_time_iso(self) -> str:
        with self._lock:
            return self._current_time.isoformat()

    def set_time(self, new_time: Union[str, int, float, datetime]) -> datetime:
        dt = parse_datetime(new_time)
        with self._lock:
            self._current_time = dt
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(dt)
            except Exception:
                pass
        return dt

    def register_listener(self, listener: Callable[[datetime], None]) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)
