from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from config import admin_username, bot_display_name, titan_access_ttl_hours
from db import (
    cancel_vip_subscription,
    check_vip_status,
    get_user,
    set_vip_subscription,
    upsert_user,
)
from keyboards import (
    get_main_keyboard,
    get_vip_action_keyboard,
    titan_open_keyboard,
)
from services.titan_access import build_titan_link
from subscription_check import check_subscription
from theory_blocks import theory_blocks

router = Router()


def is_admin(username: str | None) -> bool:
    admin = admin_username()
    return bool(username and admin) and username.lower() == admin.lower()


def admin_contact() -> str:
    admin = admin_username()
    if not admin:
        return "Администратор клуба пока не указан."
    return f"Администратор: https://t.me/{admin}"


def _parse_positive_int(value: str) -> int:
    if not value.isdigit():
        raise ValueError(value)
    number = int(value)
    if number <= 0:
        raise ValueError(value)
    return number


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await upsert_user(user.id, user.username)
    admin_help = ""
    if is_admin(user.username):
        admin_help = (
            "\n\nКоманды администратора:\n"
            "/grant 30 — открыть себе VIP на 30 дней\n"
            "/grant <id> <дни> — открыть VIP участнику\n"
            "/revoke <id> — закрыть доступ"
        )
    await message.answer(
        f"Привет. Это {bot_display_name()}.\n\n"
        "Арбитраж и расхождения ставок финансирования по 9 биржам. "
        "Внутри разделы «Дашборд», «Скринер» и «Фандинг».\n\n"
        f"{price_text()}\n\n"
        "/status — проверить доступ\n"
        "/titan — открыть Титан Трекер"
        + admin_help,
        reply_markup=get_main_keyboard(),
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
        await message.answer("Эту команду выполняет администратор клуба.")
        return
    try:
        user_id, days = _grant_target(command.args or "", message.from_user.id)
    except ValueError:
        await message.answer("Формат: /grant 30 или /grant <id участника> <дни от 1 до 365>.")
        return
    await set_vip_subscription(user_id, days)
    user = await get_user(user_id)
    expires = user["expires_at"] if user else "неизвестно"
    await message.answer(f"VIP открыт для {user_id} на {days} дн. До: {expires}")


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.username):
        await message.answer("Эту команду выполняет администратор клуба.")
        return
    raw = (command.args or "").strip()
    try:
        user_id = _parse_positive_int(raw) if raw else message.from_user.id
    except ValueError:
        await message.answer("Формат: /revoke или /revoke <id участника>.")
        return
    await upsert_user(user_id, None)
    await cancel_vip_subscription(user_id)
    await message.answer(f"VIP закрыт для {user_id}.")


@router.message(F.text == "🛰 Титан Трекер")
async def titan_button(message: Message) -> None:
    await present_titan(message)


@router.message(F.text == "💎 VIP: обучение и разбор сделок")
async def vip_button(message: Message) -> None:
    await _send_status(message)


@router.message(F.text == "📜 Правила клуба")
async def rules_button(message: Message) -> None:
    await message.answer(
        "Правила клуба\n\n"
        "1. Титан Трекер — наблюдательный терминал. Он показывает ценовой спред "
        "и расхождение фандинга, заявки на биржи сам не отправляет.\n"
        "2. Ссылку на терминал получает участник с активным VIP.\n"
        "3. Разбор в клубе — это учебный материал, не поручение открыть сделку.\n"
        "4. Решение о входе, объёме и сроке удержания остаётся за вами.\n\n"
        + admin_contact(),
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "📅 Расписание сделок")
async def schedule_button(message: Message) -> None:
    await message.answer(
        "Титан Трекер работает постоянно. На его панели стоят часы Токио, Лондона, "
        "Нью-Йорка и Москвы, чтобы торговая сессия была видна без пересчёта.\n\n"
        "Разборы клуба назначает администратор и публикует их отдельно.\n\n"
        + admin_contact(),
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "❓ Помощь")
async def help_button(message: Message) -> None:
    await message.answer(
        "Как пользоваться ботом\n\n"
        "🛰 Титан Трекер — получить ссылку, если VIP активен.\n"
        "/status — дата окончания доступа.\n"
        "/titan — открыть терминал.\n"
        "◀️ Главное меню — вернуться к основным кнопкам.\n\n"
        + admin_contact(),
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "📞 Связаться с администратором")
async def contact_button(message: Message) -> None:
    await message.answer(admin_contact(), reply_markup=get_main_keyboard())


