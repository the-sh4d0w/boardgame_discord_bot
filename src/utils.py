"""Utility stuff."""

import datetime

import requests


def get_holidays(url: str) -> dict[str, str]:
    """Get all holidays for Bavaria.

    Arguments:
        - url: the url of the holiday api.

    Returns:
        Holidays with date and name.
    """
    data: dict[str, dict[str, str]] = requests.get(url=url, timeout=10).json()
    return {v["datum"]: k for k, v in data.items()}


def next_sunday_1800(date: datetime.date = datetime.date.today()) -> datetime.datetime:
    """Get next sunday 18:00 as datetime.datetime object.

    Arguments:
        - date: date to start from (default today).

    Returns:
        Next sunday 18:00.
    """
    return datetime.datetime.combine(date + datetime.timedelta(days=6 - date.weekday()),
                                     datetime.time(18))


def next_monday(date: datetime.date = datetime.date.today()) -> datetime.date:
    """Get next monday as datetime.date object.

    Arguments:
        - date: date to start from (default today).

    Returns:
        Next monday.
    """
    return date + datetime.timedelta(days=7 - date.weekday())
