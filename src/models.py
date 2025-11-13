"""Pydantic models to represent data."""

import pathlib
import zoneinfo

import pydantic


class Reaction(pydantic.BaseModel):
    """Reaction model."""
    phrase: str
    guild_emojis: list[str]
    fallback_emoji: str


class Config(pydantic.BaseModel):
    """Config model."""
    fallback_lang: str
    timezone: zoneinfo.ZoneInfo
    holiday_api_url: str
    question_text: str
    day_names: list[str]
    event_title: str
    event_location: str
    event_description: str
    event_cover_image: pathlib.Path
    games: list[str]
    reactions: list[Reaction]
    game_night_active: bool
