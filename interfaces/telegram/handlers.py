import html

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from infrastructure.llm_api_client import LLMApiError
from infrastructure.rag.retriever import RetrievedChunk
from infrastructure.runtime import get_knowledge_retriever, get_llm_client

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
    retriever = get_knowledge_retriever()
    chunks = retriever.retrieve(message.text or "")
    context = _build_context(chunks)

    try:
        answer = await llm_client.ask(message.text or "", context=context)
    except LLMApiError as exc:
        safe_error = html.escape(str(exc))
        await message.answer(f"Ошибка LLM API: {safe_error}")
        return
    except Exception:
        await message.answer("Не удалось получить ответ от LLM API.")
        return

    await message.answer(answer)


def _build_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        lines.append(f"[Источник {idx}: {chunk.source}]")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines).strip()
