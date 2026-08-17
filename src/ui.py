"""Discord UI components (modals, views)."""

import typing

import discord

import utils


class ResponseModal(discord.ui.Modal):
    """Response modal."""

    def __init__(self, locale: str, owner: int, message: discord.Message) -> None:
        """Initialise the modal.

        Arguments:
            - locale: the locale to translate to.
            - owner: the user id of the owner.
            - message: message to respond to.
        """
        super().__init__(title=utils.translate("respond_title", locale))
        self.owner: int = owner
        self.message: discord.Message = message
        self.add_item(discord.ui.TextInput(label=utils.translate("respond_label", locale),
                                           style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
        """
        locale: str = interaction.locale.value
        text: str = typing.cast(
            discord.ui.TextInput[ResponseModal], self.children[0]).value
        await self.message.reply(text)
        await interaction.response.send_message(utils.translate("respond_submit", locale,
                                                                text=text), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
            - error: the error that occurred.
        """
        locale: str = interaction.locale.value
        await interaction.response.send_message(utils.translate("error", locale, error=error,
                                                                OWNER=self.owner), ephemeral=True)


class MessageModal(discord.ui.Modal):
    """Message modal."""

    def __init__(self, locale: str, owner: int, channel: discord.TextChannel) -> None:
        """Initialise the modal.

        Arguments:
            - locale: the locale to translate to.
            - owner: the user id of the owner.
            - channel: the channel to message.
        """
        super().__init__(title=utils.translate("msg_title", locale))
        self.owner: int = owner
        self.channel: discord.TextChannel = channel
        self.add_item(discord.ui.TextInput(label=utils.translate("msg_label", locale),
                                           style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
        """
        locale: str = interaction.locale.value
        text: str = typing.cast(
            discord.ui.TextInput[MessageModal], self.children[0]).value
        await self.channel.send(text)
        await interaction.response.send_message(utils.translate("msg_submit", locale,
                                                                text=text), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
            - error: the error that occurred.
        """
        locale: str = interaction.locale.value
        await interaction.response.send_message(utils.translate("error", locale, error=error,
                                                                OWNER=self.owner), ephemeral=True)


class QuoteModal(discord.ui.Modal):
    """Quote modal."""

    def __init__(self, locale: str, owner: int, channel: discord.TextChannel) -> None:
        """Initialise the modal.

        Arguments:
            - locale: the locale to translate to.
            - owner: the user id of the owner.
            - channel: the channel to send the quote to.
        """
        super().__init__(title=utils.translate("quote_title", locale))
        self.owner: int = owner
        self.channel: discord.TextChannel = channel
        self.add_item(discord.ui.TextInput(label=utils.translate("quote_text", locale),
                                           style=discord.TextStyle.long))
        self.add_item(discord.ui.TextInput(
            label=utils.translate("quote_source", locale)))

    async def on_submit(self, interaction: discord.Interaction) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
        """
        locale: str = interaction.locale.value
        text: str = typing.cast(
            discord.ui.TextInput[MessageModal], self.children[0]).value
        source: str = typing.cast(
            discord.ui.TextInput[MessageModal], self.children[1]).value
        embed: discord.Embed = discord.Embed(colour=discord.Colour.from_str("#044389"),
                                             title="Zitat", description=f'"{text}"\n~{source}')
        embed.set_author(name=interaction.user.name,
                         icon_url=interaction.user.display_avatar.url)
        await self.channel.send(embed=embed)
        await interaction.response.send_message(utils.translate("quote_submit", locale, text=text,
                                                                source=source), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
            - error: the error that occurred.
        """
        locale: str = interaction.locale.value
        await interaction.response.send_message(utils.translate("error", locale, error=error,
                                                                OWNER=self.owner), ephemeral=True)
