"""Boardgame discord bot."""

import asyncio
import datetime
import io
import logging
import pathlib
import queue
import random
import sys
import tomllib
import typing

import discord
import discord.app_commands
import discord.ext.commands  # pyright: ignore[reportMissingTypeStubs]
import discord.ext.tasks  # pyright: ignore[reportMissingTypeStubs]

# I hate this; Docker and relative imports are horrible, but at least it works now
from boardgame_discord_bot import TOKEN, OWNER, LOG_CHANNEL, CONFIG, LOG_FILE
from boardgame_discord_bot import models
from boardgame_discord_bot import ui
from boardgame_discord_bot import utils
from boardgame_discord_bot.cogs import administration
from boardgame_discord_bot.cogs import democracy
from boardgame_discord_bot.cogs import event as event_cog
from boardgame_discord_bot.cogs import moderation

# TODO: analysis and statistics command
# TODO: weekday roles per week/poll
# TODO: log tasks, etc. (basically all bot actions)
# TODO: some more info on tasks -> maybe a status command?; or channel?


pyproject_toml: dict[str, typing.Any] = tomllib.loads(
    pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
__VERSION__: str = pyproject_toml["project"]["version"]
"""Bot version as Major.Minor.Patch (semantic versioning)."""


# bot setup
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot: discord.ext.commands.Bot = discord.ext.commands.Bot(
    command_prefix="!!!", intents=intents,
    allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=False))
tree: discord.app_commands.CommandTree = bot.tree
dev: bool = False

# add cogs
asyncio.run(bot.add_cog(administration.AdministrationCog(bot=bot)))
asyncio.run(bot.add_cog(democracy.DemocracyCog(bot=bot)))
asyncio.run(bot.add_cog(event_cog.EventCog(bot=bot)))
asyncio.run(bot.add_cog(moderation.ModerationCog(bot=bot)))

# logging setup
log_queue: queue.Queue[discord.Embed] = queue.Queue()
logger: logging.Logger = logging.getLogger("discord")
discord_handler: utils.DiscordHandler = utils.DiscordHandler(log_queue)
discord_handler.setLevel(logging.INFO)
logging.basicConfig(level=logging.DEBUG, datefmt="%Y-%m-%d %H:%M:%S", style="{",
                    format="[{asctime}] [{levelname}] ({funcName}) {message}",
                    handlers=[logging.FileHandler(LOG_FILE.resolve()),
                              logging.StreamHandler(sys.stdout),
                              discord_handler])


# handling errors
@tree.error
async def on_error(interaction: discord.Interaction,
                   error: discord.app_commands.AppCommandError) -> None:
    """Do stuff on error.

    Arguments:
        interaction: the interaction being handled.
        error: the error being raised.
    """
    locale: str = interaction.locale.value
    send = interaction.followup.send if interaction.response.is_done() \
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
    if not role_task.is_running():
        role_task.start()
    # called multiple times; not only when first started
    text: str = f"Bot running version {__VERSION__ + (" (dev)" if dev else "")}."
    if bot.application:
        dev_text: str = " (dev)\n:warning: Bot may be unstable. Use at your own risk."
        await bot.application.edit(description=f"v{__VERSION__ + (dev_text if dev else "")}")
    logging.info(text)


@bot.event
async def on_message(message: discord.Message) -> None:
    """Do stuff on message received.

    Argumemts:
        message: the actual message.
    """
    reaction: models.Reaction
    message_text: str = message.content.lower()
    bot_id: int = typing.cast(discord.ClientUser, bot.user).id
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
        if message.type == discord.MessageType.poll_result and message.author.id == bot_id:
            # check if we have only one poll result
            if len(message.embeds[0].fields) > 3:
                # cursed, but it works
                kw: str = typing.cast(str, message.embeds[0].fields[0].value
                                      ).split("(")[-1].split(")")[0]
                logging.info("Created scheduled event %s.",
                             CONFIG.event_title.format_map({"kw": kw}))
                start_time: datetime.datetime = datetime.datetime.strptime(typing.cast(
                    str, message.embeds[0].fields[-1].value).split()[1], "%d.%m.%Y").astimezone(
                        CONFIG.timezone).replace(hour=16, minute=0)
                end_time: datetime.datetime = start_time.replace(hour=22)
                event: discord.ScheduledEvent = await message.guild.create_scheduled_event(
                    name=CONFIG.event_title.format_map({"kw": kw}),
                    location=CONFIG.event_location, description=CONFIG.event_description,
                    image=CONFIG.event_cover_image.read_bytes(),
                    start_time=start_time, end_time=end_time,
                    entity_type=discord.EntityType.external,
                    privacy_level=discord.PrivacyLevel.guild_only)
                await message.channel.send("Ergebnis der Umfrage war "
                                           f"<t:{int(start_time.timestamp())}:D>.\n{event.url}")
                await message.channel.send(file=discord.File(
                    fp=io.StringIO(utils.create_ics(
                        kw=kw, start=start_time, end=end_time)),  # type: ignore
                    filename="Spieleabend.ics"))


