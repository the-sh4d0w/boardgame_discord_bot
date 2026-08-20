"""Moderation cog."""

import datetime
import typing

import discord
import discord.app_commands
import discord.ext.commands  # pyright: ignore[reportMissingTypeStubs]

from boardgame_discord_bot import utils


class ModerationCog(discord.ext.commands.Cog):
    """Moderation cog."""

    def __init__(self, bot: discord.ext.commands.Bot) -> None:
        """Initialise the moderation cog.

        Arguments:
            bot: the bot.
        """
        self.bot: discord.ext.commands.Bot = bot

    # slash commands
    @discord.app_commands.command(name="ban", description="ban_desc")
    @discord.app_commands.describe(member="ban_member", reason="ban_reason")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions()
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  reason: typing.Optional[str] = None) -> None:
        """Ban a member and give an (optional) reason. Note: this is german-only. Text is NOT loaded
        from the language files.

        Arguments:
            interaction: the interaction being handled.
            member: member which will be banned.
            reason: reason why the member was banned.
        """
        utils.log_command(interaction)
        await member.ban(delete_message_days=0, reason=reason)
        embed: discord.Embed = discord.Embed(
            colour=discord.Colour.green(),
            title=f":white_check_mark: {member.name} wurde gebannt",
            description=reason, timestamp=datetime.datetime.now())
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="unban", description="unban_desc")
    @discord.app_commands.describe(user_id="unban_user-id", reason="unban_reason")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions()
    async def unban(self, interaction: discord.Interaction, user_id: str,
                    reason: typing.Optional[str] = None) -> None:
        """Unban a banned user and give an (optional) reason. Note: this is german-only. Text is NOT
        loaded from the language files.

        Arguments:
            interaction: the interaction being handled.
            user_id: ID of the user which will be unbanned.
            reason: reason why the user was unbanned.
        """
        utils.log_command(interaction)
        # always True as command is guild-only
        if interaction.guild and (user := self.bot.get_user(int(user_id))):
            await interaction.guild.unban(user=user, reason=reason)
            embed: discord.Embed = discord.Embed(
                colour=discord.Colour.green(),
                title=f":white_check_mark: {user.name} wurde entbannt",
                description=reason, timestamp=datetime.datetime.now())
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(":x: Nutzer mit dieser ID existiert nicht.")

    @discord.app_commands.command(name="kick", description="kick_desc")
    @discord.app_commands.describe(member="kick_member", reason="kick_reason")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions()
    async def kick(self, interaction: discord.Interaction, member: discord.Member,
                   reason: typing.Optional[str] = None) -> None:
        """Kick a member and give an (optional) reason. Note: this is german-only. Text is NOT
        loaded from the language files.

        Arguments:
            interaction: the interaction being handled.
            member: member which will be kicked.
            reason: reason why the member was kicked.
        """
        utils.log_command(interaction)
        await member.kick(reason=reason)
        embed: discord.Embed = discord.Embed(
            colour=discord.Colour.green(),
            title=f":white_check_mark: {member.name} wurde gekickt",
            description=reason, timestamp=datetime.datetime.now())
        await interaction.response.send_message(embed=embed)
