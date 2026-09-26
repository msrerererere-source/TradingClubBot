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

    async def test_demo_columns_added_to_old_table(self):
        import aiosqlite

        async with aiosqlite.connect(db.DB_NAME) as connection:
            await connection.execute("DROP TABLE users")
            await connection.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    is_vip INTEGER DEFAULT 0,
                    expires_at TEXT,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await connection.commit()
        await db.init_db()
        await db.set_demo_access(3, "ABC123", "2026-09-27T12:00:00")
        user = await db.get_user(3)
        self.assertEqual(user["demo_password"], "ABC123")
        self.assertEqual(user["demo_until"], "2026-09-27T12:00:00")


class FakeUser:
    def __init__(self, user_id: int, username: str):
        self.id = user_id
        self.username = username


class FakeMessage:
    def __init__(self, user: FakeUser):
        self.from_user = user
        self.answers: list[tuple[str, object]] = []
        self.photos: list[dict] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def answer_photo(self, photo, caption=None, reply_markup=None):
        self.photos.append({"photo": photo, "caption": caption, "reply_markup": reply_markup})

    async def answer_media_group(self, media):
        self.gallery = list(media)


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
            for key in (
                "TITAN_TRACKER_URL",
                "TITAN_ACCESS_SECRET",
                "TITAN_ACCESS_TTL_HOURS",
                "TITAN_DEMO_URL",
                "TITAN_DEMO_PASSWORD",
            )
        }
        os.environ["TITAN_TRACKER_URL"] = "https://titan.example/app"
        os.environ["TITAN_ACCESS_SECRET"] = "club-secret"
        os.environ["TITAN_ACCESS_TTL_HOURS"] = "12"
        os.environ["TITAN_DEMO_URL"] = ""
        os.environ["TITAN_DEMO_PASSWORD"] = ""

    async def asyncTearDown(self):
        db.DB_NAME = self._previous
        os.remove(self._path)
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    async def test_start_menu_is_exactly_four_buttons(self):
        from handlers.club import WELCOME, cmd_start
        from keyboards import ABOUT_BUTTON, CONTACT_BUTTON, DEMO_BUTTON, TARIFFS_BUTTON

        message = FakeMessage(FakeUser(15, "guest"))
        await cmd_start(message)
        self.assertEqual(message.answers[0][0], WELCOME)
        self.assertEqual(len(message.answers), 1)
        labels = [button.text for row in message.answers[0][1].keyboard for button in row]
        self.assertEqual(labels, [ABOUT_BUTTON, DEMO_BUTTON, TARIFFS_BUTTON, CONTACT_BUTTON])

    async def test_about_sends_one_dashboard_photo(self):
        from handlers.club import about_button

        message = FakeMessage(FakeUser(15, "guest"))
        await about_button(message)
        text = "\n".join(item[0] for item in message.answers)
        self.assertIn("9 бирж", text)
        self.assertIn("скринер", text)
        self.assertIn("фандинг", text)
        self.assertNotIn("15 000", text)
        self.assertEqual(len(message.photos), 1)
        self.assertEqual(message.photos[0]["caption"], "Дашборд")
        self.assertTrue(str(message.photos[0]["photo"].path).endswith("02-dashboard.jpg"))
        self.assertFalse(hasattr(message, "gallery"))

    async def test_guest_does_not_receive_link(self):
        from handlers.club import present_titan

        message = FakeMessage(FakeUser(15, "guest"))
        await present_titan(message)
        text = "\n".join(item[0] for item in message.answers)
        self.assertIn("демо", text.lower())
        self.assertIn("тариф", text.lower())
        self.assertNotIn("15 000", text)
        self.assertNotIn("единоразово", text)
        self.assertNotIn("https://titan.example", text)
        self.assertFalse(hasattr(message, "gallery"))

    async def test_demo_issues_link_and_password_for_24h(self):
        from handlers.club import DEMO_ALPHABET, demo_button

        message = FakeMessage(FakeUser(21, "buyer"))
        await demo_button(message)
        text = "\n".join(item[0] for item in message.answers)
        self.assertIn("24 часа", text)
        self.assertIn("https://titan.example/app", text)
        self.assertNotIn("uid=", text)
        self.assertNotIn("sig=", text)
        password = _line_value(text, "Пароль:")
        self.assertEqual(len(password), 6)
        self.assertTrue(set(password) <= set(DEMO_ALPHABET))
        user = await db.get_user(21)
        until = datetime.fromisoformat(user["demo_until"])
        remaining = (until - datetime.now()).total_seconds()
        self.assertGreater(remaining, 23.9 * 3600)
        self.assertLess(remaining, 24 * 3600 + 30)
        self.assertIn(_format_check(until), text)

    async def test_demo_reuses_password_until_expiry_then_reissues(self):
        import aiosqlite

        from handlers.club import demo_button

        message = FakeMessage(FakeUser(22, "demo"))
        await demo_button(message)
        first = _line_value(message.answers[-1][0], "Пароль:")
        os.environ["TITAN_DEMO_PASSWORD"] = "SITE99"
        again = FakeMessage(FakeUser(22, "demo"))
        await demo_button(again)
        self.assertEqual(_line_value(again.answers[-1][0], "Пароль:"), first)
        past = (datetime.now() - timedelta(minutes=1)).isoformat()
        async with aiosqlite.connect(db.DB_NAME) as connection:
            await connection.execute(
                "UPDATE users SET demo_until = ? WHERE user_id = ?",
                (past, 22),
            )
            await connection.commit()
        renewed = FakeMessage(FakeUser(22, "demo"))
        await demo_button(renewed)
        self.assertEqual(_line_value(renewed.answers[-1][0], "Пароль:"), "SITE99")
        self.assertNotIn("uid=", renewed.answers[-1][0])

    async def test_paid_user_gets_real_link_instead_of_demo(self):
        from handlers.club import demo_button

        await db.set_vip_subscription(16, 30)
        message = FakeMessage(FakeUser(16, "member"))
        await demo_button(message)
        text = "\n".join(item[0] for item in message.answers)
        self.assertNotIn("Пароль:", text)
        opened = next(item for item in message.answers if "Титан Трекер открыт" in item[0])
        self.assertIn("uid=16", opened[1].inline_keyboard[0][0].url)

    async def test_demo_without_url_does_not_invent_password(self):
        from handlers.club import demo_button

        os.environ["TITAN_TRACKER_URL"] = ""
        os.environ["TITAN_DEMO_URL"] = ""
        message = FakeMessage(FakeUser(23, "guest"))
        await demo_button(message)
        text = "\n".join(item[0] for item in message.answers)
        self.assertIn("TITAN_DEMO_URL", text)
        self.assertNotIn("Пароль:", text)

    async def test_tariffs_do_not_invent_prices(self):
        from handlers.club import tariffs_button
        from keyboards import MENU_BUTTON, TARIFF_OPTIONS

        self.assertEqual(TARIFF_OPTIONS, [])
        message = FakeMessage(FakeUser(24, "guest"))
        await tariffs_button(message)
        text = message.answers[0][0]
        for banned in ("15 000", "15000", "3 000", "7 500", "25 000", "единоразово", "₽"):
            self.assertNotIn(banned, text)
        self.assertIn("три варианта подписки", text.lower())
        labels = [button.text for row in message.answers[0][1].keyboard for button in row]
        self.assertEqual(labels, [MENU_BUTTON])

    async def test_contact_has_admin_and_faq(self):
        from handlers.club import contact_button

        message = FakeMessage(FakeUser(25, "guest"))
        message.text = "📞 Связаться с администратором"
        await contact_button(message)
        text = message.answers[0][0]
        self.assertIn("https://t.me/", text)
        self.assertIn("Что это такое", text)
        self.assertIn("Демо-доступ", text)
        self.assertIn("Тарифы", text)

    async def test_vip_receives_signed_link(self):
        from handlers.club import present_titan

        await db.set_vip_subscription(16, 30)
        message = FakeMessage(FakeUser(16, "member"))
        await present_titan(message)
        opened = next(item for item in message.answers if "Титан Трекер открыт" in item[0])
        self.assertIn("https://titan.example/app", opened[1].inline_keyboard[0][0].url)
        self.assertIn("uid=16", opened[1].inline_keyboard[0][0].url)
        self.assertFalse(hasattr(message, "gallery"))
        self.assertEqual(message.photos, [])


def _line_value(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise AssertionError(text)


def _format_check(moment: datetime) -> str:
    return moment.strftime("%d.%m.%Y %H:%M")


if __name__ == "__main__":
    unittest.main()
