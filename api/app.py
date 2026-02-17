import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, Request

from core.bootstrap_artifacts import load_bootstrap_questions
from mlcore.llm_client import LLMApiClient
from mlcore.rag.retriever import KnowledgeRetriever
from core.runtime import (
    set_knowledge_retriever,
    set_llm_client,
    set_rag_min_relevance_score,
    set_start_questions,
)
from core.settings import Settings
from supportbot.telegram.handlers import router


def create_app(settings: Settings) -> FastAPI:
    llm_client = LLMApiClient(
        provider=settings.llm_provider,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        openai_api_url=settings.llm_api_url,
        openai_api_key=settings.llm_api_key,
        gigachat_api_url=settings.gigachat_api_url,
        gigachat_auth_url=settings.gigachat_auth_url,
        gigachat_auth_key=settings.gigachat_auth_key,
        gigachat_scope=settings.gigachat_scope,
        gigachat_verify_ssl=settings.gigachat_verify_ssl,
    )
    set_llm_client(llm_client)
    retriever = KnowledgeRetriever.from_directory(
        knowledge_dir=settings.knowledge_dir,
        chunk_size_chars=settings.rag_chunk_size_chars,
        chunk_overlap_chars=settings.rag_chunk_overlap_chars,
        top_k=settings.rag_top_k,
    )
    set_knowledge_retriever(retriever)
    set_rag_min_relevance_score(settings.rag_min_relevance_score)
    set_start_questions(
        load_bootstrap_questions(
            path=settings.generated_faq_file,
            limit=settings.start_faq_limit,
        )
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    webhook_url = f"{settings.webhook_base_url}{settings.webhook_path}"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        polling_task: Optional[asyncio.Task] = None
        if settings.bot_mode == "webhook":
            await bot.set_webhook(webhook_url)
        else:
            polling_task = asyncio.create_task(
                dispatcher.start_polling(
                    bot,
                    allowed_updates=dispatcher.resolve_used_update_types(),
                    handle_signals=False,
                    close_bot_session=False,
                )
            )
        try:
            yield
        finally:
            if settings.bot_mode == "webhook":
                await bot.delete_webhook(drop_pending_updates=False)
            else:
                await dispatcher.stop_polling()
                if polling_task:
                    polling_task.cancel()
                    with suppress(asyncio.CancelledError, asyncio.TimeoutError):
                        await asyncio.wait_for(polling_task, timeout=3)
            await bot.session.close()

    app = FastAPI(title="Adaptive Support Bot API", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str | int]:
        return {
            "status": "ok",
            "mode": settings.bot_mode,
            "llm_model": llm_client.model,
            "rag_chunks": retriever.chunk_count,
        }

    @app.post(settings.webhook_path)
    async def telegram_webhook(request: Request) -> dict[str, bool]:
        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": bot})
        await dispatcher.feed_update(bot, update)
        return {"ok": True}

    return app
