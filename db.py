import aiosqlite
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

DB_NAME = "trading_club.db"

async def init_db():
    """Создаёт таблицу, если её нет"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_vip INTEGER DEFAULT 0,
                expires_at TEXT,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_user(user_id: int) -> Optional[aiosqlite.Row]:
    """Получает данные пользователя по user_id"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        return await cursor.fetchone()

async def upsert_user(user_id: int, username: str):
    """Добавляет пользователя или обновляет его данные, если он уже есть"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO users (user_id, username, is_vip, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username, 0, None)
        )
        await db.commit()
    print(f"✅ Пользователь {user_id} ({username}) обработан в БД")

async def check_vip_status(user_id: int) -> Dict[str, bool]:
    """
    Проверяет статус VIP пользователя.
    Возвращает словарь: {"is_vip": bool, "is_expired": bool}
    """
    user = await get_user(user_id)
    
    if not user:
        return {"is_vip": False, "is_expired": True}

    is_vip = bool(user["is_vip"])
    
    if not is_vip:
        return {"is_vip": False, "is_expired": True}

    expires_at_str = user["expires_at"]
    
    if not expires_at_str:
        # Если дата окончания не установлена, считаем, что подписка активна
        return {"is_vip": True, "is_expired": False}

    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        is_expired = datetime.now() > expires_at
        return {"is_vip": True, "is_expired": is_expired}
    except ValueError:
        # Если дата в БД в неверном формате, считаем подписку активной (защита от падения)
        return {"is_vip": True, "is_expired": False}

async def set_vip_subscription(user_id: int, days: int = 30):
    """
    Активирует VIP подписку на указанное количество дней.
    Устанавливает дату истечения срока.
    """
    expires_at = datetime.now() + timedelta(days=days)
    expires_at_str = expires_at.isoformat()

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE users 
            SET is_vip = 1, expires_at = ? 
            WHERE user_id = ?
            """,
            (expires_at_str, user_id)
        )
        await db.commit()
    print(f"✅ VIP подписка активирована для {user_id} на {days} дней. Окончание: {expires_at_str}")

async def cancel_vip_subscription(user_id: int):
    """
    Отменяет VIP подписку.
    Сбрасывает флаг is_vip и дату окончания.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE users 
            SET is_vip = 0, expires_at = NULL 
            WHERE user_id = ?
            """,
            (user_id,)
        )
        await db.commit()
    print(f"❌ VIP подписка отменена для {user_id}")
