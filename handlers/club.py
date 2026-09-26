import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message

from config import (
    admin_username,
    titan_access_ttl_hours,
    titan_demo_password,
    titan_demo_url,
    titan_pay_card,
    titan_pay_sbp,
)
from db import (
    cancel_vip_subscription,
    check_vip_status,
    expired_unnotified_demos,
    get_user,
    mark_demo_notified,
    set_demo_access,
    set_vip_subscription,
    upsert_user,
)
from keyboards import (
    ABOUT_BUTTON,
    BACK_BUTTON,
    CONTACT_BUTTON,
    DEMO_BUTTON,
    MENU_BUTTON,
    PAY_BUTTON,
    TARIFFS_BUTTON,
    TRY_BUTTON,
    get_about_keyboard,
    get_demo_keyboard,
    get_main_keyboard,
    get_tariffs_keyboard,
    get_vip_action_keyboard,
    titan_open_keyboard,
)
from services.titan_access import build_titan_link
from subscription_check import check_subscription

router = Router()

DEMO_HOURS = 24
DEMO_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ABOUT_SHOTS = (
    ("02-dashboard.jpg", "Скриншот дашборда"),
    ("03-screener.jpg", "Скриншот скринера"),
    ("04-funding.jpg", "Скриншот фандинга"),
)

WELCOME = (
    "👋 Привет! Я — бот Титан Трекера.\n"
    "Веб-терминал для межбиржевого арбитража: 9 бирж,\n"
    "реальное время, скринер спредов и ставок фандинга\n"
    "в одном окне.\n"
    "Выбери, что нужно:"
)


def is_admin(username: str | None) -> bool:
    admin = admin_username()
    return bool(username and admin) and username.lower() == admin.lower()


def admin_contact() -> str:
    admin = admin_username()
    if not admin:
        return "Администратор пока не указан."
    return f"Администратор: https://t.me/{admin}"


def about_text() -> str:
    return (
        "Титан Трекер — веб-терминал межбиржевого арбитража.\n"
        "Открывается по ссылке в браузере. В одном окне\n"
        "держит цены и ставки финансирования с 9 бирж.\n"
        "Три контура:\n"
        "• Дашборд — общая рыночная картина\n"
        "• Скринер — ищет пары с достаточным спредом\n"
        "• Фандинг — ищет разницу ставок по контрактам\n"
        "Обновление в реальном времени, счётчик свежести\n"
        "на экране — 14 секунд.\n"
        "Заявки на биржи не отправляет. Терминал показывает\n"
        "возможность — решение за тобой."
    )


def contact_text() -> str:
    return (
        admin_contact()
        + "\n\n"
        "Коротко по кнопкам:\n"
        "• 📊 Что это такое — описание и скриншоты дашборда, скринера и фандинга.\n"
        "• 🔓 Демо-доступ — ссылка и пароль на 24 часа.\n"
        "• 💳 Тарифы — Dashboard, единоразово 15 000 ₽.\n"
        "• 📞 Связаться — написать администратору."
    )


def tariffs_text() -> str:
    return (
        "💳 Тарифы\n"
        "📊 Dashboard — единоразовый доступ — 15 000 ₽\n"
        "Полный доступ к терминалу Титан Трекер.\n"
        "Один платёж — бессрочный доступ.\n"
        "Дашборд, скринер спредов, ставки фандинга —\n"
        "все 9 бирж в одном окне.\n"
        "Оплата:\n"
        "💳 Банковская карта\n"
        "📲 СБП — перевод по QR или ссылке\n"
        "После оплаты бот автоматически сгенерирует\n"
        "пароль и выдаст ссылку на терминал\n"
        "в течение 1 минуты.\n"
        "⚠️ Терминал предоставляет аналитику и не\n"
        "является торговой рекомендацией. Решение\n"
        "о сделке принимаешь ты."
    )


def pay_text() -> str:
    card = titan_pay_card()
    sbp = titan_pay_sbp()
    lines = [
        "Оплата 15 000 ₽. Один платёж — бессрочный доступ.",
        "",
    ]
    if card:
        lines.append(f"💳 Банковская карта: {card}")
    else:
        lines.append("💳 Банковская карта")
    if sbp:
        lines.append(f"📲 СБП — перевод по QR или ссылке: {sbp}")
    else:
        lines.append("📲 СБП — перевод по QR или ссылке")
    if not card and not sbp:
        lines.append("")
        lines.append(admin_contact())
    lines.append("")
    lines.append("После оплаты бот выдаст пароль и ссылку на терминал.")
    return "\n".join(lines)


def about_gallery() -> list[InputMediaPhoto]:
    folder = Path(__file__).resolve().parent.parent / "images" / "titan"
    media = []
    for name, caption in ABOUT_SHOTS:
        path = folder / name
        if path.is_file():
            media.append(InputMediaPhoto(media=FSInputFile(path), caption=caption))
    return media


DEMO_LOGIN = "demo"


