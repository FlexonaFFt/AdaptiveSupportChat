import html
from contextlib import suppress
from typing import Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from mlcore.llm_client import LLMApiError
from mlcore.rag.retriever import RetrievedChunk
from core.runtime import (
    get_knowledge_retriever,
    get_llm_client,
    get_rag_min_relevance_score,
    get_start_questions,
)

router = Router()
_started_users: set[int] = set()
_chat_history_by_user: dict[int, list[dict[str, str]]] = {}
_MAX_HISTORY_ITEMS = 10


def _main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="FAQ")]],
        resize_keyboard=True,
    )


def _dialog_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="У меня новый вопрос")],
        ],
        resize_keyboard=True,
    )


def _operator_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Перевести на оператора")],
            [KeyboardButton(text="У меня новый вопрос")],
        ],
        resize_keyboard=True,
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

    user_id = message.from_user.id
    _started_users.add(user_id)
    _reset_dialog(user_id)

    await message.answer(
        "Здравствуйте! Чем могу помочь?",
        reply_markup=_main_keyboard(),
    )


@router.message(F.text == "FAQ")
async def faq_menu_handler(message: Message) -> None:
    if message.from_user is None:
        return
    if message.from_user.id not in _started_users:
        await message.answer("Начните диалог командой /start.")
        return

    questions = get_start_questions()
    await message.answer(
        "Частые вопросы:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Выберите тему:",
        reply_markup=_faq_keyboard(questions),
    )


@router.message(F.text == "У меня новый вопрос")
async def back_handler(message: Message) -> None:
    if message.from_user is None:
        return
    if message.from_user.id not in _started_users:
        await message.answer("Начните диалог командой /start.")
        return

    _reset_dialog(message.from_user.id)
    await message.answer(
        "Начнем заново. Чем могу помочь?",
        reply_markup=_main_keyboard(),
    )


@router.message(F.text == "Перевести на оператора")
async def transfer_to_operator_handler(message: Message) -> None:
    if message.from_user is None:
        return
    if message.from_user.id not in _started_users:
        await message.answer("Начните диалог командой /start.")
        return

    await message.answer(
        "Передаю ваш запрос оператору. Пожалуйста, ожидайте ответ в чате.",
        reply_markup=_dialog_keyboard(),
    )


@router.callback_query(F.data.startswith("support:faq:"))
async def support_faq_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return

    user_id = callback.from_user.id
    if user_id not in _started_users:
        await callback.answer("Сначала отправьте /start.", show_alert=True)
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
    await callback.message.answer(
        f"Вопрос: {html.escape(questions[idx])}",
        reply_markup=_dialog_keyboard(),
    )
    await _answer_with_rag(
        message=callback.message,
        user_id=user_id,
        question_text=questions[idx],
        with_progress=True,
    )


@router.message(F.text)
async def support_question_handler(message: Message) -> None:
    if message.from_user is None:
        return

    user_id = message.from_user.id
    if user_id not in _started_users:
        await message.answer("Начните диалог командой /start.")
        return

    await _answer_with_rag(
        message=message,
        user_id=user_id,
        question_text=message.text or "",
        with_progress=True,
    )


async def _answer_with_rag(
    message: Message,
    user_id: int,
    question_text: str,
    with_progress: bool = False,
) -> None:
    progress_message: Optional[Message] = None
    if with_progress:
        progress_message = await message.answer("Понял, сейчас проверю.")

    llm_client = get_llm_client()
    retriever = get_knowledge_retriever()
    chunks = retriever.retrieve(question_text)
    context = _build_context(chunks)
    top_score = chunks[0].score if chunks else 0.0
    is_low_relevance = top_score < get_rag_min_relevance_score()
    history = _chat_history_by_user.get(user_id, [])
    try:
        answer = await llm_client.ask(question_text, context=context, chat_history=history)
    except LLMApiError as exc:
        await _cleanup_progress(progress_message)
        safe_error = html.escape(str(exc))
        await message.answer(f"Ошибка LLM API: {safe_error}")
        return
    except Exception:
        await _cleanup_progress(progress_message)
        await message.answer("Не удалось получить ответ от LLM API.")
        return

    await _cleanup_progress(progress_message)
    clean_answer, needs_operator = _sanitize_customer_answer(
        answer,
        chunks_found=len(chunks) > 0,
        low_relevance=is_low_relevance,
    )
    _append_history(user_id, "user", question_text)
    _append_history(user_id, "assistant", clean_answer)
    reply_keyboard = _operator_keyboard() if needs_operator else _dialog_keyboard()
    await message.answer(clean_answer, reply_markup=reply_keyboard)


def _build_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        lines.append(f"[Источник {idx}: {chunk.source}]")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines).strip()


def _sanitize_customer_answer(
    answer: str,
    chunks_found: bool,
    low_relevance: bool,
) -> tuple[str, bool]:
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
    uncertainty_markers = [
        "не могу дать точный ответ",
        "не могу точно ответить",
        "недостаточно данных",
        "нужна помощь оператора",
        "рекомендую передать вопрос оператору",
        "выходит за рамки нашей поддержки",
    ]
    if any(marker in lowered for marker in banned_markers):
        return (
            "Сейчас не могу дать точный ответ по этому вопросу. "
            "Нажмите кнопку «Перевести на оператора», и мы подключим специалиста.",
            True,
        )
    if any(marker in lowered for marker in uncertainty_markers):
        return text, True
    if not chunks_found or low_relevance:
        return (
            "Уточните, пожалуйста, номер заказа, категорию товара или регион доставки. "
            "Если вопрос срочный, нажмите «Перевести на оператора».",
            True,
        )
    return text, False


def _reset_dialog(user_id: int) -> None:
    _chat_history_by_user[user_id] = []


def _append_history(user_id: int, role: str, content: str) -> None:
    history = _chat_history_by_user.setdefault(user_id, [])
    history.append({"role": role, "content": content})
    if len(history) > _MAX_HISTORY_ITEMS:
        _chat_history_by_user[user_id] = history[-_MAX_HISTORY_ITEMS:]


async def _cleanup_progress(progress_message: Optional[Message]) -> None:
    if progress_message is None:
        return
    with suppress(TelegramBadRequest):
        await progress_message.delete()
