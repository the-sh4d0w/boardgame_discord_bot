"""Discord UI components (modals, views)."""

import typing

import discord

import utils


class TextModal(discord.ui.Modal):
    """Text modal."""

    def __init__(self, title: str, label: str, owner: int) -> None:
        """Initialise the modal.

        Arguments:
            - title: modal title.
            - label: text input label.
            - owner: the user id of the owner.
        """
        super().__init__(title=title)
        self.owner: int = owner
        self.add_item(discord.ui.TextInput(label=label))

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


class ResponseModal(TextModal):
    """Response modal."""

    def __init__(self, title: str, label: str, owner: int, message: discord.Message) -> None:
        """Initialise the modal.

        Arguments:
            - title: modal title.
            - label: text input label.
            - owner: the user id of the owner.
            - message: message to respond to.
        """
        super().__init__(title, label, owner)
        self.message: discord.Message = message

    async def on_submit(self, interaction: discord.Interaction) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
        """
        locale: str = interaction.locale.value
        text: str = typing.cast(discord.ui.TextInput, self.children[0]).value
        await self.message.reply(text)
        await interaction.response.send_message(utils.translate("respond_submit", locale,
                                                                text=text), ephemeral=True)


class MessageModal(TextModal):
    """Message modal."""

    def __init__(self, title: str, label: str, owner: int, channel: discord.TextChannel) -> None:
        """Initialise the modal.

        Arguments:
            - title: modal title.
            - label: text input label.
            - owner: the user id of the owner.
            - channel: the channel to message.
        """
        super().__init__(title, label, owner)
        self.channel: discord.TextChannel = channel

    async def on_submit(self, interaction: discord.Interaction) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
        """
        locale: str = interaction.locale.value
        text: str = typing.cast(discord.ui.TextInput, self.children[0]).value
        await self.channel.send(text)
        await interaction.response.send_message(utils.translate("msg_submit", locale,
                                                                text=text), ephemeral=True)


class QuoteModal(discord.ui.Modal):
    """Quote modal."""

    def __init__(self, title: str, text_label: str, source_label: str, owner: int,
                 channel: discord.TextChannel) -> None:
        """Initialise the modal.

        Arguments:
            - title: modal title.
            - text_label: text text input label.
            - source_label: source text text input label.
            - owner: the user id of the owner.
            - channel: the channel to send the quote to.
        """
        super().__init__(title=title)
        self.owner: int = owner
        self.channel: discord.TextChannel = channel
        self.add_item(discord.ui.TextInput(label=text_label))
        self.add_item(discord.ui.TextInput(label=source_label))

    async def on_submit(self, interaction: discord.Interaction) \
            -> None:  # pylint:disable=arguments-differ
        """Do stuff on submit.

        Arguments:
            - interaction: the interaction being handled.
        """
        locale: str = interaction.locale.value
        text: str = typing.cast(discord.ui.TextInput, self.children[0]).value
        source: str = typing.cast(discord.ui.TextInput, self.children[1]).value
        embed: discord.Embed = discord.Embed(colour=discord.Colour.from_str("#044389"),
                                             title="Zitat", description=f'"{text}"\n~{source}')
        embed.set_author(name=interaction.user.name,
                         icon_url=interaction.user.display_avatar.url)
        await self.channel.send(embed=embed)
        await interaction.response.send_message(utils.translate("quote_submit", locale, text=text,
                                                                source=source), ephemeral=True)