def demo_access_text(url: str, password: str) -> str:
    return (
        "Даю тебе 24 часа полного доступа к терминалу.\n"
        f"Ссылка: {url}\n"
        f"Логин: {DEMO_LOGIN}\n"
        f"Пароль: {password}\n"
        "Что можно делать:\n"
        "• Видеть все 9 бирж\n"
        "• Смотреть спреды и фандинг\n"
        "• Проверить, как работает счётчик свежести\n"
        "Что нельзя:\n"
        "• Менять настройки\n"
        "• Торговать (терминал не отправляет заявки)\n"
        "⏰ Доступ активен 24 часа с момента выдачи.\n"
        "После — придёт уведомление, и доступ закроется.\n"
        "Если зайдёт — пиши, откроем полный доступ."
    )


def demo_closed_text() -> str:
    return (
        "⏰ 24 часа демо закончились. Доступ закрыт.\n"
        "Если терминал зашёл — напиши, откроем полный доступ."
    )


def _parse_positive_int(value: str) -> int:
    if not value.isdigit():
        raise ValueError(value)
    number = int(value)
    if number <= 0:
        raise ValueError(value)
    return number


def _new_demo_password() -> str:
    shared = titan_demo_password()
    if shared:
        return shared
    return "".join(secrets.choice(DEMO_ALPHABET) for _ in range(6))


async def issue_demo(user_id: int, now: datetime | None = None) -> tuple[str, datetime]:
    """Возвращает пароль и момент окончания. До истечения пароль тот же."""
    moment = now or datetime.now()
    user = await get_user(user_id)
    if user is not None:
        stored_until = user["demo_until"]
        stored_password = user["demo_password"]
        if stored_until and stored_password:
            try:
                until = datetime.fromisoformat(stored_until)
            except ValueError:
                until = None
            if until is not None and until > moment:
                return stored_password, until
    password = _new_demo_password()
    until = moment + timedelta(hours=DEMO_HOURS)
    await set_demo_access(user_id, password, until.isoformat())
    return password, until


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await upsert_user(user.id, user.username)
    await message.answer(WELCOME, reply_markup=get_main_keyboard())
    if is_admin(user.username):
        await message.answer(
            "Команды администратора:\n"
            "/grant 30 — открыть себе доступ на 30 дней\n"
            "/grant <id> <дни> — открыть доступ участнику\n"
            "/revoke <id> — закрыть доступ"
        )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    await _send_status(message)


@router.message(Command("titan"))
async def cmd_titan(message: Message) -> None:
    await present_titan(message)


@router.message(Command("grant"))
async def cmd_grant(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.username):
        await message.answer("Эту команду выполняет администратор.")
        return
    try:
        user_id, days = _grant_target(command.args or "", message.from_user.id)
    except ValueError:
        await message.answer("Формат: /grant 30 или /grant <id участника> <дни от 1 до 365>.")
        return
    await set_vip_subscription(user_id, days)
    user = await get_user(user_id)
    expires = user["expires_at"] if user else "неизвестно"
    await message.answer(f"Доступ открыт для {user_id} на {days} дн. До: {expires}")


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.username):
        await message.answer("Эту команду выполняет администратор.")
        return
    raw = (command.args or "").strip()
    try:
        user_id = _parse_positive_int(raw) if raw else message.from_user.id
    except ValueError:
        await message.answer("Формат: /revoke или /revoke <id участника>.")
        return
    await upsert_user(user_id, None)
    await cancel_vip_subscription(user_id)
    await message.answer(f"Доступ закрыт для {user_id}.")


@router.message(F.text == ABOUT_BUTTON)
async def about_button(message: Message) -> None:
    await message.answer(about_text(), reply_markup=get_about_keyboard())
    media = about_gallery()
    if len(media) >= 2:
        sender = getattr(message, "answer_media_group", None)
        if sender is not None:
            await sender(media=media)
            return
    for item in media:
        await message.answer_photo(item.media, caption=item.caption)


@router.message(F.text.in_({DEMO_BUTTON, TRY_BUTTON}))
async def demo_button(message: Message) -> None:
    user = message.from_user
    await upsert_user(user.id, user.username)
    if await check_subscription(user.id):
        await message.answer("Доступ уже открыт. Демо не нужно.")
        await send_paid_link(message)
        return
    url = titan_demo_url()
    if not url:
        await message.answer(
            "Демо пока не открыто: в .env нет TITAN_DEMO_URL или TITAN_TRACKER_URL.",
            reply_markup=get_demo_keyboard(),
        )
        return
    password, _until = await issue_demo(user.id)
    await message.answer(
        demo_access_text(url, password),
        reply_markup=get_demo_keyboard(),
    )


@router.message(F.text == TARIFFS_BUTTON)
async def tariffs_button(message: Message) -> None:
    await message.answer(tariffs_text(), reply_markup=get_tariffs_keyboard())


