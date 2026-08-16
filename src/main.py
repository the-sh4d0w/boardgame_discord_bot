"""Boardgame discord bot."""

import datetime
import logging
import os
import pathlib
import queue
import random
import sys
import tomllib
import typing

import discord
import discord.app_commands
import discord.ext.tasks
import dotenv

import models
import ui
import utils

# TODO: warn command with counter -> needs database
# TODO: role / colour choosing command
# TODO: analysis and statistics command
# TODO: improve config validation
# TODO: ask everyone who voted for the winning day if they're here when the event starts
# TODO: suggest board games command (BGG list?)
# TODO: ask user for name on first join
# TODO: a bit of general cleanup and order
# TODO: improve command descriptions


pyproject_toml: dict[str, typing.Any] = tomllib.loads(
    pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
__VERSION__: str = pyproject_toml["project"]["version"]
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
LOG_PATH: str = "logs"
LOG_FILE: pathlib.Path = pathlib.Path(
    "/", LOG_PATH, f"log_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log")


# bot setup
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot: discord.Client = discord.Client(intents=intents)
tree: discord.app_commands.CommandTree = discord.app_commands.CommandTree(
    client=bot,
    allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=False))

# logging setup
dev: bool = False
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
    text: str = f"Bot running version {__VERSION__ + (" (dev)" if dev else "")}."
    if bot.application:
        dev_text: str = " (dev)\nWarning: Bot may be unstable. Use at own risk."
        await bot.application.edit(description=f"v{__VERSION__ + (dev_text if dev else "")}")
    logging.info(text)


