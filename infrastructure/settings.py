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
    llm_provider: str
    llm_api_key: str
    llm_api_url: str
    llm_model: str
    llm_timeout_seconds: int
    gigachat_auth_key: str
    gigachat_auth_url: str
    gigachat_api_url: str
    gigachat_scope: str
    gigachat_verify_ssl: bool
    knowledge_dir: str
    rag_top_k: int
    rag_chunk_size_chars: int
    rag_chunk_overlap_chars: int


def load_settings() -> Settings:
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    bot_mode = os.getenv("BOT_MODE", "polling").strip().lower()
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "").strip().rstrip("/")
    webhook_path = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip()
    app_host = os.getenv("APP_HOST", "0.0.0.0").strip()
    app_port = int(os.getenv("APP_PORT", "8000").strip())
    llm_provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    llm_api_key = os.getenv("LLM_API_KEY", "").strip()
    llm_api_url = os.getenv(
        "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
    ).strip()
    llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
    llm_timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "30").strip())
    gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY", "").strip()
    gigachat_auth_url = os.getenv(
        "GIGACHAT_AUTH_URL",
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
    ).strip()
    gigachat_api_url = os.getenv(
        "GIGACHAT_API_URL", "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    ).strip()
    gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()
    gigachat_verify_ssl = os.getenv("GIGACHAT_VERIFY_SSL", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    knowledge_dir = os.getenv("KNOWLEDGE_DIR", "knowledge").strip()
    rag_top_k = int(os.getenv("RAG_TOP_K", "4").strip())
    rag_chunk_size_chars = int(os.getenv("RAG_CHUNK_SIZE_CHARS", "900").strip())
    rag_chunk_overlap_chars = int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "120").strip())

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Put it in .env (see .env.example).")
    if bot_mode not in {"polling", "webhook"}:
        raise RuntimeError("BOT_MODE must be either 'polling' or 'webhook'.")
    if llm_provider not in {"openai", "gigachat"}:
        raise RuntimeError("LLM_PROVIDER must be either 'openai' or 'gigachat'.")
    if rag_top_k < 1:
        raise RuntimeError("RAG_TOP_K must be >= 1.")
    if rag_chunk_size_chars < 200:
        raise RuntimeError("RAG_CHUNK_SIZE_CHARS must be >= 200.")
    if rag_chunk_overlap_chars < 0:
        raise RuntimeError("RAG_CHUNK_OVERLAP_CHARS must be >= 0.")
    if rag_chunk_overlap_chars >= rag_chunk_size_chars:
        raise RuntimeError("RAG_CHUNK_OVERLAP_CHARS must be less than RAG_CHUNK_SIZE_CHARS.")
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
        llm_provider=llm_provider,
        llm_api_key=llm_api_key,
        llm_api_url=llm_api_url,
        llm_model=llm_model,
        llm_timeout_seconds=llm_timeout_seconds,
        gigachat_auth_key=gigachat_auth_key,
        gigachat_auth_url=gigachat_auth_url,
        gigachat_api_url=gigachat_api_url,
        gigachat_scope=gigachat_scope,
        gigachat_verify_ssl=gigachat_verify_ssl,
        knowledge_dir=knowledge_dir,
        rag_top_k=rag_top_k,
        rag_chunk_size_chars=rag_chunk_size_chars,
        rag_chunk_overlap_chars=rag_chunk_overlap_chars,
    )