@router.message(F.text == PAY_BUTTON)
async def pay_button(message: Message) -> None:
    await upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(pay_text(), reply_markup=get_tariffs_keyboard())


@router.message(F.text.in_({CONTACT_BUTTON, "📞 Связаться с администратором"}))
async def contact_button(message: Message) -> None:
    await message.answer(contact_text(), reply_markup=get_main_keyboard())


@router.message(F.text == "🛰 Титан Трекер")
async def titan_button(message: Message) -> None:
    await present_titan(message)


@router.message(F.text == "✅ Продлить обучение (автопродление)")
async def renew_button(message: Message) -> None:
    await tariffs_button(message)


@router.message(F.text == "❌ Не продлевать (отключить доступ)")
async def cancel_button(message: Message) -> None:
    await upsert_user(message.from_user.id, message.from_user.username)
    await cancel_vip_subscription(message.from_user.id)
    await message.answer(
        "Доступ отключён. Ссылка на Титан Трекер для этого аккаунта закрыта.",
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text.in_({MENU_BUTTON, BACK_BUTTON}))
async def main_menu_button(message: Message) -> None:
    await message.answer(WELCOME, reply_markup=get_main_keyboard())


@router.callback_query(F.data == "titan_access")
async def titan_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await present_titan(callback.message)


@router.message(F.text)
async def fallback(message: Message) -> None:
    await message.answer(
        "Выберите пункт меню или отправьте /start.",
        reply_markup=get_main_keyboard(),
    )


def _grant_target(args: str, sender_id: int) -> tuple[int, int]:
    parts = args.split()
    if len(parts) == 1:
        days = _parse_positive_int(parts[0])
        user_id = sender_id
    elif len(parts) == 2:
        user_id = _parse_positive_int(parts[0])
        days = _parse_positive_int(parts[1])
    else:
        raise ValueError(args)
    if days > 365:
        raise ValueError(args)
    return user_id, days


async def _send_status(message: Message) -> None:
    user = message.from_user
    await upsert_user(user.id, user.username)
    active = await check_subscription(user.id)
    record = await get_user(user.id)
    if active:
        expires = record["expires_at"] if record and record["expires_at"] else "без даты окончания"
        text = f"Доступ открыт. Титан Трекер можно открыть.\nДо: {expires}"
        markup = get_vip_action_keyboard()
    else:
        status = await check_vip_status(user.id)
        if status["is_vip"] and status["is_expired"]:
            text = "Срок доступа истёк. Ссылка на терминал закрыта."
        else:
            text = "Доступ ещё не открыт."
        text += "\nДемо — на 24 часа. Тариф — 15 000 ₽ единоразово.\n\n" + admin_contact()
        markup = get_main_keyboard()
    await message.answer(text, reply_markup=markup)


async def present_titan(message: Message) -> None:
    user = message.from_user
    await upsert_user(user.id, user.username)
    if not await check_subscription(user.id):
        status = await check_vip_status(user.id)
        if status["is_vip"] and status["is_expired"]:
            reason = "Срок доступа истёк. Ссылка на терминал закрыта."
        else:
            reason = "Доступ ещё не открыт."
        await message.answer(
            reason + "\nМожно взять демо на 24 часа или открыть тарифы.\n\n" + admin_contact(),
            reply_markup=get_main_keyboard(),
        )
        return
    await send_paid_link(message)


async def watch_demo_expiry(bot) -> None:
    """Пишет человеку, когда его 24 часа демо закончились."""
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

    for row in await expired_unnotified_demos():
        user_id = row["user_id"]
        try:
            await bot.send_message(
                user_id,
                demo_closed_text(),
                reply_markup=get_main_keyboard(),
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            await mark_demo_notified(user_id)
        except Exception:
            logging.getLogger(__name__).exception("Не удалось закрыть демо %s", user_id)
        else:
            await mark_demo_notified(user_id)


async def send_paid_link(message: Message) -> None:
    user = message.from_user
    built = build_titan_link(user.id)
    if built is None:
        await message.answer(
            "Доступ активен. Адрес Титан Трекера ещё не задан: "
            "в .env нужна переменная TITAN_TRACKER_URL.\n\n" + admin_contact(),
            reply_markup=get_vip_action_keyboard(),
        )
        return

    link, personal = built
    record = await get_user(user.id)
    expires = ""
    if record and record["expires_at"]:
        expires = f"\nДо: {record['expires_at']}"
    if personal:
        freshness = f"Персональная ссылка действует {titan_access_ttl_hours()} ч."
    else:
        freshness = "Сейчас выдаётся общий адрес терминала. Персональная подпись включится после TITAN_ACCESS_SECRET."
    keyboard = titan_open_keyboard(link)
    text = f"Титан Трекер открыт.{expires}\n{freshness}"
    if keyboard is None:
        text += f"\n{link}"
    await message.answer(text, reply_markup=keyboard)
    await message.answer("Управление доступом:", reply_markup=get_vip_action_keyboard())