@router.message(F.text == "⚡ Кратко о правилах")
async def short_rules_button(message: Message) -> None:
    candles = "\n\n".join(block["text"] for block in theory_blocks.values())
    await message.answer(
        "Коротко\n"
        "• Терминал показывает расхождения и не торгует за вас.\n"
        "• Ссылка на Титан Трекер живёт, пока действует VIP.\n"
        "• Риск и размер позиции считаете вы.\n\n"
        f"Опора по свечам:\n{candles}",
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "✅ Продлить обучение (автопродление)")
async def renew_button(message: Message) -> None:
    if is_admin(message.from_user.username):
        await set_vip_subscription(message.from_user.id, 30)
        await message.answer(
            "VIP продлён на 30 дней. Титан Трекер можно открыть сразу.",
            reply_markup=get_vip_action_keyboard(),
        )
        return
    await message.answer(
        "Продление подтверждает администратор клуба. "
        "После подтверждения бот снова выдаст ссылку на Титан Трекер.\n\n"
        + admin_contact(),
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "❌ Не продлевать (отключить доступ)")
async def cancel_button(message: Message) -> None:
    await upsert_user(message.from_user.id, message.from_user.username)
    await cancel_vip_subscription(message.from_user.id)
    await message.answer(
        "VIP отключён. Ссылка на Титан Трекер для этого аккаунта закрыта.",
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "◀️ Главное меню")
async def main_menu_button(message: Message) -> None:
    await message.answer("Главное меню.", reply_markup=get_main_keyboard())


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
            text = "Срок доступа истёк. Ссылка на Титан Трекер закрыта."
        else:
            text = "Доступ ещё не открыт.\n" + price_text()
        text += "\n\n" + admin_contact()
        markup = get_main_keyboard()
    await message.answer(text, reply_markup=markup)


def titan_about_text() -> str:
    return (
        "Титан Трекер — терминал межбиржевого арбитража и ставок финансирования.\n\n"
        "Что делает:\n"
        "• Собирает 9 бирж в одном окне.\n"
        "• Дашборд показывает общую картину рынка.\n"
        "• Скринер находит расхождение цены между биржами.\n"
        "• Фандинг показывает, где ставки финансирования разошлись.\n"
        "• Данные идут в реальном времени.\n"
        "• Часы Токио, Лондона, Нью-Йорка и Москвы показывают торговую сессию.\n"
        "• Новичку по этим разделам видно, как устроена связка и с чего начать.\n\n"
        "Чего не делает:\n"
        "• Не открывает сделки на биржах.\n"
        "• Не обещает прибыль.\n"
        "• Объём и решение о входе остаются за человеком.\n\n"
        f"{price_text()}\n"
        "Ссылку на терминал бот выдаёт после оплаты."
    )


def price_text() -> str:
    return "Стоимость: 15 000 ₽.\nОплата один раз. Подписки нет."


async def present_titan(message: Message) -> None:
    await message.answer(titan_about_text())
    user = message.from_user
    await upsert_user(user.id, user.username)
    if not await check_subscription(user.id):
        status = await check_vip_status(user.id)
        if status["is_vip"] and status["is_expired"]:
            reason = "Срок доступа истёк, поэтому ссылка на Титан Трекер закрыта."
        else:
            reason = (
                "Титан Трекер стоит 15 000 ₽. Оплата один раз, подписки нет. "
                "Ссылка на терминал открывается после оплаты."
            )
        await message.answer(reason + "\n\n" + admin_contact(), reply_markup=get_main_keyboard())
        return

    built = build_titan_link(user.id)
    if built is None:
        await message.answer(
            "VIP-доступ активен. Адрес Титан Трекера ещё не задан: "
            "в .env нужна переменная TITAN_TRACKER_URL.\n\n" + admin_contact(),
            reply_markup=get_vip_action_keyboard(),
        )
        return

    link, personal = built
    record = await get_user(user.id)
    expires = ""
    if record and record["expires_at"]:
        expires = f"\nVIP до: {record['expires_at']}"
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
