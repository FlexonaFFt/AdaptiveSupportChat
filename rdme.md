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
- Flow reader и валидатор markdown-сценариев.
- Flow engine с пользовательским состоянием in-memory.
- Healthcheck: `GET /health`.

## Reader (v1)
- Реализован `reader`, который:
  - читает `flow.md`,
  - парсит блоки (`message`, `menu`, `mes-menu`),
  - валидирует структуру и переходы,
  - строит runtime-граф для бота.
- Ошибки спецификации возвращаются в структурированном виде (`E_*` коды).

## Flow Engine (v1)
- Хранит текущее состояние пользователя (in-memory).
- Обрабатывает переходы по кнопкам.
- Рендерит сообщения и inline-кнопки по сценарию.
- Поддерживает правило `hide_on_next` (скрытие прошлого сообщения при следующем шаге).

## Безопасность и конфигурация
- Креды бота не хранятся в репозитории.
- Используются переменные окружения (`.env`, есть `.env.example`).
- Основные параметры:
  - `BOT_TOKEN`
  - `BOT_MODE`
  - `FLOW_FILE`
  - `APP_HOST`, `APP_PORT`
  - `WEBHOOK_BASE_URL`, `WEBHOOK_PATH` (для webhook-режима)

## Что достигнуто
- Получен рабочий MVP адаптивного бота, который строит диалог и кнопки из внешнего markdown-сценария.
- Подготовлена база для следующего этапа: горячая перезагрузка flow, персистентное хранилище состояния и расширенные правила маршрутизации.

## Docker
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
