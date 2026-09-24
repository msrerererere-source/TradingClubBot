import os
import tempfile
import unittest
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import db
from services.titan_access import build_titan_link, verify_titan_access


class TitanLinkTests(unittest.TestCase):
    def setUp(self):
        self._env = {
            key: os.environ.get(key)
            for key in ("TITAN_TRACKER_URL", "TITAN_ACCESS_SECRET", "TITAN_ACCESS_TTL_HOURS")
        }

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_url_returns_nothing(self):
        os.environ["TITAN_TRACKER_URL"] = ""
        os.environ["TITAN_ACCESS_SECRET"] = "secret"
        self.assertIsNone(build_titan_link(10))

    def test_without_secret_link_stays_shared(self):
        os.environ["TITAN_TRACKER_URL"] = "https://titan.example/app"
        os.environ["TITAN_ACCESS_SECRET"] = ""
        self.assertEqual(build_titan_link(10), ("https://titan.example/app", False))

    def test_signed_link_roundtrip(self):
        os.environ["TITAN_TRACKER_URL"] = "https://titan.example/app?ref=club"
        os.environ["TITAN_ACCESS_SECRET"] = "club-secret"
        os.environ["TITAN_ACCESS_TTL_HOURS"] = "12"
        now = 1_700_000_000
        link, personal = build_titan_link(42, now=now)
        self.assertTrue(personal)
        query = parse_qs(urlsplit(link).query)
        self.assertEqual(query["uid"], ["42"])
        self.assertEqual(query["ref"], ["club"])
        exp = int(query["exp"][0])
        self.assertEqual(exp, now + 12 * 3600)
        self.assertTrue(verify_titan_access(42, exp, query["sig"][0], now=now + 10))
        self.assertFalse(verify_titan_access(42, exp, query["sig"][0], now=exp + 1))
        self.assertFalse(verify_titan_access(7, exp, query["sig"][0], now=now + 10))
        self.assertFalse(verify_titan_access(42, exp, "0" * 64, now=now + 10))


class VipStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._previous = db.DB_NAME
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self._path = path
        db.DB_NAME = path
        await db.init_db()

    async def asyncTearDown(self):
        db.DB_NAME = self._previous
        os.remove(self._path)

    async def test_start_does_not_wipe_vip(self):
        await db.upsert_user(5, "member")
        await db.set_vip_subscription(5, 30)
        await db.upsert_user(5, "member_renamed")
        status = await db.check_vip_status(5)
        self.assertTrue(status["is_vip"])
        self.assertFalse(status["is_expired"])
        user = await db.get_user(5)
        self.assertEqual(user["username"], "member_renamed")

    async def test_expired_vip_is_not_active(self):
        await db.set_vip_subscription(8, 30)
        past = (datetime.now() - timedelta(days=1)).isoformat()
        import aiosqlite

        async with aiosqlite.connect(db.DB_NAME) as connection:
            await connection.execute(
                "UPDATE users SET expires_at = ? WHERE user_id = ?",
                (past, 8),
            )
            await connection.commit()
        from subscription_check import check_subscription

        self.assertFalse(await check_subscription(8))

    async def test_cancel_closes_access(self):
        await db.set_vip_subscription(9, 10)
        await db.cancel_vip_subscription(9)
        from subscription_check import check_subscription

        self.assertFalse(await check_subscription(9))


class FakeUser:
    def __init__(self, user_id: int, username: str):
        self.id = user_id
        self.username = username


class FakeMessage:
    def __init__(self, user: FakeUser):
        self.from_user = user
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))


class TitanFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._previous = db.DB_NAME
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self._path = path
        db.DB_NAME = path
        await db.init_db()
        self._env = {
            key: os.environ.get(key)
            for key in ("TITAN_TRACKER_URL", "TITAN_ACCESS_SECRET", "TITAN_ACCESS_TTL_HOURS")
        }
        os.environ["TITAN_TRACKER_URL"] = "https://titan.example/app"
        os.environ["TITAN_ACCESS_SECRET"] = "club-secret"
        os.environ["TITAN_ACCESS_TTL_HOURS"] = "12"

    async def asyncTearDown(self):
        db.DB_NAME = self._previous
        os.remove(self._path)
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    async def test_guest_does_not_receive_link(self):
        from handlers.club import present_titan

        message = FakeMessage(FakeUser(15, "guest"))
        await present_titan(message)
        text = message.answers[0][0]
        self.assertIn("активным VIP", text)
        self.assertNotIn("https://titan.example", text)

    async def test_vip_receives_signed_link(self):
        from handlers.club import present_titan

        await db.set_vip_subscription(16, 30)
        message = FakeMessage(FakeUser(16, "member"))
        await present_titan(message)
        self.assertIn("Титан Трекер открыт", message.answers[0][0])
        self.assertIn("https://titan.example/app", message.answers[0][1].inline_keyboard[0][0].url)
        self.assertIn("uid=16", message.answers[0][1].inline_keyboard[0][0].url)


if __name__ == "__main__":
    unittest.main()
