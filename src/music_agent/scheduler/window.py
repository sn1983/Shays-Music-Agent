"""Deciding whether a run that just fired should publish.

GitHub Actions does not promise punctual cron triggers — a job scheduled for
the top of the hour routinely starts 20-70 minutes late. A guard that demands
an exact local hour therefore skips most real runs, which is exactly what
happened on the first scheduled days.

The rule is instead "at or after the publishing hour", combined with the
once-per-day check in the pipeline: several trigger times can be scheduled,
the first one that lands after the hour publishes, and the rest do nothing.
"""

from __future__ import annotations


def is_due(current_hour: int, not_before_hour: int | None) -> bool:
    """Whether a run firing at ``current_hour`` local time should publish.

    ``not_before_hour`` of ``None`` means "always due" — the caller did not ask
    for a time window at all (a manual run, or a cron that already fires at the
    right local time).
    """
    if not_before_hour is None:
        return True
    return current_hour >= not_before_hour
