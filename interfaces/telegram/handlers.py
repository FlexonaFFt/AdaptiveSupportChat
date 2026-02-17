import html
from typing import Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from infrastructure.llm_api_client import LLMApiError
from infrastructure.rag.retriever import RetrievedChunk
from infrastructure.runtime import (
    get_knowledge_retriever,
    get_llm_client,
    get_start_questions,
)

router = Router()
_support_mode_users: set[int] = set()


def _support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поддержка", callback_data="support:start")]
        ]
    )


def _faq_keyboard(questions: list[str]) -> Optional[InlineKeyboardMarkup]:
    if not questions:
        return None
    rows = [
        [InlineKeyboardButton(text=q[:64], callback_data=f"support:faq:{i}")]
        for i, q in enumerate(questions)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        questions = get_start_questions()
        await callback.message.answer(
            "Режим поддержки включен. Напишите вопрос или выберите частый вопрос ниже.",
            reply_markup=_faq_keyboard(questions),
        )


@router.callback_query(F.data.startswith("support:faq:"))
async def support_faq_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return

    user_id = callback.from_user.id
    if user_id not in _support_mode_users:
        await callback.answer("Сначала нажмите Поддержка через /start.", show_alert=True)
        return

    try:
        idx = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer()
        return

    questions = get_start_questions()
    if idx < 0 or idx >= len(questions):
        await callback.answer()
        return

    await callback.answer()
    await callback.message.answer(f"Вопрос: {html.escape(questions[idx])}")
    await _answer_with_rag(
        message=callback.message,
        question_text=questions[idx],
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

    await _answer_with_rag(message=message, question_text=message.text or "")


async def _answer_with_rag(message: Message, question_text: str) -> None:
    llm_client = get_llm_client()
    retriever = get_knowledge_retriever()
    chunks = retriever.retrieve(question_text)
    context = _build_context(chunks)
    try:
        answer = await llm_client.ask(question_text, context=context)
    except LLMApiError as exc:
        safe_error = html.escape(str(exc))
        await message.answer(f"Ошибка LLM API: {safe_error}")
        return
    except Exception:
        await message.answer("Не удалось получить ответ от LLM API.")
        return

    await message.answer(_sanitize_customer_answer(answer))


def _build_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        lines.append(f"[Источник {idx}: {chunk.source}]")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines).strip()


def _sanitize_customer_answer(answer: str) -> str:
    text = answer.strip()
    lowered = text.lower()
    banned_markers = [
        "в представленном контексте отсутствует",
        "информация в контексте отсутствует",
        "в контексте нет",
        "в базе знаний нет",
        "rag",
        "retrieval",
        "контекст",
    ]
    if any(marker in lowered for marker in banned_markers):
        return (
            "Сейчас не могу дать точный ответ по этому вопросу. "
            "Могу передать ваш запрос оператору, чтобы он уточнил детали."
        )
    return text
