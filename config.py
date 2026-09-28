import os

from dotenv import load_dotenv

load_dotenv()


def bot_display_name() -> str:
    return os.getenv("BOT_DISPLAY_NAME", "Титан Трекер").strip() or "Титан Трекер"


def bot_token() -> str:
    return os.getenv("BOT_TOKEN", "").strip()


def admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "Natilev500").strip().lstrip("@")


def titan_tracker_url() -> str:
    return os.getenv("TITAN_TRACKER_URL", "").strip()


def paid_terminal_url() -> str:
    return titan_tracker_url() or "https://titan-tracker.onrender.com"


def titan_demo_url() -> str:
    return os.getenv("TITAN_DEMO_URL", "").strip() or titan_tracker_url()


def titan_demo_password() -> str:
    return os.getenv("TITAN_DEMO_PASSWORD", "").strip()


def robokassa_merchant_login() -> str:
    return os.getenv("ROBOKASSA_MERCHANT_LOGIN", "").strip()


def robokassa_password1() -> str:
    return os.getenv("ROBOKASSA_PASSWORD1", "").strip()


def robokassa_password2() -> str:
    return os.getenv("ROBOKASSA_PASSWORD2", "").strip()


def robokassa_is_test() -> bool:
    return os.getenv("ROBOKASSA_TEST", "").strip().lower() in {"1", "true", "yes"}


def robokassa_hash_algo() -> str:
    algo = os.getenv("ROBOKASSA_HASH", "md5").strip().lower()
    return algo if algo in {"md5", "sha256"} else "md5"


def robokassa_result_port() -> int:
    raw = os.getenv("ROBOKASSA_RESULT_PORT", "8080").strip()
    try:
        port = int(raw)
    except ValueError:
        return 8080
    return port if port > 0 else 8080


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
