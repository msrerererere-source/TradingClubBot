"""Точка входа бота Trading Club.

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


async def main() -> None:
    token = bot_token()
    if not token:
        raise SystemExit("ОШИБКА: Не найден BOT_TOKEN в файле .env")

    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
