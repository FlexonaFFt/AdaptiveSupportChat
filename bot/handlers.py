from contextlib import suppress
from typing import Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from .flow.engine import RenderItem
from .runtime import get_flow_engine

router = Router()
_last_message_id_by_user: dict[int, int] = {}
_last_hide_on_next_by_user: dict[int, bool] = {}


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    if message.from_user is None:
        return
    engine = get_flow_engine()
    await _render_items(message, message.from_user.id, engine.start(message.from_user.id))


@router.callback_query(F.data.startswith("flow:"))
async def flow_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    engine = get_flow_engine()
    button_id = callback.data.split(":", 1)[1]
    await _render_items(
        callback.message,
        callback.from_user.id,
        engine.on_button(callback.from_user.id, button_id),
    )
    await callback.answer()


async def _render_items(message: Message, user_id: int, items: list[RenderItem]) -> None:
    if _last_hide_on_next_by_user.get(user_id) and user_id in _last_message_id_by_user:
        with suppress(TelegramBadRequest):
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=_last_message_id_by_user[user_id],
            )

    last_message_id: Optional[int] = None
    last_hide_on_next = False
    for item in items:
        sent = await message.answer(item.text, reply_markup=item.keyboard)
        last_message_id = sent.message_id
        last_hide_on_next = item.rules_hide_on_next

    if last_message_id is not None:
        _last_message_id_by_user[user_id] = last_message_id
        _last_hide_on_next_by_user[user_id] = last_hide_on_next
