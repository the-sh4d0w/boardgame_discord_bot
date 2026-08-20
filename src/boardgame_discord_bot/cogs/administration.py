"""Administration cog."""


import discord
import discord.app_commands
import discord.ext.commands  # pyright: ignore[reportMissingTypeStubs]

from boardgame_discord_bot import OWNER
from boardgame_discord_bot import utils


class AdministrationCog(discord.ext.commands.Cog):
    """Administration cog."""

    def __init__(self, bot: discord.ext.commands.Bot) -> None:
        """Initialise the administration cog.

        Arguments:
            bot: the bot.
        """
        self.bot: discord.ext.commands.Bot = bot

    # slash commands
    @discord.app_commands.command(name="sync", description="sync_desc")
    @discord.app_commands.dm_only()
    @utils.check_if_owner(OWNER)
    async def sync(self, interaction: discord.Interaction) -> None:
        """Sync commands.

        Arguments:
            interaction: the interaction being handled.
        """
        utils.log_command(interaction)
        locale: str = interaction.locale.value
        await interaction.response.defer(ephemeral=True)
        synced: list[discord.app_commands.AppCommand] = await self.bot.tree.sync()
        commands: str = ", ".join(map(lambda cmd: utils.translate(cmd.name, locale),
                                      synced))
        text: str = utils.translate("sync_text", locale, amount=len(synced),
                                    synced=commands)
        await interaction.followup.send(content=text, ephemeral=True)

    @discord.app_commands.command(name="ascend", description="ascend_desc")
    @discord.app_commands.describe(server_id="ascend_server-id", role_id="ascend_role-id",
                                   user_id="ascend_user-id")
    @discord.app_commands.dm_only()
    @utils.check_if_owner(OWNER)
    async def ascend(self, interaction: discord.Interaction, server_id: str, role_id: str,
                     user_id: str = str(OWNER)) -> None:
        """Ascend.

        Arguments:
            interaction: the interaction being handled.
            server_id: the ID of the server.
            role_id: the ID of the role.
            user_id: the ID of the user.
        """
        utils.log_command(interaction)
        locale: str = interaction.locale.value
        if (guild := self.bot.get_guild(int(server_id))) \
            and (role := guild.get_role(int(role_id))) \
                and (member := guild.get_member(int(user_id))):
            await member.add_roles(role)
            await interaction.response.send_message(utils.translate(
                "ascend_success", locale, role=role.mention, member=member.mention), ephemeral=True)
        else:
            await interaction.response.send_message(utils.translate("ascend_fail", locale),
                                                    ephemeral=True)

    @discord.app_commands.command(name="descend", description="descend_desc")
    @discord.app_commands.describe(server_id="descend_server-id", role_id="descend_role-id",
                                   user_id="descend_user-id")
    @discord.app_commands.dm_only()
    @utils.check_if_owner(OWNER)
    async def descend(self, interaction: discord.Interaction, server_id: str, role_id: str,
                      user_id: str = str(OWNER)) -> None:
        """Descend.

        Arguments:
            interaction: the interaction being handled.
            server_id: the ID of the server.
            role_id: the ID of the role.
            user_id: the ID of the user.
        """
        utils.log_command(interaction)
        locale: str = interaction.locale.value
        if (guild := self.bot.get_guild(int(server_id))) \
            and (role := guild.get_role(int(role_id))) \
                and (member := guild.get_member(int(user_id))):
            await member.remove_roles(role)
            await interaction.response.send_message(utils.translate(
                "descend_success", locale, role=role.mention, member=member.mention),
                ephemeral=True)
        else:
            await interaction.response.send_message(utils.translate("descend_fail", locale),
                                                    ephemeral=True)
