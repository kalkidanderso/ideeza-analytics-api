"""Shared helpers for time-range and time-series aggregation.

Kept separate from the views so the three endpoints share the same
truncation and range logic instead of each rolling their own.
"""
from datetime import timedelta

from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone

# Maps the public range/compare names to the ORM truncation function.
TRUNC_FUNCS = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
    "year": TruncYear,
}

# How far back each range looks when no explicit window is given.
RANGE_WINDOWS = {
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}


def resolve_range(value, default="month"):
    """Validate a range/compare value, falling back to a sane default."""
    value = (value or default).lower()
    if value not in TRUNC_FUNCS:
        raise ValueError(
            f"Invalid range {value!r}; choose one of {sorted(TRUNC_FUNCS)}."
        )
    return value


def window_start(range_name):
    """Earliest timestamp for a single range window (one week, one year, ...).

    Used by blog-views and top, where ?range=year should mean "the last
    year", not several years.
    """
    return timezone.now() - RANGE_WINDOWS[range_name]


def series_start(range_name, periods=12):
    """Earliest timestamp for a multi-period time series.

    Used by performance, which shows several periods of history (e.g. the
    last 12 months) so growth can be compared period over period.
    """
    return timezone.now() - RANGE_WINDOWS[range_name] * periods


def growth_pct(current, previous):
    """Percentage change vs the previous period.

    Returns None for the first period (no baseline to compare against)
    and 100.0 when growth starts from zero, which reads better than a
    divide-by-zero or an infinite value.
    """
    if previous is None:
        return None
    if previous == 0:
        return 100.0 if current else 0.0
    return round((current - previous) / previous * 100, 2)
