import os

from dotenv import load_dotenv

load_dotenv()


def bot_display_name() -> str:
    return os.getenv("BOT_DISPLAY_NAME", "Дашборд Титан Бот").strip() or "Дашборд Титан Бот"


def bot_token() -> str:
    return os.getenv("BOT_TOKEN", "").strip()


def admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "natalia_trading").strip().lstrip("@")


def titan_tracker_url() -> str:
    return os.getenv("TITAN_TRACKER_URL", "").strip()


def titan_access_secret() -> str:
    return os.getenv("TITAN_ACCESS_SECRET", "").strip()


def titan_access_ttl_hours() -> int:
    raw = os.getenv("TITAN_ACCESS_TTL_HOURS", "12").strip()
    try:
        hours = int(raw)
    except ValueError:
        return 12
    return hours if hours > 0 else 12


def titan_webapp_enabled() -> bool:
    return os.getenv("TITAN_WEBAPP", "").strip().lower() in {"1", "true", "yes"}