@bot.event
async def on_message(message: discord.Message) -> None:
    """Do stuff on message received.

    Argumemts:
        - message: the actual message.
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


@bot.event
async def on_scheduled_event_update(before: discord.ScheduledEvent, after: discord.ScheduledEvent) \
        -> None:
    """Do stuff on scheduled event update.

    Arguments:
        - before: scheduled event before update.
        - after: scheduled event after update.
    """
    bot_id: int = typing.cast(discord.ClientUser, bot.user).id
    if after.guild and after.creator and after.creator.id == bot_id:
        if before.status == discord.EventStatus.scheduled \
                and after.status == discord.EventStatus.active:
            CONFIG.game_night_active = True
        elif before.status == discord.EventStatus.active \
                and after.status == discord.EventStatus.completed:
            CONFIG.game_night_active = False


@bot.event
async def on_raw_poll_vote_add(payload: discord.RawPollVoteActionEvent) \
        -> None:
    """Do stuff on raw poll vote add.

    Arguments:
        - payload: raw event payload data.
    """
    bot_id: int = typing.cast(discord.ClientUser, bot.user).id
    if payload.guild_id and (guild := bot.get_guild(payload.guild_id)):
        if (user := guild.get_member(payload.user_id)) \
            and (channel := guild.get_channel(payload.channel_id)) \
                and channel.type == discord.ChannelType.text\
                and (message := await channel.fetch_message(payload.message_id)) \
                and message.poll and (answer := [answer for answer in message.poll.answers
                                                 if answer.id == payload.answer_id][0]):
            if answer.poll.message and answer.poll.message.author.id == bot_id \
                    and answer.poll.message.guild:
                day: str = answer.text.split(",")[0]
                for role in answer.poll.message.guild.roles:
                    if role.name == day:
                        await user.add_roles(role, reason="Voted in Boardgame Bot poll.")


@bot.event
async def on_raw_poll_vote_remove(payload: discord.RawPollVoteActionEvent) \
        -> None:
    """Do stuff on raw poll vote remove.

    Arguments:
        - payload: raw event payload data.
    """
    bot_id: int = typing.cast(discord.ClientUser, bot.user).id
    if payload.guild_id and (guild := bot.get_guild(payload.guild_id)):
        if (user := guild.get_member(payload.user_id)) \
            and (channel := guild.get_channel(payload.channel_id)) \
                and channel.type == discord.ChannelType.text\
                and (message := await channel.fetch_message(payload.message_id)) \
                and message.poll and (answer := [answer for answer in message.poll.answers
                                                 if answer.id == payload.answer_id][0]):
            if answer.poll.message and answer.poll.message.author.id == bot_id \
                    and answer.poll.message.guild:
                day: str = answer.text.split(",")[0]
                for role in answer.poll.message.guild.roles:
                    if role.name == day:
                        await user.remove_roles(role, reason="Voted in Boardgame Bot poll.")


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


# slash commands
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
@discord.app_commands.describe(server_id="ascend_server-id", role_id="ascend_role-id",
                               user_id="ascend_user-id")
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
@discord.app_commands.describe(server_id="descend_server-id", role_id="descend_role-id",
                               user_id="descend_user-id")
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
@discord.app_commands.describe(hours="poll_hours", weekend="poll_weekend")
@discord.app_commands.guild_only()
async def create_poll(interaction: discord.Interaction, hours: typing.Optional[int] = None,
                      weekend: typing.Optional[bool] = False) -> None:
    """Create poll. Note: this is german-only. Text is NOT loaded from the language files.

    Arguments:
        - interaction: the interaction being handled.
        - hours: poll duration in hours.
        - weekend: include the weekend as options if True.
    """
    utils.log_command(interaction)
    await interaction.response.defer()
    # create roles and remove users if already member of role
    for role_name, role_colour in zip(CONFIG.day_names, CONFIG.role_colours):
        if interaction.guild \
                and not any(role.name == role_name for role in interaction.guild.roles):
            await interaction.guild.create_role(
                name=role_name, mentionable=True,
                reason="Weekday role for Boardgame Bot (manually through command).",
                colour=discord.Colour.from_str(role_colour.as_hex("long")))
    if interaction.guild:
        for role_name in CONFIG.day_names:
            for role in interaction.guild.roles:
                if role.name == role_name:
                    for member in role.members:
                        if role in member.roles:
                            await member.remove_roles(role, reason="Role reset by Boardgame Bot.")
    # poll setup
    today: datetime.date = datetime.date.today()
    duration: datetime.timedelta
    if hours and 0 < hours <= 768:
        duration = datetime.timedelta(hours=hours)
    else:
        duration = utils.next_sunday_1800(today) - datetime.datetime.now()
    kw: int = (datetime.datetime.now() +
               datetime.timedelta(days=7)).isocalendar().week
    monday: datetime.date = utils.next_monday(today)
    holidays: dict[str, str] = utils.get_holidays(CONFIG.holiday_api_url)
    # create actual poll
    poll: discord.Poll = discord.Poll(question=CONFIG.question_text.format_map({"kw": kw}),
                                      duration=duration, multiple=True)
    # it works...
    for i in range(7 - (not weekend) * 2):
        date: datetime.date = monday + datetime.timedelta(i)
        poll_text: str = f"{CONFIG.day_names[i]}, {date.strftime("%d.%m.%Y")}"
        if date.isoformat() in holidays:
            poll_text += f" ({holidays[date.isoformat()]})"
        poll.add_answer(text=poll_text)
    await interaction.followup.send(poll=poll)


@tree.command(name="event", description="event_desc")
@discord.app_commands.describe(date="event_date")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def create_event(interaction: discord.Interaction, date: str) -> None:
    """Create a scheduled event."""
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    try:
        start_time: datetime.datetime = datetime.datetime.fromisoformat(date).astimezone(
            CONFIG.timezone).replace(hour=16, minute=0)
        end_time: datetime.datetime = start_time.replace(hour=22)
        kw: int = start_time.isocalendar().week
        if interaction.guild:
            event: discord.ScheduledEvent = await interaction.guild.create_scheduled_event(
                name=CONFIG.event_title.format_map({"kw": f"KW {kw}"}),
                location=CONFIG.event_location, description=CONFIG.event_description,
                image=CONFIG.event_cover_image.read_bytes(),
                start_time=start_time, end_time=end_time,
                entity_type=discord.EntityType.external,
                privacy_level=discord.PrivacyLevel.guild_only)
            await interaction.response.send_message(f"Event für <t:{int(start_time.timestamp())}:D>"
                                                    f" wurde erstellt.\n{event.url}")
    except ValueError:
        await interaction.response.send_message(utils.translate("event_error", locale),
                                                ephemeral=True)


@tree.command(name="roles", description="roles_desc")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def create_roles(interaction: discord.Interaction) -> None:
    """Create roles for weekdays.

    Arguments:
        - interaction: the interaction being handled.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    role_amount: int = 0
    for role_name, role_colour in zip(CONFIG.day_names, CONFIG.role_colours):
        if interaction.guild \
                and not any(role.name == role_name for role in interaction.guild.roles):
            await interaction.guild.create_role(
                name=role_name, mentionable=True,
                reason="Weekday role for Boardgame Bot (manually through command).",
                colour=discord.Colour.from_str(role_colour.as_hex("long")))
            role_amount += 1
    await interaction.response.send_message(utils.translate("roles_created", locale,
                                            role_amount=role_amount), ephemeral=True)


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
    channel: discord.TextChannel = typing.cast(discord.TextChannel,
                                               interaction.channel)
    await interaction.response.send_modal(ui.MessageModal(locale, OWNER, channel))


