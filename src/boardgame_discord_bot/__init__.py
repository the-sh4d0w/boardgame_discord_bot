"""Shared stuff."""

import datetime
import os
import pathlib
import typing

import dotenv

from boardgame_discord_bot import models

# load environment variables
dotenv.load_dotenv()
TOKEN: str = typing.cast(str, os.environ.get("DISCORD_BOT_TOKEN"))
OWNER: int = int(typing.cast(str, os.environ.get("OWNER_ID")))
LOG_CHANNEL: int = int(typing.cast(str, os.environ.get("LOG_CHANNEL")))

# config values
CONFIG_PATH: str = "config.json"
CONFIG: models.Config = models.Config.model_validate_json(
    pathlib.Path(CONFIG_PATH).read_text(encoding="utf-8"))
LOG_PATH: str = "logs"
LOG_FILE: pathlib.Path = pathlib.Path(
    "/", LOG_PATH, f"log_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log")
