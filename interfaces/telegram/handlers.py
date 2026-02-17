import html

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from infrastructure.llm_api_client import LLMApiError
from infrastructure.runtime import get_llm_client

router = Router()
_support_mode_users: set[int] = set()


def _support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поддержка", callback_data="support:start")]
        ]
    )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    if message.from_user is None:
        return
    _support_mode_users.discard(message.from_user.id)
    await message.answer(
        "Нажмите кнопку ниже, чтобы перейти в режим поддержки.",
        reply_markup=_support_keyboard(),
    )


@router.callback_query(F.data == "support:start")
async def support_callback(callback: CallbackQuery) -> None:
    _support_mode_users.add(callback.from_user.id)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            "Режим поддержки включен. Напишите вопрос, и я отправлю его в LLM."
        )


@router.message(F.text)
async def support_question_handler(message: Message) -> None:
    if message.from_user is None:
        return

    user_id = message.from_user.id
    if user_id not in _support_mode_users:
        await message.answer(
            "Сначала нажмите кнопку Поддержка через /start.",
            reply_markup=_support_keyboard(),
        )
        return

    llm_client = get_llm_client()
    try:
        answer = await llm_client.ask(message.text or "")
    except LLMApiError as exc:
        safe_error = html.escape(str(exc))
        await message.answer(f"Ошибка LLM API: {safe_error}")
        return
    except Exception:
        await message.answer("Не удалось получить ответ от LLM API.")
        return

    await message.answer(answer)
