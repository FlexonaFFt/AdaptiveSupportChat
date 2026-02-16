from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from .keyboards import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет! Нажми кнопку, чтобы перейти в поддержку.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery) -> None:
    await callback.message.answer("Раздел поддержки скоро будет расширен.")
    await callback.answer()

