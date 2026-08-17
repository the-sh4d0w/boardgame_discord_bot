"""Utility stuff."""

import datetime
import types
import json
import logging
import pathlib
import queue
import typing
import uuid

import discord
import jinja2
import requests

import models


LANG_PATH: str = "path"
COMMAND: int = 21
REACTION: int = 22
ACTIVITY: int = 23
LOG_LEVEL_COLOURS: dict[int, discord.Colour] = {
    logging.DEBUG: discord.Colour.dark_grey(),
    logging.INFO: discord.Colour.blue(),
    COMMAND: discord.Colour.green(),
    REACTION: discord.Colour.yellow(),
    ACTIVITY: discord.Colour.purple(),
    logging.WARNING: discord.Colour.orange(),
    logging.ERROR: discord.Colour.red(),
    logging.CRITICAL: discord.Colour.dark_red()
}
LOG_LEVEL_EMOJIS: dict[int, str] = {
    logging.DEBUG: "https://cdn.discordapp.com/emojis/1387999726204358796.webp",
    logging.INFO: "https://cdn.discordapp.com/emojis/1387999724853923983.webp",
    COMMAND: "https://cdn.discordapp.com/emojis/1388360110262325409.webp",
    REACTION: "https://cdn.discordapp.com/emojis/1389279750496714916.webp",
    ACTIVITY: "https://cdn.discordapp.com/emojis/1389280670487941141.webp",
    logging.WARNING: "https://cdn.discordapp.com/emojis/1387999723436114082.webp",
    logging.ERROR: "https://cdn.discordapp.com/emojis/1387999720831455403.webp",
    logging.CRITICAL: "https://cdn.discordapp.com/emojis/1387999722144403637.webp"
}
logging.addLevelName(COMMAND, "COMMAND")
logging.addLevelName(REACTION, "REACTION")
logging.addLevelName(ACTIVITY, "ACTIVITY")


class DiscordHandler(logging.Handler):
    """Discord logging handler."""

    def __init__(self, log_queue: queue.Queue[discord.Embed]) -> None:
        """Initialise the handler.

        Arguments:
            - log_queue: the queue to send logs to.
        """
        super().__init__()
        self.log_queue: queue.Queue[discord.Embed] = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        """Log the record by adding it to the queue.

        Arguments:
            - record: the record to log.
        """
        embed: discord.Embed
        match record.levelno:
            case 21 | 22:  # COMMAND, REACTION
                embed = discord.Embed(colour=LOG_LEVEL_COLOURS[record.levelno],
                                      title=record.funcName,
                                      description=record.message,
                                      timestamp=datetime.datetime.fromtimestamp(record.created))
                embed.set_author(name=record.levelname,
                                 icon_url=LOG_LEVEL_EMOJIS[record.levelno])
            case logging.ERROR | logging.CRITICAL:  # ERROR, CRITICAL
                error: tuple[type[Exception], Exception,
                             types.TracebackType] = record.exc_info  # type: ignore
                embed = discord.Embed(colour=LOG_LEVEL_COLOURS[record.levelno],
                                      title=record.funcName,
                                      description=record.message,
                                      timestamp=datetime.datetime.fromtimestamp(record.created))
                embed.set_author(name=record.levelname,
                                 icon_url=LOG_LEVEL_EMOJIS[record.levelno])
                embed.add_field(name="Exception", value=f"```{error[0]}```")
                embed.add_field(name="Traceback",
                                value=f"```{error[1].with_traceback(error[2])}```")
            case _:  # INFO, WARNING, REACTION, DEBUG (below log level)
                embed = discord.Embed(colour=LOG_LEVEL_COLOURS[record.levelno],
                                      title=record.funcName,
                                      description=f"```{record.message}```",
                                      timestamp=datetime.datetime.fromtimestamp(record.created))
                embed.set_author(name=record.levelname,
                                 icon_url=LOG_LEVEL_EMOJIS[record.levelno])
        self.log_queue.put(embed)


