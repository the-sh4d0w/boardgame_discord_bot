"""Utility stuff."""

import datetime
import json
import pathlib
import typing

import discord
import requests


LANG_PATH: str = "path"


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


def check_if_owner(owner_id: int):
    """Check if the user is the bot owner."""
    def predicate(interaction: discord.Interaction) -> bool:
        """Predicate to check if the user is the bot owner.

        Arguments:
            - interaction: the interaction being handled.

        Returns:
            True if owner, False otherwise.
        """
        return interaction.user.id == owner_id
    return discord.app_commands.check(predicate)


def load_languages() -> dict[str, dict[str, str]]:
    """Load all language files.

    Returns:
        The loaded language maps.
    """
    lang_maps: dict[str, dict[str, str]] = {}
    for file in pathlib.Path("lang").iterdir():
        lang_maps[file.name.removesuffix(".json")] = json.loads(
            file.read_text(encoding="utf-8"))
    return lang_maps


def translate(key: str, locale: str, **format_kwargs: typing.Any) -> str:
    """Get text for key in given locale and optionally format with values.

    Arguments:
        - key: the translation key.
        - locale: the locale to translate to.
        - format_kwargs: the keyword arguments for formatting.

    Returns:
        The translated and formatted text.
    """
    # we hot load the language files
    lang_maps: dict[str, dict[str, str]] = load_languages()
    # try and translate with given locale
    if (lang := lang_maps.get(locale)) is not None and lang.get(key) is not None:
        return lang[key].format_map(format_kwargs)
    # fallback to default locale
    if (lang := lang_maps.get("en-GB")) is not None and lang.get(key) is not None:
        return lang[key].format_map(format_kwargs)
    # fail; shouldn't ever happen
    return key
