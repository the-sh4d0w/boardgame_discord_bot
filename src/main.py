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
import ui
import utils


# TODO: logging (including in a discord channel)
# TODO: log errors, starting and closing in channel
# TODO: localised times
# TODO: close poll early (context menu command)
# TODO: automatically create event
# TODO: optional alternative end datetime for poll
# TODO: better general error handling
# TODO: improve config validation
# TODO: fix calendar week bug
# TODO: fix sunday 18:00 bug
# TODO: suggest board games (BGG list?)
# TODO: install contexts (DMs, server, ...)
# TODO: manually set activity
# TODO: delete bot messages
# TODO: ascension command (and maybe general role management)
# TODO: move sync to DMs
# TODO: analysis
# TODO: also add english (simplified)
# TODO: more extensive logging of actions on discord (users joining by which  method; users \
#       leaving; etc.) -> maybe?; for statistics?


__VERSION__ = 3, 5, 0
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
    client=bot,
    # FIXME: this doesn't seem to work
    allowed_installs=discord.app_commands.installs.AppInstallationType(guild=True, user=False))


class BoardgameTranslator(discord.app_commands.Translator):
    """Boardgame translator."""

    async def translate(self, string: discord.app_commands.locale_str, locale: discord.Locale,
                        context: discord.app_commands.TranslationContext | None) -> str | None:
        """Translate the string to the given locale.

        Arguments:
            - string: the translation key.
            - locale: the discord locale to translate to.
            - context: additional translation context.

        Returns:
            Translated string if locale exists, None otherwise.
        """
        return utils.translate(string.message, locale.value)


# handling errors
@tree.error
async def on_error(interaction: discord.Interaction,
                   error: discord.app_commands.AppCommandError) -> None:
    """Do stuff on error.

    Arguments:
        - interaction: the interaction being handled.
        - error: the error being raised.
    """
    locale: str = interaction.locale.value
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.followup.send(utils.translate(
            "error_perm", locale, permissions=", ".join(error.missing_permissions)),
            ephemeral=True)
    elif isinstance(error, discord.app_commands.CheckFailure):
        await interaction.followup.send(utils.translate("error_owner", locale, OWNER=OWNER),
                                        ephemeral=True)
    else:
        await interaction.followup.send(utils.translate("error", locale, error=error,
                                                        OWNER=OWNER), ephemeral=True)


# handling events
@bot.event
async def on_ready() -> None:
    """Do stuff on ready."""
    if tree.translator is None:
        await tree.set_translator(BoardgameTranslator())
    if not activity_task.is_running():
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


# tasks
@discord.ext.tasks.loop(minutes=10)
async def activity_task() -> None:
    """Update activity."""
    game: str = random.choice(CONFIG.games)
    await bot.change_presence(activity=discord.Game(name=game))


# commands
@tree.command(name="sync_name", description="sync_desc")
@discord.app_commands.default_permissions()
@utils.check_if_owner(OWNER)
async def sync(interaction: discord.Interaction) -> None:
    """Sync commands.

    Arguments:
        - interaction: the interaction being handled.
    """
    locale: str = interaction.locale.value
    await interaction.response.defer(ephemeral=True)
    synced: list[discord.app_commands.AppCommand] = await tree.sync()
    commands: str = ", ".join(map(lambda cmd: utils.translate(cmd.name, locale),
                                  synced))
    text: str = utils.translate("sync_text", locale, amount=len(synced),
                                synced=commands)
    await interaction.followup.send(content=text, ephemeral=True)


@tree.command(name="poll_name", description="poll_desc")
async def create_poll(interaction: discord.Interaction) -> None:
    """Create poll. Note: this is german-only. Text is NOT loaded from the language files.

    Arguments:
        - interaction: the interaction being handled.
    """
    index: int
    name: str
    poll: discord.Poll = discord.Poll(question=CONFIG.question_text.format(
        datetime.datetime.now().isocalendar().week + 1),
        duration=utils.next_sunday_1800() - datetime.datetime.now(), multiple=True)
    monday: datetime.date = utils.next_monday()
    holidays: dict[str, str] = utils.get_holidays(CONFIG.holiday_api_url)
    for index, name in enumerate(CONFIG.weekday_names):
        date: datetime.date = monday + datetime.timedelta(index)
        poll_text: str = f"{name}, {date.strftime("%d.%m.")}"
        if date.isoformat() in holidays:
            poll_text += f" ({holidays[date.isoformat()]})"
        poll.add_answer(text=poll_text)
    await interaction.response.send_message(poll=poll)


@tree.command(name="msg_name", description="msg_desc")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.checks.has_permissions(administrator=True)
async def send_message(interaction: discord.Interaction) -> None:
    """Send a message.

    Arguments:
        - interaction: the interaction being handled.
    """
    locale: str = interaction.locale.value
    title: str = utils.translate("msg_title", locale)
    label: str = utils.translate("msg_label", locale)
    channel: discord.TextChannel = typing.cast(discord.TextChannel,
                                               interaction.channel)
    await interaction.response.send_modal(ui.MessageModal(title, label, OWNER, channel))


# context menu commands
@tree.context_menu(name="react_name")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.checks.has_permissions(administrator=True)
async def react(interaction: discord.Interaction, message: discord.Message) -> None:
    """React to message.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    locale: str = interaction.locale.value
    emojis: list[str | discord.Emoji | discord.PartialEmoji] = []
    await interaction.response.defer(ephemeral=True)
    for reaction in message.reactions:
        if interaction.user in [user async for user in reaction.users()]:
            emojis.append(reaction.emoji)
            await message.add_reaction(reaction.emoji)
    if len(emojis) > 0:
        await interaction.followup.send(utils.translate("react_success", locale,
                                        reactions=", ".join(map(str, emojis))), ephemeral=True)
    else:
        await interaction.followup.send(utils.translate("react_fail", locale), ephemeral=True)


@tree.context_menu(name="respond_name")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.checks.has_permissions(administrator=True)
async def respond(interaction: discord.Interaction, message: discord.Message) -> None:
    """Respond to message.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    locale: str = interaction.locale.value
    title: str = utils.translate("respond_title", locale)
    label: str = utils.translate("respond_label", locale)
    await interaction.response.send_modal(ui.ResponseModal(title, label, OWNER, message))


if __name__ == "__main__":
    bot.run(TOKEN)
