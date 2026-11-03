# Бот-публикатор Telegram-канала Operation Zero

Работает через GitHub Actions (`.github/workflows/tg-channel.yml`), без своего сервера.

- Пост = JSON-файл в `tgbot/queue/` (формат — в начале `post.py`). Поле `at` — время по Екатеринбургу; без него пост уходит сразу.
- Публикация: при каждом пуше в `tgbot/queue/` и каждые 30 минут (для отложенных). Опубликованные записываются в `tgbot/sent.json`, повторно не уходят.
- `tgbot/stats.json` — число подписчиков канала по дням.

## Настройка (один раз, делает владелец)
1. @BotFather → /newbot → получить токен.
2. Добавить бота администратором канала с правом публиковать и закреплять сообщения.
3. GitHub → репозиторий → Settings → Secrets and variables → Actions:
   - Secret `TG_BOT_TOKEN` = токен бота;
   - Variable `TG_CHANNEL` = `@имя_канала`.
4. Actions → «Telegram-канал — публикация постов» → Run workflow.
