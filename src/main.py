"""Boardgame discord bot."""

import datetime
import logging
import os
import pathlib
import queue
import random
import sys
import typing

import discord
import discord.app_commands
import discord.ext.tasks
import dotenv

import models
import ui
import utils


# TODO: automatically create event when poll closes
# TODO: persistent logs for docker (and log DEBUG to file)
# TODO: log more information (command parameters and error types)
# TODO: more reactions (Mischwald, Mau, Codenames, Leon)
# TODO: role / colour choosing command
# TODO: analysis and statistics command
# TODO: fix calendar week bug
# TODO: fix sunday 18:00 bug (if it even is one)
# TODO: improve config validation
# TODO: suggest board games command (BGG list?)
# TODO: ask user for name on first join or on command?
# TODO: a bit of general cleanup and order


__VERSION__ = 3, 10, 0
"""Bot version as Major.Minor.Patch (semantic versioning)."""

# load environment variables
dotenv.load_dotenv()
TOKEN: str = typing.cast(str, os.environ.get("DISCORD_BOT_TOKEN"))
OWNER: int = int(typing.cast(str, os.environ.get("OWNER_ID")))
LOG_CHANNEL: int = int(typing.cast(str, os.environ.get("LOG_CHANNEL")))

# config values
CONFIG_PATH: str = "config.json"
CONFIG: models.Config = models.Config.model_validate_json(
    pathlib.Path(CONFIG_PATH).read_text(encoding="utf-8"))
LOG_FILE: str = f"log_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log"


# bot setup
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot: discord.Client = discord.Client(intents=intents)
tree: discord.app_commands.CommandTree = discord.app_commands.CommandTree(
    client=bot,
    allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=False))

# logging setup
log_queue: queue.Queue[discord.Embed] = queue.Queue()
logger: logging.Logger = logging.getLogger("discord")
logging.basicConfig(level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S", style="{",
                    format="[{asctime}] [{levelname}] ({funcName}) {message}",
                    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout),
                              utils.DiscordHandler(log_queue)])


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
    send: typing.Callable = interaction.followup.send if interaction.response.is_done() \
        else interaction.response.send_message
    # user with missing permissions tried to use command
    if isinstance(error, discord.app_commands.MissingPermissions):
        miss_perms: str = ", ".join(error.missing_permissions)
        if interaction.command and interaction.data:
            cmd_mention: str = f"</{interaction.command.name}:{interaction.data.get("id")}>"
            logging.exception(msg=f"{interaction.user.mention} tried to use command {cmd_mention}"
                              f" in <#{interaction.channel_id}> while missing the following"
                              f"permissions: {miss_perms}", exc_info=error)
        await send(utils.translate("error_perm", locale, permissions=miss_perms), ephemeral=True)
    # user that is not owner tried to use command
    elif isinstance(error, discord.app_commands.CheckFailure):
        if interaction.command and interaction.data:
            cmd_mention: str = f"</{interaction.command.name}:{interaction.data.get("id")}>"
            logging.exception(msg=f"{interaction.user.mention} tried to use command {cmd_mention}"
                              f" in <#{interaction.channel_id}> despite not being <@{OWNER}>.",
                              exc_info=error)
        await send(utils.translate("error_owner", locale, OWNER=OWNER), ephemeral=True)
    # generic exception occurred
    else:
        if interaction.command and interaction.data:
            cmd_mention: str = f"</{interaction.command.name}:{interaction.data.get("id")}>"
            logging.exception(msg=f"Command {cmd_mention} was used by {interaction.user.mention}"
                              f" in <#{interaction.channel_id}>.", exc_info=error)
        else:
            logging.exception(msg="An error occurred.", exc_info=error)
        await send(utils.translate("error", locale, OWNER=OWNER), ephemeral=True)


