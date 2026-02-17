# AdaptiveSupport — Bot + API

## Новая структура проекта (без `src`)
```text
domain/
  flow/
application/
infrastructure/
interfaces/
  telegram/
  api/
batch/
  airflow/
main.py
```

## Что сейчас покрыто
- Telegram bot runtime (`aiogram`).
- HTTP API и lifecycle (`FastAPI + uvicorn`).
- Тестовый сценарий поддержки:
  - `/start` показывает кнопку `Поддержка`,
  - после нажатия пользователь может отправлять вопросы,
  - бот показывает автосгенерированные частые вопросы кнопками,
  - бот выполняет retrieval по файлам в `knowledge/`,
  - бот отправляет вопрос + найденный контекст в LLM API и возвращает ответ.
- Healthcheck: `GET /health`.

## Безопасность и конфигурация
- Креды бота не хранятся в репозитории.
- Используются переменные окружения (`.env`, есть `.env.example`).
- Основные параметры:
  - `BOT_TOKEN`
  - `BOT_MODE`
  - `LLM_PROVIDER` (`openai` или `gigachat`)
  - `LLM_API_KEY`
  - `LLM_API_URL`
  - `LLM_MODEL`
  - `GIGACHAT_AUTH_KEY` (если `LLM_PROVIDER=gigachat`)
  - `GIGACHAT_AUTH_URL`, `GIGACHAT_API_URL`, `GIGACHAT_SCOPE`
  - `KNOWLEDGE_DIR`
  - `RAG_TOP_K`, `RAG_CHUNK_SIZE_CHARS`, `RAG_CHUNK_OVERLAP_CHARS`
  - `GENERATED_DIR`, `GENERATED_FAQ_FILE`, `START_FAQ_LIMIT`
  - `APP_HOST`, `APP_PORT`
  - `WEBHOOK_BASE_URL`, `WEBHOOK_PATH` (для webhook-режима)

## Что достигнуто
- Получен рабочий MVP интеграции Telegram-бота с LLM API через HTTP.
- Подготовлена база для следующего этапа: подключение RAG и сценариев эскалации.

## Docker
Во время `docker build` автоматически запускается bootstrap:
- читает документы из `knowledge/`,
- генерирует `generated/faq.json` с частыми вопросами.

Сборка образа:
```bash
docker build -t adaptive-support:bot-api .
```

Запуск:
```bash
docker run --env-file .env -p 8000:8000 adaptive-support:bot-api
```

## Docker Compose
Запуск:
```bash
docker compose up -d --build
```

Остановка:
```bash
docker compose down
```

Логи:
```bash
docker compose logs -f bot-api
```

## GigaChat конфигурация
Для переключения на GigaChat:
```env
LLM_PROVIDER=gigachat
GIGACHAT_AUTH_KEY=<authorization_key>
GIGACHAT_AUTH_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth
GIGACHAT_API_URL=https://gigachat.devices.sberbank.ru/api/v1/chat/completions
GIGACHAT_SCOPE=GIGACHAT_API_PERS
LLM_MODEL=GigaChat
```

## RAG
- Положите `.md`/`.txt` документы в `/Users/flexonafft/AdaptiveSupport/knowledge`.
- При сборке образа генерируются FAQ-артефакты из документов.
- При старте приложения индекс чанков строится автоматически.
- В ответ LLM передается только найденный по вопросу контекст из базы знаний.
