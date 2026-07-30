"""The publishing window must tolerate GitHub's late cron triggers.

The first scheduled days were lost to an exact-hour check: both triggers fired
late (21:19 and 22:09 local for a 20:00 slot) and neither matched.
"""

from __future__ import annotations

import pytest

from music_agent.scheduler.window import is_due


def test_a_run_at_the_publishing_hour_is_due():
    assert is_due(20, 20)


@pytest.mark.parametrize("delayed_hour", [21, 22, 23])
def test_a_late_trigger_still_publishes(delayed_hour):
    # This is the case that silently skipped: cron said 20:00, GitHub fired at 21:19.
    assert is_due(delayed_hour, 20)


@pytest.mark.parametrize("early_hour", [0, 12, 19])
def test_a_run_before_the_publishing_hour_is_not_due(early_hour):
    assert not is_due(early_hour, 20)


def test_no_window_means_always_due():
    # A manual run has no window to respect.
    assert is_due(3, None)


def test_the_summer_schedule_publishes_on_the_first_slot():
    # Israel is UTC+3 in summer: the 17:07 UTC slot is 20:07 local.
    summer_local_hours = [20, 21, 22, 23]  # the four UTC slots, converted
    assert [is_due(hour, 20) for hour in summer_local_hours] == [True, True, True, True]


def test_the_winter_schedule_skips_the_first_slot():
    # Israel is UTC+2 in winter: the 17:07 UTC slot is only 19:07 local, so it
    # must not publish an hour early; the next slot is 20:07 and does.
    winter_local_hours = [19, 20, 21, 22]
    assert [is_due(hour, 20) for hour in winter_local_hours] == [False, True, True, True]
