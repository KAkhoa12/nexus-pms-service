from datetime import datetime

from app.modules.leases.service import _build_due_dates


def test_build_due_dates_starts_from_next_month() -> None:
    due_dates = _build_due_dates(datetime(2026, 3, 20), 12)

    assert len(due_dates) == 12
    assert due_dates[0] == datetime(2026, 4, 20)
    assert due_dates[-1] == datetime(2027, 3, 20)


def test_build_due_dates_handles_month_end() -> None:
    due_dates = _build_due_dates(datetime(2025, 1, 31), 3)

    assert due_dates == [
        datetime(2025, 2, 28),
        datetime(2025, 3, 31),
        datetime(2025, 4, 30),
    ]
