"""Pydantic models to represent data."""

import pathlib
import zoneinfo

import pydantic
import pydantic_extra_types


class Reaction(pydantic.BaseModel):
    """Reaction model."""
    phrase: str
    guild_emojis: list[str]
    fallback_emoji: str  # sadly can't match emoji, it seems


class Config(pydantic.BaseModel):
    """Config model."""
    fallback_lang: str = pydantic.Field(pattern=r"^[a-z]{2}(-[A-Z]{2}){0,1}$")
    timezone: zoneinfo.ZoneInfo
    holiday_api_url: pydantic.HttpUrl
    question_text: str
    day_names: list[str]
    event_title: str
    event_location: str
    event_description: str
    event_cover_image: pathlib.Path
    games: list[str]
    reactions: list[Reaction]
    game_night_active: bool
    role_colours: list[pydantic_extra_types.Color]
