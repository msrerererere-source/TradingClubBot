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
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                demo_password TEXT,
                demo_until TEXT,
                demo_notified INTEGER DEFAULT 0,
                access_password TEXT,
                paid_at TEXT,
                access_status TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                inv_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                password TEXT,
                reminded INTEGER DEFAULT 0,
                notified INTEGER DEFAULT 0
            )
        """)
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in await cursor.fetchall()}
        for name, declaration in (
            ("demo_password", "TEXT"),
            ("demo_until", "TEXT"),
            ("demo_notified", "INTEGER DEFAULT 0"),
            ("access_password", "TEXT"),
            ("paid_at", "TEXT"),
            ("access_status", "TEXT"),
        ):
            if name not in columns:
                await db.execute(f"ALTER TABLE users ADD COLUMN {name} {declaration}")
        await db.commit()

async def get_user(user_id: int) -> Optional[aiosqlite.Row]:
    """Получает данные пользователя по user_id"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        return await cursor.fetchone()

async def upsert_user(user_id: int, username: Optional[str]):
    """Добавляет пользователя или обновляет username, не сбрасывая VIP."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username)
            """,
            (user_id, username),
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
            INSERT INTO users (user_id, is_vip, expires_at)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                is_vip = 1,
                expires_at = excluded.expires_at
            """,
            (user_id, expires_at_str),
        )
        await db.commit()
    print(f"✅ VIP подписка активирована для {user_id} на {days} дней. Окончание: {expires_at_str}")

async def set_demo_access(user_id: int, password: str, until: str) -> None:
    """Запоминает пароль демо и момент, когда 24 часа заканчиваются."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, demo_password, demo_until, demo_notified)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                demo_password = excluded.demo_password,
                demo_until = excluded.demo_until,
                demo_notified = 0
            """,
            (user_id, password, until),
        )
        await db.commit()


async def expired_unnotified_demos(now: datetime | None = None) -> list[aiosqlite.Row]:
    """Демо, у которых 24 часа уже вышли и уведомление ещё не отправлено."""
    moment = (now or datetime.now()).isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT user_id, demo_until
            FROM users
            WHERE demo_until IS NOT NULL
              AND demo_until <= ?
              AND COALESCE(demo_notified, 0) = 0
            """,
            (moment,),
        )
        return list(await cursor.fetchall())


async def mark_demo_notified(user_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET demo_notified = 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def create_payment(user_id: int, amount: str = "15000.00", now: datetime | None = None) -> int:
    """Новый счёт. Старые незакрытые счета этого человека больше не напоминают."""
    moment = (now or datetime.now()).isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE payments
            SET reminded = 1
            WHERE user_id = ? AND status = 'pending'
            """,
            (user_id,),
        )
        cursor = await db.execute(
            """
            INSERT INTO payments (user_id, amount, status, created_at, reminded, notified)
            VALUES (?, ?, 'pending', ?, 0, 0)
            """,
            (user_id, amount, moment),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_payment(inv_id: int) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payments WHERE inv_id = ?", (inv_id,))
        return await cursor.fetchone()


async def activate_paid_access(user_id: int, password: str, paid_at: str, inv_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE payments
            SET status = 'paid', paid_at = ?, password = ?, notified = 0
            WHERE inv_id = ?
            """,
            (paid_at, password, inv_id),
        )
        await db.execute(
            """
            INSERT INTO users (user_id, is_vip, expires_at, access_password, paid_at, access_status)
            VALUES (?, 1, NULL, ?, ?, 'активен')
            ON CONFLICT(user_id) DO UPDATE SET
                is_vip = 1,
                expires_at = NULL,
                access_password = excluded.access_password,
                paid_at = excluded.paid_at,
                access_status = 'активен'
            """,
            (user_id, password, paid_at),
        )
        await db.commit()


async def mark_payment_notified(inv_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE payments SET notified = 1 WHERE inv_id = ?", (inv_id,))
        await db.commit()


async def payments_to_remind(now: datetime | None = None, minutes: int = 30) -> list[aiosqlite.Row]:
    moment = now or datetime.now()
    deadline = (moment - timedelta(minutes=minutes)).isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT inv_id, user_id, created_at
            FROM payments AS pending
            WHERE status = 'pending'
              AND COALESCE(reminded, 0) = 0
              AND created_at <= ?
              AND inv_id = (
                  SELECT MAX(latest.inv_id)
                  FROM payments AS latest
                  WHERE latest.user_id = pending.user_id
                    AND latest.status = 'pending'
              )
            """,
            (deadline,),
        )
        return list(await cursor.fetchall())


async def mark_payment_reminded(inv_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE payments SET reminded = 1 WHERE inv_id = ?", (inv_id,))
        await db.commit()


async def cancel_vip_subscription(user_id: int):
    """
    Отменяет VIP подписку.
    Сбрасывает флаг is_vip и дату окончания.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE users 
            SET is_vip = 0, expires_at = NULL, access_status = NULL
            WHERE user_id = ?
            """,
            (user_id,)
        )
        await db.commit()
    print(f"❌ VIP подписка отменена для {user_id}")
