from datetime import datetime, time, timedelta, tzinfo
from unittest.mock import MagicMock

import pytest

from hueplanner.planner.actions.schedule import (
    get_closest_next,
    get_closest_next_prev,
    get_closest_prev,
    get_closest_prev_next,
)
from hueplanner.scheduler import ScheduleOnce, SchedulePeriodic

# Assuming the modified functions are imported from the module


# Helper function to create a mock SchedulerTask
def create_mock_task(schedule):
    mock_task = MagicMock()
    mock_task.schedule = schedule
    return mock_task


# Fixed pivot time for testing
pivot_time = datetime(2024, 9, 14, 12, 0)  # Fixed date for reproducibility


@pytest.mark.parametrize(
    "task_type, overlap",
    [
        (ScheduleOnce, False),
        (ScheduleOnce, True),
        (SchedulePeriodic, False),
        (SchedulePeriodic, True),
    ],
)
def test_get_closest_prev(task_type, overlap):
    if task_type is ScheduleOnce:
        # ScheduleOnce at 10:00 AM on the pivot day
        schedule = ScheduleOnce(run_at=datetime.combine(pivot_time.date(), time(10, 0)))
    else:
        # SchedulePeriodic every 2 hours starting from 8:00 AM on the pivot day
        schedule = SchedulePeriodic(interval=timedelta(hours=2), start_at=time(8, 0))

    # Create tasks
    tasks = (create_mock_task(schedule),)

    closest_task = get_closest_prev(tasks, overlap, pivot=pivot_time)

    if overlap:
        assert closest_task is not None
    else:
        if task_type is ScheduleOnce:
            assert closest_task is not None  # Should find the previous task for ScheduleOnce with overlap
        else:
            assert closest_task is not None  # Should find the closest previous periodic task


@pytest.mark.parametrize(
    "task_type, overlap",
    [
        (ScheduleOnce, False),
        (ScheduleOnce, True),
        (SchedulePeriodic, False),
        (SchedulePeriodic, True),
    ],
)
def test_get_closest_next(task_type, overlap):
    if task_type is ScheduleOnce:
        # ScheduleOnce at 2:00 PM on the pivot day
        schedule = ScheduleOnce(run_at=datetime.combine(pivot_time.date(), time(14, 0)))
    else:
        # SchedulePeriodic every 2 hours starting from 2:00 PM on the pivot day
        schedule = SchedulePeriodic(interval=timedelta(hours=2), start_at=time(14, 0))

    # Create tasks
    tasks = (create_mock_task(schedule),)

    closest_task = get_closest_next(tasks, overlap, pivot=pivot_time)

    if overlap:
        assert closest_task is not None
    else:
        assert closest_task is not None  # Should find the closest next task for both Once and Periodic


@pytest.mark.parametrize(
    "task_type, overlap",
    [
        (ScheduleOnce, False),
        (ScheduleOnce, True),
        (SchedulePeriodic, False),
        (SchedulePeriodic, True),
    ],
)
def test_get_closest_next_prev(task_type, overlap):
    if task_type is ScheduleOnce:
        # ScheduleOnce at 1:00 PM on the pivot day
        schedule = ScheduleOnce(run_at=datetime.combine(pivot_time.date(), time(13, 0)))
    else:
        # SchedulePeriodic every 3 hours starting from 1:00 PM on the pivot day
        schedule = SchedulePeriodic(interval=timedelta(hours=3), start_at=time(13, 0))

    # Create tasks
    tasks = (create_mock_task(schedule),)

    closest_task = get_closest_next_prev(tasks, overlap, pivot=pivot_time)

    if overlap:
        assert closest_task is not None
    else:
        assert closest_task is not None  # Should find the closest task for both Once and Periodic


@pytest.mark.parametrize(
    "task_type, overlap",
    [
        (ScheduleOnce, False),
        (ScheduleOnce, True),
        (SchedulePeriodic, False),
        (SchedulePeriodic, True),
    ],
)
def test_get_closest_prev_next(task_type, overlap):
    if task_type is ScheduleOnce:
        # ScheduleOnce at 11:00 AM on the pivot day
        schedule = ScheduleOnce(run_at=datetime.combine(pivot_time.date(), time(11, 0)))
    else:
        # SchedulePeriodic every 2 hours starting from 11:00 AM on the pivot day
        schedule = SchedulePeriodic(interval=timedelta(hours=2), start_at=time(11, 0))

    # Create tasks
    tasks = (create_mock_task(schedule),)

    closest_task = get_closest_prev_next(tasks, overlap, pivot=pivot_time)

    if overlap:
        assert closest_task is not None
    else:
        assert closest_task is not None  # Should find the closest task for both Once and Periodic
