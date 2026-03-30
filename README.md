# Telegram Support Bot (MVP)

MVP бота техподдержки для стартапа (fintech + AI + crypto) на `Python + aiogram 3 + PostgreSQL + Redis + Docker`.

## Возможности

- Обязательный выбор категории при `/start`
- Один активный тикет на пользователя
- Создание тикета и отправка в закрытую группу поддержки
- Действия сотрудников через inline-кнопки:
  - взять в работу
  - ответить пользователю
  - внутренний комментарий
  - назначить
  - закрыть
  - эскалация разработчику
- После ответа сотрудника тикет переходит в `WAITING_USER`
- В сообщении пользователю после ответа есть кнопки:
  - "Проблема решена — закрыть тикет"
  - "Проблема не решена"
- Авто-закрытие тикетов в статусе `WAITING_USER`, если пользователь не ответил 48 часов
- Команды группы: `/active`, `/in_progress`, `/closed`, `/my`
- Все сообщения и статусы сохраняются в PostgreSQL
- Whitelist сотрудников через таблицу `staff_users`

## Структура проекта

```text
.
├── app
│   ├── bot
│   │   ├── formatters.py
│   │   └── keyboards.py
│   ├── db
│   │   ├── repositories
│   │   │   ├── messages.py
│   │   │   ├── staff_users.py
│   │   │   └── tickets.py
│   │   ├── base.py
│   │   ├── enums.py
│   │   ├── models.py
│   │   └── session.py
│   ├── handlers
│   │   ├── staff.py
│   │   └── user.py
│   ├── services
│   │   ├── staff_service.py
│   │   └── ticket_service.py
│   ├── states
│   │   ├── staff.py
│   │   └── user.py
│   ├── utils
│   │   └── content.py
│   ├── config.py
│   ├── constants.py
│   ├── logging.py
│   └── main.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Быстрый старт

1. Создайте `.env`:
   - `cp .env.example .env`
   - заполните `BOT_TOKEN`, `SUPPORT_GROUP_ID`, `STAFF_SEED_IDS`
   - при необходимости задайте `TICKET_ID_OFFSET` (например `100000`)
   - при необходимости задайте `STAFF_NAME_MAP` для красивых имен в меню назначения
   - таймаут авто-закрытия настраивается через `WAITING_USER_TIMEOUT_HOURS` (по умолчанию `48`)
2. Поднимите сервисы:
   - `docker compose up --build`
3. Добавьте бота в закрытую группу поддержки и выдайте права на отправку сообщений.

## Примечания по данным

- В `tickets` добавлено поле `closed_by`, чтобы команда `/closed` показывала, кто закрыл тикет.
- Ограничение "один активный тикет на пользователя" обеспечено частичным уникальным индексом:
  - `UNIQUE (user_id) WHERE status <> 'CLOSED'`
- Пользовательский номер тикета в сообщениях = `id + TICKET_ID_OFFSET` (в БД хранится реальный `id`).
