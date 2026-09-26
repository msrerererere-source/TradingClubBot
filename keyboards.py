from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import titan_webapp_enabled

ABOUT_BUTTON = "📊 Что это такое"
DEMO_BUTTON = "🔓 Демо-доступ"
TARIFFS_BUTTON = "💳 Тарифы"
CONTACT_BUTTON = "📞 Связаться"
MENU_BUTTON = "◀️ Главное меню"

# Три варианта подписки. Названия и цены приходят отдельно, пока список пуст.
TARIFF_OPTIONS: list[str] = []


def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text=ABOUT_BUTTON)
    builder.button(text=DEMO_BUTTON)
    builder.button(text=TARIFFS_BUTTON)
    builder.button(text=CONTACT_BUTTON)
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_vip_action_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text=MENU_BUTTON)
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_tariffs_keyboard(options: list[str]):
    builder = ReplyKeyboardBuilder()
    for title in options:
        builder.button(text=title)
    builder.button(text=MENU_BUTTON)
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_vip_keyboard():
    """Старая кнопка оставлена: по ней бот открывает тот же вход в трекер."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🛰 Открыть Титан Трекер", callback_data="titan_access")
    builder.adjust(1)
    return builder.as_markup()


def titan_open_keyboard(url: str) -> InlineKeyboardMarkup | None:
    rows = []
    if url.startswith("https://") and titan_webapp_enabled():
        rows.append(
            [InlineKeyboardButton(text="Открыть в Telegram", web_app=WebAppInfo(url=url))]
        )
    if url.startswith("https://") or url.startswith("http://"):
        rows.append([InlineKeyboardButton(text="Открыть Титан Трекер", url=url)])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)