# handling events
@bot.event
async def on_ready() -> None:
    """Do stuff on ready."""
    if tree.translator is None:
        await tree.set_translator(utils.BoardgameTranslator())
    if not activity_task.is_running():
        activity_task.start()
    if not log_task.is_running():
        log_task.start()
    # called multiple times; not only when first started
    text: str = f"Bot running version {".".join(map(str, __VERSION__))}."
    logging.info(text)


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
                utils.log_reaction(message, reaction)
                if emoji:
                    await message.add_reaction(emoji)
                else:
                    await message.add_reaction(reaction.fallback_emoji)


# tasks
@discord.ext.tasks.loop(minutes=30)
async def activity_task() -> None:
    """Update activity."""
    activity: discord.BaseActivity = discord.Game(
        name=random.choice(CONFIG.games))
    utils.log_activity(activity)
    await bot.change_presence(activity=activity)


@discord.ext.tasks.loop(seconds=10)
async def log_task() -> None:
    """Log records by actually sending them to the log channel on discord."""
    log_channel: discord.TextChannel = typing.cast(discord.TextChannel,
                                                   bot.get_channel(LOG_CHANNEL))
    while not log_queue.empty():
        embed: discord.Embed = log_queue.get()
        await log_channel.send(embed=embed)


# commands
@tree.command(name="sync", description="sync_desc")
@discord.app_commands.dm_only()
@utils.check_if_owner(OWNER)
async def sync(interaction: discord.Interaction) -> None:
    """Sync commands.

    Arguments:
        - interaction: the interaction being handled.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    await interaction.response.defer(ephemeral=True)
    synced: list[discord.app_commands.AppCommand] = await tree.sync()
    commands: str = ", ".join(map(lambda cmd: utils.translate(cmd.name, locale),
                                  synced))
    text: str = utils.translate("sync_text", locale, amount=len(synced),
                                synced=commands)
    await interaction.followup.send(content=text, ephemeral=True)


@tree.command(name="ascend", description="ascend_desc")
@discord.app_commands.describe(server_id="ascend_server-id")
@discord.app_commands.describe(role_id="ascend_role-id")
@discord.app_commands.describe(user_id="ascend_user-id")
@discord.app_commands.dm_only()
@utils.check_if_owner(OWNER)
async def ascend(interaction: discord.Interaction, server_id: str, role_id: str,
                 user_id: str = str(OWNER)) -> None:
    """Ascend.

    Arguments:
        - interaction: the interaction being handled.
        - server_id: the ID of the server.
        - role_id: the ID of the role.
        - user_id: the ID of the user.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    if (guild := bot.get_guild(int(server_id))) and (role := guild.get_role(int(role_id))) \
            and (member := guild.get_member(int(user_id))):
        await member.add_roles(role)
        await interaction.response.send_message(utils.translate(
            "ascend_success", locale, role=role.mention, member=member.mention), ephemeral=True)
    else:
        await interaction.response.send_message(utils.translate("ascend_fail", locale),
                                                ephemeral=True)


