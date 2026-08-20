"""Democracy cog."""

import datetime
import typing

import discord
import discord.app_commands
import discord.ext.commands  # pyright: ignore[reportMissingTypeStubs]

from boardgame_discord_bot import CONFIG
from boardgame_discord_bot import utils


class DemocracyCog(discord.ext.commands.Cog):
    """Democracy cog."""

    def __init__(self, bot: discord.ext.commands.Bot) -> None:
        """Initialise the democracy cog.

        Arguments:
            bot: the bot.
        """
        self.bot: discord.ext.commands.Bot = bot

    # handling events
    @discord.ext.commands.Cog.listener()
    async def on_raw_poll_vote_add(self, payload: discord.RawPollVoteActionEvent) \
            -> None:
        """Do stuff on raw poll vote add.

        Arguments:
            payload: raw event payload data.
        """
        bot_id: int = typing.cast(discord.ClientUser, self.bot.user).id
        if payload.guild_id and (guild := self.bot.get_guild(payload.guild_id)):
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

    @discord.ext.commands.Cog.listener()
    async def on_raw_poll_vote_remove(self, payload: discord.RawPollVoteActionEvent) \
            -> None:
        """Do stuff on raw poll vote remove.

        Arguments:
            payload: raw event payload data.
        """
        bot_id: int = typing.cast(discord.ClientUser, self.bot.user).id
        if payload.guild_id and (guild := self.bot.get_guild(payload.guild_id)):
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

    # slash commands
    @discord.app_commands.command(name="poll", description="poll_desc")
    @discord.app_commands.describe(hours="poll_hours", weekend="poll_weekend")
    @discord.app_commands.guild_only()
    async def create_poll(self, interaction: discord.Interaction,
                          hours: typing.Optional[int] = None,
                          weekend: typing.Optional[bool] = False) -> None:
        """Create poll. Note: this is german-only. Text is NOT loaded from the language files.

        Arguments:
            interaction: the interaction being handled.
            hours: poll duration in hours.
            weekend: include the weekend as options if True.
        """
        utils.log_command(interaction)
        await interaction.response.defer()
        # create roles and remove users if already member of role
        if interaction.guild:
            for role_name, role_colour in zip(CONFIG.day_names, CONFIG.role_colours):
                if not any(role.name == role_name for role in interaction.guild.roles):
                    await interaction.guild.create_role(
                        name=role_name, mentionable=True,
                        reason="Weekday role for Boardgame Bot (manually through command).",
                        colour=discord.Colour.from_str(role_colour.as_hex("long")))
            for role_name in CONFIG.day_names:
                for role in interaction.guild.roles:
                    if role.name == role_name:
                        for member in role.members:
                            if role in member.roles:
                                await member.remove_roles(
                                    role, reason="Role reset by Boardgame Bot.")
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
        holidays: dict[str, str] = utils.get_holidays(
            str(CONFIG.holiday_api_url))
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

    @discord.app_commands.command(name="roles", description="roles_desc")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions()
    async def create_roles(self, interaction: discord.Interaction) -> None:
        """Create roles for weekdays.

        Arguments:
            interaction: the interaction being handled.
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
