# Flow Markdown Spec v1

## 1. Назначение
`flow.md` описывает сценарий бота поддержки в виде блоков.
Reader парсит файл в граф переходов и рендерит UI.

## 2. Общая структура файла
1. Первая строка: заголовок сценария  
`# Support Flow: <flow_id>`
2. Далее идут блоки, разделенные строкой  
`---`
3. Каждый блок начинается с заголовка  
`## block: <block_id>`

## 3. Блоки

### 3.1 Обязательные поля блока
- `type`: `message | menu | mes-menu`
- `rules`: объект правил

### 3.2 Тип `message`
Показывает сообщение без кнопок меню.
Поля:
- `text` (обяз.)
- `next` (обяз., кроме terminal-сценария)

### 3.3 Тип `menu`
Показывает сообщение и набор кнопок.
Поля:
- `menu_id` (обяз.)
- `text` (обяз.)
- `buttons` (обяз., список >= 1)

Каждая кнопка:
- `id` (обяз., уникален в блоке)
- `text` (обяз.)
- `next` (обяз., целевой `block_id`)

### 3.4 Тип `mes-menu`
Показывает сообщение и одну кнопку под сообщением.
Поля:
- `text` (обяз.)
- `button` (обяз., объект)

`button`:
- `id` (обяз.)
- `text` (обяз.)
- `next` (обяз.)

## 4. Правила `rules`

### 4.1 Общие поля
- `hide_on_next`: `true|false`  
Если `true`, сообщение удаляется/скрывается после следующей активации пользователем.

### 4.2 Для `menu`
- `replace_menu`: `true|false`  
Если `true`, предыдущее меню заменяется новым.

## 5. Валидация

### 5.1 Глобальная
1. `flow_id` в заголовке обязателен.
2. Должен существовать блок `start` (точка входа).
3. Все `block_id` уникальны.
4. Все `next` ссылаются на существующий блок.
5. Хотя бы один terminal-блок (блок без `next` и без кнопок с `next` наружу, либо `end`).

### 5.2 По типам
- `message`: запрещены `menu_id`, `buttons`, `button`.
- `menu`: обязателен `buttons`, запрещен `button`.
- `mes-menu`: обязателен `button`, запрещены `buttons`, `menu_id`.

### 5.3 Ошибки
Reader должен возвращать:
- код ошибки (`E_*`),
- `block_id`,
- строку/позицию (если доступно),
- понятное сообщение.

Примеры кодов:
- `E_FLOW_HEADER`
- `E_DUPLICATE_BLOCK_ID`
- `E_UNKNOWN_TYPE`
- `E_MISSING_FIELD`
- `E_INVALID_NEXT`
- `E_RULES_INVALID`

## 6. Рантайм-контракт
1. На `/start` бот загружает `start`.
2. По кнопке движок переходит в `next`.
3. UI строится строго из текущего блока.
4. Правила `rules` применяются перед рендером нового блока.

## 7. Минимальный пример
```md
# Support Flow: client_v1

## block: start
type: message
text: "Добро пожаловать в поддержку."
rules:
  hide_on_next: true
next: main_menu

---

## block: main_menu
type: menu
menu_id: main
text: "Выберите тему:"
rules:
  hide_on_next: false
  replace_menu: true
buttons:
  - id: billing
    text: "Оплата"
    next: billing
  - id: operator
    text: "Оператор"
    next: end

---

## block: billing
type: mes-menu
text: "Опишите проблему с оплатой."
rules:
  hide_on_next: true
button:
  id: back
  text: "Назад"
  next: main_menu

---

## block: end
type: message
text: "Запрос передан оператору."
rules:
  hide_on_next: false
```
