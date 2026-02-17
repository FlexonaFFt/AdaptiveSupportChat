from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_mode: str
    webhook_base_url: str
    webhook_path: str
    app_host: str
    app_port: int
    flow_file: str


def load_settings() -> Settings:
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    bot_mode = os.getenv("BOT_MODE", "polling").strip().lower()
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "").strip().rstrip("/")
    webhook_path = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip()
    app_host = os.getenv("APP_HOST", "0.0.0.0").strip()
    app_port = int(os.getenv("APP_PORT", "8000").strip())
    flow_file = os.getenv("FLOW_FILE", "docs/flow.md").strip()

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Put it in .env (see .env.example).")
    if bot_mode not in {"polling", "webhook"}:
        raise RuntimeError("BOT_MODE must be either 'polling' or 'webhook'.")
    if bot_mode == "webhook" and not webhook_base_url:
        raise RuntimeError(
            "WEBHOOK_BASE_URL is not set. Put it in .env (see .env.example)."
        )
    if not webhook_path.startswith("/"):
        raise RuntimeError("WEBHOOK_PATH must start with '/'.")

    return Settings(
        bot_token=bot_token,
        bot_mode=bot_mode,
        webhook_base_url=webhook_base_url,
        webhook_path=webhook_path,
        app_host=app_host,
        app_port=app_port,
        flow_file=flow_file,
    )