@tree.command(name="descend", description="descend_desc")
@discord.app_commands.describe(server_id="descend_server-id")
@discord.app_commands.describe(role_id="descend_role-id")
@discord.app_commands.describe(user_id="descend_user-id")
@discord.app_commands.dm_only()
@utils.check_if_owner(OWNER)
async def descend(interaction: discord.Interaction, server_id: str, role_id: str,
                  user_id: str = str(OWNER)) -> None:
    """Descend.

    Arguments:
        - interaction: the interaction being handled.
        - server_id: the ID of the server.
        - role_id: the ID of the role.
        - user_id: the ID of the user.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    if (guild := bot.get_guild(int(server_id))) and (role := guild.get_role(int(role_id))) \
            and (member := guild.get_member(int(user_id))):
        await member.remove_roles(role)
        await interaction.response.send_message(utils.translate(
            "descend_success", locale, role=role.mention, member=member.mention), ephemeral=True)
    else:
        await interaction.response.send_message(utils.translate("descend_fail", locale),
                                                ephemeral=True)


@tree.command(name="poll", description="poll_desc")
@discord.app_commands.describe(hours="poll_hours")
@discord.app_commands.guild_only()
async def create_poll(interaction: discord.Interaction, hours: typing.Optional[int] = None) \
        -> None:
    """Create poll. Note: this is german-only. Text is NOT loaded from the language files.

    Arguments:
        - interaction: the interaction being handled.
        - hours: poll duration in hours.
    """
    utils.log_command(interaction)
    await interaction.response.defer()
    # poll setup
    duration: datetime.timedelta
    if hours and 0 < hours <= 768:
        duration = datetime.timedelta(hours=hours)
    else:
        duration = utils.next_sunday_1800() - datetime.datetime.now()
    kw: int = datetime.datetime.now().isocalendar().week + 1
    monday: datetime.date = utils.next_monday()
    holidays: dict[str, str] = utils.get_holidays(CONFIG.holiday_api_url)
    day_names: list[str] = ["Montag", "Dienstag",
                            "Mittwoch", "Donnerstag", "Freitag"]
    # create actual poll
    poll: discord.Poll = discord.Poll(question=CONFIG.question_text.format_map({"kw": kw}),
                                      duration=duration, multiple=True)
    for i in range(5):
        date: datetime.date = monday + datetime.timedelta(i)
        poll_text: str = f"{day_names[i]}, {date.strftime("%d.%m.")}"
        if date.isoformat() in holidays:
            poll_text += f" ({holidays[date.isoformat()]})"
        poll.add_answer(text=poll_text)
    await interaction.followup.send(poll=poll)


@tree.command(name="msg", description="msg_desc")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def send_message(interaction: discord.Interaction) -> None:
    """Send a message.

    Arguments:
        - interaction: the interaction being handled.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    title: str = utils.translate("msg_title", locale)
    label: str = utils.translate("msg_label", locale)
    channel: discord.TextChannel = typing.cast(discord.TextChannel,
                                               interaction.channel)
    await interaction.response.send_modal(ui.MessageModal(title, label, OWNER, channel))


# context menu commands
@tree.context_menu(name="react")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def react(interaction: discord.Interaction, message: discord.Message) -> None:
    """React to message.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    utils.log_command(interaction)
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


@tree.context_menu(name="respond")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def respond(interaction: discord.Interaction, message: discord.Message) -> None:
    """Respond to message.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    title: str = utils.translate("respond_title", locale)
    label: str = utils.translate("respond_label", locale)
    await interaction.response.send_modal(ui.ResponseModal(title, label, OWNER, message))


@tree.context_menu(name="close")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def close_poll(interaction: discord.Interaction, message: discord.Message) -> None:
    """Close a bot poll.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    bot_id: int = typing.cast(discord.ClientUser, bot.user).id
    if message.poll:
        if message.author.id == bot_id:
            if not message.poll.is_finalised():
                await message.poll.end()
                await interaction.response.send_message(utils.translate("close_success", locale),
                                                        ephemeral=True)
            else:
                await interaction.response.send_message(utils.translate("close_already", locale),
                                                        ephemeral=True)
        else:
            await interaction.response.send_message(utils.translate("close_not-bot", locale,
                                                                    bot=bot_id), ephemeral=True)
    else:
        await interaction.response.send_message(utils.translate("close_not-poll", locale),
                                                ephemeral=True)


@tree.context_menu(name="delete")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def delete_msg(interaction: discord.Interaction, message: discord.Message) -> None:
    """Delete a bot message.

    Arguments:
        - interaction: the interaction being handled.
        - message: the message that the context menu command was executed on.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    bot_id: int = typing.cast(discord.ClientUser, bot.user).id
    if message.author.id == typing.cast(discord.ClientUser, bot.user).id:
        await message.delete()
        await interaction.response.send_message(utils.translate("delete_success", locale),
                                                ephemeral=True)
    else:
        await interaction.response.send_message(utils.translate("delete_fail", locale,
                                                                bot=bot_id), ephemeral=True)


if __name__ == "__main__":
    bot.run(token=TOKEN, log_handler=None)
