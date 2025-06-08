"""Boardgame discord bot."""

import datetime
import os
import typing

import discord
import discord.app_commands
import requests


__VERSION__ = 2, 0, 0
"""Bot version as Major.Minor.Patch (semantic versioning)."""

# load environment variables
TOKEN = typing.cast(str, os.environ.get("DISCORD_BOT_TOKEN"))
OWNER = int(typing.cast(str, os.environ.get("OWNER_ID")))

# config values
HOLIDAY_API_URL = "https://feiertage-api.de/api/?nur_land=BY"
QUESTION_TEXT = "Welche Tage (vrmtl. ab 15:00 / 16:00 / 17:00) nächste Woche (KW{0}) passen für" \
    " euch?"
WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
EMOJI_NAME = "Schafkopf_Nein_danke"
EMOJI_ALT = "🤬"

# bot setup
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
bot: discord.Client = discord.Client(intents=intents)
tree: discord.app_commands.CommandTree = discord.app_commands.CommandTree(
    client=bot)


def get_holidays() -> dict[str, str]:
    """Get all holidays for Bavaria.

    Returns:
        Holidays with date and name.
    """
    data: dict[str, dict[str, str]] = requests.get(url=HOLIDAY_API_URL,
                                                   timeout=10).json()
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


@bot.event
async def on_message(message: discord.Message) -> None:
    """Do things on message received.

    Argumemts:
        - message: the actual message.
    """
    message_text: str = message.content.lower()
    if "schafkopf" in message_text and not message.guild is None:
        emoji: discord.Emoji | None = discord.utils.get(
            message.guild.emojis, name=EMOJI_NAME)
        if not emoji is None:
            await message.add_reaction(emoji)
        else:
            await message.add_reaction(EMOJI_ALT)


@tree.command(name="sync", description="Synchronisiere Befehle.")
async def sync(interaction: discord.Interaction) -> None:
    """Sync commands.

    Arguments:
        - interaction: the interaction that triggered the command.
    """
    if interaction.user.id == OWNER:
        synced = await tree.sync()
        await interaction.response.send_message(f"{len(synced)} Befehle synchronisiert.",
                                                ephemeral=True)
    else:
        await interaction.response.send_message("Nur der Besitzer kann diesen Befehl verwenden.",
                                                ephemeral=True)


@tree.command(name="poll", description="Starte eine Umfrage.")
async def create_poll(interaction: discord.Interaction) -> None:
    """Create poll.

    Arguments:
        - interaction: the interaction that triggered the command.
    """
    poll: discord.Poll = discord.Poll(question=QUESTION_TEXT.format(
        datetime.datetime.now().isocalendar().week + 1),
        duration=next_sunday_1800() - datetime.datetime.now(), multiple=True)
    monday: datetime.date = next_monday()
    holidays: dict[str, str] = get_holidays()
    for i in range(5):
        date: datetime.date = monday + datetime.timedelta(i)
        poll_text: str = f"{WEEKDAY_NAMES[i]}, {date.strftime("%d.%m.")}"
        if date.isoformat() in holidays:
            poll_text += f" ({holidays[date.isoformat()]})"
        poll.add_answer(text=poll_text)
    await interaction.response.send_message(poll=poll)


if __name__ == "__main__":
    bot.run(TOKEN)
