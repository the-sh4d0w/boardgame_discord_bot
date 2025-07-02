"""Pydantic models to represent data."""

import pydantic


class Reaction(pydantic.BaseModel):
    """Reaction model."""
    phrase: str
    guild_emojis: list[str]
    fallback_emoji: str


class Config(pydantic.BaseModel):
    """Config model."""
    fallback_lang: str
    holiday_api_url: str
    question_text: str
    games: list[str]
    reactions: list[Reaction]
