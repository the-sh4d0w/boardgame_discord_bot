"""Discord UI components (modals, views)."""

import typing

import discord

import utils


class ResponseModal(discord.ui.Modal):
    """Response modal."""

    @classmethod
    async def create(cls, interaction: discord.Interaction, message: discord.Message,
                     owner: int) -> "ResponseModal":
        """Create a response modal. Exists because __init__ can't be async.

        Arguments:
            - interaction: the interaction being handled.
            - message: the message to answer to.
        """
        locale: str = interaction.locale.value
        modal: ResponseModal = ResponseModal(utils.translate("respond_title", locale),
                                             message, owner)
        text_input: discord.ui.TextInput = discord.ui.TextInput(
            label=utils.translate("respond_label", locale))
        modal.add_item(text_input)
        return modal

    def __init__(self, title: str, message: discord.Message, owner: int) -> None:
        """Initialise the modal.

        Arguments:
            - title: modal title.
            - message: the message to answer to.
        """
        super().__init__(title=title)
        self.message: discord.Message = message
        self.owner: int = owner

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