# tasks
@discord.ext.tasks.loop(minutes=15)
async def activity_task() -> None:
    """Update activity."""
    activity: discord.BaseActivity
    if dev:
        activity = discord.Game(name="In active development")
    elif CONFIG.game_night_active:
        activity = discord.Game(name="Spieleabend")
    else:
        random.seed(datetime.datetime.now().isoformat())
        activity = discord.Game(
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


@discord.ext.tasks.loop(time=datetime.time(hour=22))
async def role_task() -> None:
    """Reset weekday roles."""
    if datetime.date.today().weekday() == 6:
        kw: int = datetime.datetime.now().isocalendar().week
        for guild in bot.guilds:
            for role_name in CONFIG.day_names:
                role_name = f"{role_name} (KW{kw:02})"
                for role in guild.roles:
                    if role.name == role_name:
                        await role.delete(reason="Role reset by Boardgame Bot.")


# slash commands; not worth moving
@tree.command(name="msg", description="msg_desc")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def send_message(interaction: discord.Interaction) -> None:
    """Send a message.

    Arguments:
        interaction: the interaction being handled.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    channel: discord.TextChannel = typing.cast(discord.TextChannel,
                                               interaction.channel)
    await interaction.response.send_modal(ui.MessageModal(locale, OWNER, channel))


@tree.command(name="quote", description="quote_desc")
@discord.app_commands.guild_only()
async def quote(interaction: discord.Interaction) -> None:
    """Send formatted quote.

    Arguments:
        interaction: the interaction being handled.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    channel: discord.TextChannel = typing.cast(discord.TextChannel,
                                               interaction.channel)
    await interaction.response.send_modal(ui.QuoteModal(locale, OWNER, channel))


# message commands; context_menu can't seem to be properly used ina  Cog
@tree.context_menu(name="react")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def react(interaction: discord.Interaction, message: discord.Message) -> None:
    """React to message.

    Arguments:
        interaction: the interaction being handled.
        message: the message that the context menu command was executed on.
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
        interaction: the interaction being handled.
        message: the message that the context menu command was executed on.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    await interaction.response.send_modal(ui.ResponseModal(locale, OWNER, message))


@tree.context_menu(name="close")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def close_poll(interaction: discord.Interaction, message: discord.Message) -> None:
    """Close a bot poll.

    Arguments:
        interaction: the interaction being handled.
        message: the message that the context menu command was executed on.
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
        interaction: the interaction being handled.
        message: the message that the context menu command was executed on.
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


# user commands; context_menu can't seem to be properly used ina  Cog
@tree.context_menu(name="modview")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def modview(interaction: discord.Interaction, member: discord.Member) -> None:
    """Get modview info.

    Arguments:
        interaction: the interaction being handled.
        member: the member that the context menu command was executed on.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    await interaction.response.defer(ephemeral=True)
    messages: int = 0
    links: int = 0
    media: int = 0
    for channel in member.guild.text_channels:
        async for message in channel.history(limit=None):
            if message.author.id == member.id:
                messages += 1
                if len(message.embeds) > 0 and message.embeds[0].url:
                    links += 1
                if len(message.attachments) > 0:
                    media += 1
    permissions:  list[str] = [perm[0] for perm in member.guild_permissions
                               if perm[1]]
    user_embed: discord.Embed = discord.Embed(colour=member.colour,
                                              title=member.display_name)
    user_embed.set_author(name=member.name, icon_url=member.display_avatar.url)
    # activity information: messages, links, media
    activity_embed: discord.Embed = discord.Embed(
        colour=member.colour, title=utils.translate("modview_activity", locale))
    activity_embed.add_field(name=utils.translate("modview_messages", locale),
                             value=messages)
    activity_embed.add_field(name=utils.translate("modview_links", locale),
                             value=links)
    activity_embed.add_field(name=utils.translate("modview_media", locale),
                             value=media)
    # permission information: amount, permissions
    perm_embed: discord.Embed = discord.Embed(colour=member.colour,
                                              title=utils.translate("modview_mod-perms", locale))
    perm_embed.add_field(name=utils.translate("modview_amount-perms", locale),
                         value=len(permissions))
    perm_embed.add_field(name=utils.translate("modview_perms", locale),
                         value=", ".join(permissions))
    # role information: roles, top role
    roles_embed: discord.Embed = discord.Embed(colour=member.colour,
                                               title=utils.translate("modview_roles", locale))
    roles_embed.add_field(name=utils.translate("modview_roles", locale), value=", ".join(map(
        lambda r: r.mention if r.name != "@everyone" else r.name, member.roles)))
    roles_embed.add_field(name=utils.translate("modview_top-role", locale),
                          value=member.top_role.mention if member.top_role.name != "@everyone"
                          else member.top_role.name)
    # account information: verified, discord join date, server join date, join method?
    account_embed: discord.Embed = discord.Embed(colour=member.colour,
                                                 title=utils.translate("modview_account", locale))
    account_embed.add_field(name=utils.translate("modview_verified", locale),
                            value="❌" if member.pending else "✔")
    account_embed.add_field(name=utils.translate("modview_discord-join", locale),
                            value=member.created_at.date())
    account_embed.add_field(name=utils.translate("modview_server-join", locale),
                            value=typing.cast(datetime.datetime, member.joined_at).date())
    await interaction.followup.send(embeds=[user_embed, activity_embed, perm_embed,
                                            roles_embed, account_embed], ephemeral=True)


if __name__ == "__main__":
    dev = len(sys.argv) > 1 and sys.argv[1] == "--dev"
    bot.run(token=TOKEN, log_handler=None)
