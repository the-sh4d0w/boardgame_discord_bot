"""Event cog."""

import datetime
import io
import typing

import discord
import discord.app_commands
import discord.ext.commands  # pyright: ignore[reportMissingTypeStubs]

from boardgame_discord_bot import CONFIG
from boardgame_discord_bot import utils


class EventCog(discord.ext.commands.Cog):
    """Event cog."""

    def __init__(self, bot: discord.ext.commands.Bot) -> None:
        """Initialise the event cog.

        Arguments:
            bot: the bot.
        """
        self.bot: discord.ext.commands.Bot = bot

    # handling events
    @discord.ext.commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent,
                                        after: discord.ScheduledEvent) -> None:
        """Do stuff on scheduled event update.

        Arguments:
            before: scheduled event before update.
            after: scheduled event after update.
        """
        bot_id: int = typing.cast(discord.ClientUser, self.bot.user).id
        if after.guild and after.creator and after.creator.id == bot_id:
            if before.status == discord.EventStatus.scheduled \
                    and after.status == discord.EventStatus.active:
                CONFIG.game_night_active = True
            elif before.status == discord.EventStatus.active \
                    and after.status == discord.EventStatus.completed:
                CONFIG.game_night_active = False

    # slash commands
    @discord.app_commands.command(name="event", description="event_desc")
    @discord.app_commands.describe(date="event_date")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions()
    async def create_event(self, interaction: discord.Interaction, date: str) -> None:
        """Create a scheduled event.

        Arguments:
            interaction: the interaction being handled.
            date: the date for the event.
        """
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
                await interaction.response.send_message(
                    f"Event für <t:{int(start_time.timestamp())}:D> wurde erstellt.\n{event.url}")
                await interaction.response.send_message(file=discord.File(
                    fp=io.StringIO(utils.create_ics(
                        kw=kw, start=start_time, end=end_time)),  # type: ignore
                    filename="Spieleabend.ics"))
        except ValueError:
            await interaction.response.send_message(utils.translate("event_error", locale),
                                                    ephemeral=True)