@tree.command(name="quote", description="quote_desc")
@discord.app_commands.guild_only()
async def quote(interaction: discord.Interaction) -> None:
    """Send formatted quote.

    Arguments:
        - interaction: the interaction being handled.
    """
    utils.log_command(interaction)
    locale: str = interaction.locale.value
    channel: discord.TextChannel = typing.cast(discord.TextChannel,
                                               interaction.channel)
    await interaction.response.send_modal(ui.QuoteModal(locale, OWNER, channel))


@tree.command(name="ban", description="ban_desc")
@discord.app_commands.describe(member="ban_member", reason="ban_reason")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def ban(interaction: discord.Interaction, member: discord.Member,
              reason: typing.Optional[str] = None) -> None:
    """Ban a member and give an (optional) reason. Note: this is german-only. Text is NOT loaded
    from the language files.

    Arguments:
        - interaction: the interaction being handled.
        - member: member which will be banned.
        - reason: reason why the member was banned.
    """
    utils.log_command(interaction)
    await member.ban(delete_message_days=0, reason=reason)
    embed: discord.Embed = discord.Embed(colour=discord.Colour.green(),
                                         title=f":white_check_mark: {member.name} wurde gebannt",
                                         description=reason, timestamp=datetime.datetime.now())
    await interaction.response.send_message(embed=embed)


@tree.command(name="unban", description="unban_desc")
@discord.app_commands.describe(user_id="unban_user-id", reason="unban_reason")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def unban(interaction: discord.Interaction, user_id: str,
                reason: typing.Optional[str] = None) -> None:
    """Unban a banned user and give an (optional) reason. Note: this is german-only. Text is NOT
    loaded from the language files.

    Arguments:
        - interaction: the interaction being handled.
        - user_id: ID of the user which will be unbanned.
        - reason: reason why the user was unbanned.
    """
    utils.log_command(interaction)
    # always True as command is guild-only
    if interaction.guild and (user := bot.get_user(int(user_id))):
        await interaction.guild.unban(user=user, reason=reason)
        embed: discord.Embed = discord.Embed(colour=discord.Colour.green(),
                                             title=f":white_check_mark: {user.name} wurde entbannt",
                                             description=reason, timestamp=datetime.datetime.now())
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(":x: Nutzer mit dieser ID existiert nicht.")


@tree.command(name="kick", description="kick_desc")
@discord.app_commands.describe(member="kick_member", reason="kick_reason")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def kick(interaction: discord.Interaction, member: discord.Member,
               reason: typing.Optional[str] = None) -> None:
    """Kick a member and give an (optional) reason. Note: this is german-only. Text is NOT loaded
    from the language files.

    Arguments:
        - interaction: the interaction being handled.
        - member: member which will be kicked.
        - reason: reason why the member was kicked.
    """
    utils.log_command(interaction)
    await member.kick(reason=reason)
    embed: discord.Embed = discord.Embed(colour=discord.Colour.green(),
                                         title=f":white_check_mark: {member.name} wurde gekickt",
                                         description=reason, timestamp=datetime.datetime.now())
    await interaction.response.send_message(embed=embed)


# message commands
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
    await interaction.response.send_modal(ui.ResponseModal(locale, OWNER, message))


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


# user commands
@tree.context_menu(name="modview")
@discord.app_commands.guild_only()
@discord.app_commands.default_permissions()
async def modview(interaction: discord.Interaction, member: discord.Member) -> None:
    """Get modview info.

    Arguments:
        - interaction: the interaction being handled.
        - member: the member that the context menu command was executed on.
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
