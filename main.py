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
from handlers.club import watch_demo_expiry, watch_unpaid
from services.robokassa_server import start_result_server


async def _watch_demo(bot: Bot) -> None:
    while True:
        try:
            await watch_demo_expiry(bot)
        except Exception:
            logging.exception("Проверка демо не прошла")
        await asyncio.sleep(60)


async def _watch_unpaid(bot: Bot) -> None:
    while True:
        try:
            await watch_unpaid(bot)
        except Exception:
            logging.exception("Проверка неоплаченных счетов не прошла")
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
    result_server = await start_result_server(bot)
    watcher = asyncio.create_task(_watch_demo(bot))
    unpaid = asyncio.create_task(_watch_unpaid(bot))
    try:
        await dispatcher.start_polling(bot)
    finally:
        watcher.cancel()
        unpaid.cancel()
        if result_server is not None:
            await result_server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
