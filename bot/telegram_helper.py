"""Helper for building and sending Telegram messages with media support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import Bot, InlineKeyboardMarkup, InputMediaPhoto, Message
from telegram.constants import ChatAction, ParseMode
from telegram.helpers import escape_markdown

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO


class TelegramMessageRepr:
    """Structured Telegram message representation."""

    def __init__(
        self,
        text: str = "",
        parse_mode: str = ParseMode.HTML,
        reply_markup: InlineKeyboardMarkup | None = None,
        silent: bool = False,
        suppress_escaping: bool = False,
    ) -> None:
        if parse_mode == ParseMode.MARKDOWN_V2 and not suppress_escaping:
            self._text = escape_markdown(text, version=2)
        else:
            self._text = text
        self._parse_mode = parse_mode
        self._reply_markup = reply_markup
        self._silent = silent

    def is_silent(self) -> bool:
        return self._silent

    def with_reply_markup(self, reply_markup: InlineKeyboardMarkup | None) -> TelegramMessageRepr:
        # suppress_escaping=True because self._text is already escaped
        return TelegramMessageRepr(self._text, parse_mode=self._parse_mode, reply_markup=reply_markup, silent=self._silent, suppress_escaping=True)

    async def send_as_reply(self, other_message: Message, photo: BytesIO | bytes | None = None) -> None:
        if photo:
            await other_message.get_bot().send_chat_action(other_message.chat_id, action=ChatAction.UPLOAD_PHOTO)
            await other_message.reply_photo(
                photo=photo,
                caption=self._text,
                parse_mode=self._parse_mode,
                disable_notification=self._silent,
                reply_markup=self._reply_markup,
            )
        else:
            await other_message.get_bot().send_chat_action(other_message.chat_id, action=ChatAction.TYPING)
            await other_message.reply_text(
                self._text,
                parse_mode=self._parse_mode,
                disable_notification=self._silent,
                do_quote=True,
                reply_markup=self._reply_markup,
            )

    async def send(self, bot: Bot, chat_id: int, photo: BytesIO | bytes | None = None, message_thread_id: int | None = None) -> Message:
        if photo:
            return await bot.send_photo(
                chat_id,
                photo=photo,
                caption=self._text,
                parse_mode=self._parse_mode,
                reply_markup=self._reply_markup,
                disable_notification=self._silent,
                message_thread_id=message_thread_id,
            )
        return await bot.send_message(
            chat_id,
            text=self._text,
            parse_mode=self._parse_mode,
            reply_markup=self._reply_markup,
            disable_notification=self._silent,
            message_thread_id=message_thread_id,
        )

    async def update_existing(self, other_message: Message, photo: BytesIO | bytes | None = None) -> None:
        if photo:
            # TODO: [fixme] check if media in message!
            await other_message.edit_media(media=InputMediaPhoto(photo))
        if other_message.caption:
            await other_message.edit_caption(
                caption=self._text,
                parse_mode=self._parse_mode,
                reply_markup=self._reply_markup,
            )
        else:
            await other_message.edit_text(
                text=self._text,
                parse_mode=self._parse_mode,
                reply_markup=self._reply_markup,
            )

    def _build_media_group(self, photos: Sequence[BytesIO | bytes]) -> list[InputMediaPhoto]:
        media = [InputMediaPhoto(photos[0], caption=self._text, parse_mode=self._parse_mode)]
        media.extend(InputMediaPhoto(p) for p in photos[1:])
        return media

    async def send_media_group(self, bot: Bot, chat_id: int, photos: Sequence[BytesIO | bytes], message_thread_id: int | None = None) -> list[Message]:
        return list(
            await bot.send_media_group(
                chat_id,
                media=self._build_media_group(photos),
                disable_notification=self._silent,
                message_thread_id=message_thread_id,
            )
        )

    async def send_as_reply_media_group(self, other_message: Message, photos: Sequence[BytesIO | bytes]) -> list[Message]:
        await other_message.get_bot().send_chat_action(other_message.chat_id, action=ChatAction.UPLOAD_PHOTO)
        return list(
            await other_message.get_bot().send_media_group(
                other_message.chat_id,
                media=self._build_media_group(photos),
                disable_notification=self._silent,
                reply_to_message_id=other_message.message_id,
            )
        )

    async def update_existing_media_group(self, messages: list[Message], photos: Sequence[BytesIO | bytes]) -> None:
        for i, (msg, photo) in enumerate(zip(messages, photos)):
            if i == 0:
                await msg.edit_media(
                    media=InputMediaPhoto(photo, caption=self._text, parse_mode=self._parse_mode),
                    reply_markup=self._reply_markup,
                )
            else:
                await msg.edit_media(media=InputMediaPhoto(photo))
