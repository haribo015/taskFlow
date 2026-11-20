"""Pure aggregation functions (easy to unit test)."""

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.models import TaskSnapshot
from app.schemas import AssigneeStats

STATUSES = ("todo", "in_progress", "done")
PRIORITIES = ("low", "medium", "high")


def count_by(tasks: Sequence[TaskSnapshot], attribute: str, keys: Sequence[str]) -> dict[str, int]:
    counter = Counter(getattr(t, attribute) for t in tasks)
    return {key: counter.get(key, 0) for key in keys}


def overdue_count(tasks: Sequence[TaskSnapshot], now: datetime) -> int:
    today = now.date()
    return sum(1 for t in tasks if t.status != "done" and t.due_date and t.due_date < today)


def completed_since(tasks: Sequence[TaskSnapshot], now: datetime, days: int = 7) -> int:
    threshold = now - timedelta(days=days)
    return sum(1 for t in tasks if t.completed_at and t.completed_at >= threshold)


def completion_rate(tasks: Sequence[TaskSnapshot]) -> float:
    if not tasks:
        return 0.0
    return round(sum(1 for t in tasks if t.status == "done") / len(tasks), 3)


def by_assignee(tasks: Sequence[TaskSnapshot]) -> list[AssigneeStats]:
    totals: Counter[int | None] = Counter()
    done: Counter[int | None] = Counter()
    for task in tasks:
        totals[task.assignee_id] += 1
        if task.status == "done":
            done[task.assignee_id] += 1
    return [
        AssigneeStats(assignee_id=assignee, total=total, done=done[assignee])
        for assignee, total in totals.most_common()
    ]


def utcnow() -> datetime:
    return datetime.now(UTC)
