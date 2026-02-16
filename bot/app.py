import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, Request

from .config import Settings
from .flow.engine import FlowEngine
from .flow.reader import load_flow_from_markdown
from .handlers import router
from .runtime import set_flow_engine


def create_app(settings: Settings) -> FastAPI:
    flow = load_flow_from_markdown(settings.flow_file)
    set_flow_engine(FlowEngine(flow))

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
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.bot_mode, "flow_id": flow.flow_id}

    @app.post(settings.webhook_path)
    async def telegram_webhook(request: Request) -> dict[str, bool]:
        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": bot})
        await dispatcher.feed_update(bot, update)
        return {"ok": True}

    return app