class BoardgameTranslator(discord.app_commands.Translator):
    """Boardgame translator."""

    async def translate(self, string: discord.app_commands.locale_str, locale: discord.Locale,
                        context) -> str | None:  # type: ignore
        """Translate the string to the given locale.

        Arguments:
            - string: the translation key.
            - locale: the discord locale to translate to.
            - context: additional translation context.

        Returns:
            Translated string if locale exists, None otherwise.
        """
        return translate(string.message, locale.value)


def log_command(interaction: discord.Interaction) -> None:
    """Log the use of a command.

    Arguments:
        - interaction: interaction related to use of command.
    """
    if interaction.command and interaction.data:
        cmd_mention: str = f"</{interaction.command.name}:{interaction.data.get("id")}>"
        logging.log(stacklevel=2, level=COMMAND, msg=f"Command {cmd_mention} was used by "
                    f"{interaction.user.mention} in <#{interaction.channel_id}>.")


def log_reaction(message: discord.Message, reaction: models.Reaction) -> None:
    """Log the reaction.

    Arguments:
        - message: the message being reacted to.
        - reaction: the reaction.
    """
    logging.log(stacklevel=2, level=REACTION, msg=f"Message by {message.author.mention} in "
                f"<#{message.channel.id}> contained phrase '{reaction.phrase}'. The following "
                f"reaction was added: {reaction.fallback_emoji}.")


def log_activity(activity: discord.BaseActivity) -> None:
    """Log the change of activity.

    Arguments:
        - activity: the new activity.
    """
    logging.log(stacklevel=2, level=ACTIVITY,
                msg=f"Changed activity to {activity}.")


def get_holidays(url: str) -> dict[str, str]:
    """Get all holidays for Bavaria.

    Arguments:
        - url: the url of the holiday api.

    Returns:
        Holidays with date and name.
    """
    today: datetime.date = datetime.date.today()
    data: dict[str, dict[str, str]] = requests.get(url=url + f"&jahr={today.year}",
                                                   timeout=10).json()
    data.update(requests.get(url=url + f"&jahr={today.year+1}",
                             timeout=10).json())
    return {v["datum"]: k for k, v in data.items()}


def next_sunday_1800(date: datetime.date) -> datetime.datetime:
    """Get next sunday 18:00 as datetime.datetime object.

    Arguments:
        - date: date to start from (default today).

    Returns:
        Next sunday 18:00.
    """
    return datetime.datetime.combine(date + datetime.timedelta(
        days=7 if date.weekday() == 6 else 6 - date.weekday()), datetime.time(18, 0))


def next_monday(date: datetime.date) -> datetime.date:
    """Get next monday as datetime.date object.

    Arguments:
        - date: date to start from (default today).

    Returns:
        Next monday.
    """
    return date + datetime.timedelta(days=7 - date.weekday())


def format_date_iso_tz(dt: datetime.datetime) -> str:
    """Formate datetime.datetime as ISO 8601 without spaces as UTC with timezone letter.

    Arguments:
        - dt: datetime to format.

    Returns:
        Formatted datetime.
    """
    return dt.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S") + "Z"


def create_ics(kw: str, start: datetime.datetime, end: datetime.datetime) -> str:
    """Create .ics file.

    Arguments:
        - kw: calendar week.
        - start: start date and time.
        - end: end date and time.

    Returns:
        The content of the .ics file.
    """
    environment: jinja2.Environment = jinja2.Environment(loader=jinja2.FileSystemLoader(
        ".", encoding="utf-8"), keep_trailing_newline=True)
    now: datetime.datetime = datetime.datetime.now()
    cal_uuid: uuid.UUID = uuid.uuid1()
    return environment.get_template("ics.j2").render(
        kw=kw, cal_uuid=cal_uuid, now=format_date_iso_tz(now), start=format_date_iso_tz(start),
        end=format_date_iso_tz(end))


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
