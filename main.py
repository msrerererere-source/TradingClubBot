"""Точка входа бота «Титан Трекер».

Запуск:
    pip install -r requirements.txt
    cp .env.example .env
    python main.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import bot_token
from db import init_db
from handlers import router
from handlers.club import watch_demo_expiry


async def _watch_demo(bot: Bot) -> None:
    while True:
        try:
            await watch_demo_expiry(bot)
        except Exception:
            logging.exception("Проверка демо не прошла")
        await asyncio.sleep(60)


async def main() -> None:
    token = bot_token()
    if not token:
        raise SystemExit("ОШИБКА: Не найден BOT_TOKEN в файле .env")

    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    watcher = asyncio.create_task(_watch_demo(bot))
    try:
        await dispatcher.start_polling(bot)
    finally:
        watcher.cancel()


if __name__ == "__main__":
    asyncio.run(main())
