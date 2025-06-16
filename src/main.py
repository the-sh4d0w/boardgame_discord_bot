"""Boardgame discord bot."""

import datetime
import os
import pathlib
import random
import typing

import discord
import discord.app_commands
import discord.ext.tasks
import dotenv

import models
import utils

# TODO: translations
# TODO: logging

__VERSION__ = 3, 3, 0
"""Bot version as Major.Minor.Patch (semantic versioning)."""

# load environment variables
dotenv.load_dotenv()
TOKEN: str = typing.cast(str, os.environ.get("DISCORD_BOT_TOKEN"))
OWNER: int = int(typing.cast(str, os.environ.get("OWNER_ID")))

# config values
CONFIG_PATH: str = "config.json"
CONFIG: models.Config = models.Config.model_validate_json(
    pathlib.Path(CONFIG_PATH).read_text(encoding="utf-8"))


# bot setup
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
bot: discord.Client = discord.Client(intents=intents)
tree: discord.app_commands.CommandTree = discord.app_commands.CommandTree(
    client=bot)


class ResponseModal(discord.ui.Modal, title="Antwort"):
    """Response modal."""
    name: discord.ui.TextInput = discord.ui.TextInput(
        label="Text", placeholder="Antworttext hier")

    def __init__(self, message: discord.Message) -> None:
        """Initialise the modal.

        Arguments:
            - message: the message to answer to.
        """
        super().__init__()
        self.message: discord.Message = message

    async def on_submit(self, interaction: discord.Interaction) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
        """
        await self.message.reply(self.name.value)
        await interaction.response.send_message(f"Antwort '{self.name.value}' gesendet.",
                                                ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
            - error: the error that occurred.
        """
        await interaction.response.send_message(f"Ein Fehler trat auf: {error}. Kontaktiere "
                                                f"<@{OWNER}>.", ephemeral=True)


def check_if_owner():
    """Check if the user is the bot owner."""
    def predicate(interaction: discord.Interaction) -> bool:
        """Predicate to check if the user is the bot owner.

        Arguments:
            - interaction: the interaction being handled.

        Returns:
            True if owner, False otherwise.
        """
        return interaction.user.id == OWNER
    return discord.app_commands.check(predicate)


@tree.error
async def on_error(interaction: discord.Interaction,
                   error: discord.app_commands.AppCommandError) -> None:
    """Do stuff on error.

    Arguments:
        - interaction: the interaction being handled.
        - error: the error being raised.
    """
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("Fehlende Berechtigung.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message(f"Fehler: Du bist nicht <@{OWNER}>.",
                                                ephemeral=True)
    else:
        await interaction.response.send_message(f"Ein Fehler trat auf: {error}. Kontaktiere "
                                                f"<@{OWNER}>.", ephemeral=True)


@bot.event
async def on_ready() -> None:
    """Do stuff on ready."""
    activity_task.start()


@bot.event
async def on_message(message: discord.Message) -> None:
    """Do stuff on message received.

    Argumemts:
        - message: the actual message.
    """
    reaction: models.Reaction
    message_text: str = message.content.lower()
    if message.guild:
        for reaction in CONFIG.reactions:
            if reaction.phrase in message_text:
                emoji: discord.Emoji | None = discord.utils.get(
                    message.guild.emojis, name=random.choice(reaction.guild_emojis))
                if emoji:
                    await message.add_reaction(emoji)
                else:
                    await message.add_reaction(reaction.fallback_emoji)


@discord.ext.tasks.loop(minutes=10)
async def activity_task() -> None:
    """Update activity."""
    game: str = random.choice(CONFIG.games)
    await bot.change_presence(activity=discord.Game(name=game))


@tree.command(name="sync", description="Synchronisiere Befehle.")
@discord.app_commands.default_permissions()
@check_if_owner()
async def sync(interaction: discord.Interaction) -> None:
    """Sync commands.

    Arguments:
        - interaction: the interaction being handled.
    """
    synced: list[discord.app_commands.AppCommand] = await tree.sync()
    await interaction.response.send_message(f"{len(synced)} Befehle synchronisiert.",
                                            ephemeral=True)


@tree.command(name="poll", description="Starte eine Umfrage.")
async def create_poll(interaction: discord.Interaction) -> None:
    """Create poll.

    Arguments:
        - interaction: the interaction being handled.
    """
    poll: discord.Poll = discord.Poll(question=CONFIG.question_text.format(
        datetime.datetime.now().isocalendar().week + 1),
        duration=utils.next_sunday_1800() - datetime.datetime.now(), multiple=True)
    monday: datetime.date = utils.next_monday()
    holidays: dict[str, str] = utils.get_holidays(CONFIG.holiday_api_url)
    for i in range(5):
        date: datetime.date = monday + datetime.timedelta(i)
        poll_text: str = f"{CONFIG.weekday_names[i]}, {date.strftime("%d.%m.")}"
        if date.isoformat() in holidays:
            poll_text += f" ({holidays[date.isoformat()]})"
        poll.add_answer(text=poll_text)
    await interaction.response.send_message(poll=poll)


@tree.context_menu(name="react")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.checks.has_permissions(administrator=True)
async def react(interaction: discord.Interaction, message: discord.Message) -> None:
    """React to message.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    emojis: list[str | discord.Emoji | discord.PartialEmoji] = []
    await interaction.response.defer(ephemeral=True)
    for reaction in message.reactions:
        if interaction.user in [user async for user in reaction.users()]:
            emojis.append(reaction.emoji)
            await message.add_reaction(reaction.emoji)
    if len(emojis) > 0:
        await interaction.followup.send("Folgende Reaktionen hinzugefügt: "
                                        + ", ".join(map(str, emojis)), ephemeral=True)
    else:
        await interaction.followup.send("Keine Reaktionen gefunden.", ephemeral=True)


@tree.context_menu(name="respond")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.checks.has_permissions(administrator=True)
async def respond(interaction: discord.Interaction, message: discord.Message) -> None:
    """Respond to message.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    await interaction.response.send_modal(ResponseModal(message))


if __name__ == "__main__":
    bot.run(TOKEN)
