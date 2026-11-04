"""Commander's priority queue of triaged radio reports.

``score = priority*10 + MAYDAY_BONUS (if mayday) + max(0, 10 - age_minutes)``;
acknowledged items get ``ACK_PENALTY`` (-100) so they sink to the bottom but stay visible.
:meth:`PriorityQueue.items` rescores at call time (age moves) and returns a stable
descending sort, so two equal scores keep insertion order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fireline.models import QueueItem

MAYDAY_BONUS = 25.0
RECENCY_WINDOW_MIN = 10.0
ACK_PENALTY = -100.0


def _parse_ts(ts: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def age_minutes(item: QueueItem, now: Optional[datetime] = None) -> float:
    """Minutes since the report was triaged (0 if the timestamp is unreadable)."""
    now = now or datetime.now(timezone.utc)
    then = _parse_ts(item.triage.timestamp) or _parse_ts(item.report.timestamp)
    if then is None:
        return 0.0
    return max(0.0, (now - then).total_seconds() / 60.0)


def compute_score(item: QueueItem, now: Optional[datetime] = None) -> float:
    """Priority with mayday boost and recency bonus; acknowledged items sink by 100."""
    score = item.triage.priority * 10.0
    if item.triage.mayday:
        score += MAYDAY_BONUS
    score += max(0.0, RECENCY_WINDOW_MIN - age_minutes(item, now))
    if item.acknowledged:
        score += ACK_PENALTY
    return round(score, 3)


class PriorityQueue:
    """Insertion-ordered store of :class:`QueueItem` keyed by ``report.id``."""

    def __init__(self) -> None:
        self._items: dict[str, QueueItem] = {}

    # ------------------------------------------------------------- mutation
    def push(self, item: QueueItem) -> QueueItem:
        """Add (or replace by report id) and score the item. Returns the stored item."""
        key = item.report.id
        existing = self._items.get(key)
        if existing is not None and existing.acknowledged and not item.acknowledged:
            item.acknowledged = True  # re-triage of an acked report stays acked
        item.score = compute_score(item)
        self._items[key] = item
        return item

    def ack(self, report_id: str) -> bool:
        """Mark acknowledged; returns False if unknown."""
        item = self._items.get(report_id)
        if item is None:
            return False
        item.acknowledged = True
        item.score = compute_score(item)
        return True

    def remove(self, report_id: str) -> Optional[QueueItem]:
        return self._items.pop(report_id, None)

    def clear(self) -> None:
        self._items.clear()

    # --------------------------------------------------------------- queries
    def get(self, report_id: str) -> Optional[QueueItem]:
        return self._items.get(report_id)

    def items(self, now: Optional[datetime] = None) -> list[QueueItem]:
        """All items rescored now, highest score first, insertion order on ties."""
        for item in self._items.values():
            item.score = compute_score(item, now)
        return sorted(self._items.values(), key=lambda it: -it.score)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, report_id: object) -> bool:
        return report_id in self._items
