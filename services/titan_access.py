"""Персональная ссылка на Титан Трекер.

Бот не встраивает терминал: исходников трекера в этом репозитории нет.
Связка такая: активный VIP получает ссылку, а Титан Трекер проверяет подпись.

Параметры ссылки:
    uid — Telegram user id
    exp — unix-время, до которого ссылка действует
    sig — HMAC-SHA256 от строки "{uid}:{exp}" ключом TITAN_ACCESS_SECRET

На стороне трекера достаточно пересчитать подпись и сравнить её через
compare_digest, затем убедиться, что exp ещё не прошёл.
"""

import hashlib
import hmac
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config import titan_access_secret, titan_access_ttl_hours, titan_tracker_url


def _sign(user_id: int, exp: int) -> str:
    payload = f"{user_id}:{exp}".encode()
    return hmac.new(titan_access_secret().encode(), payload, hashlib.sha256).hexdigest()


def build_titan_link(user_id: int, now: float | None = None) -> tuple[str, bool] | None:
    """Возвращает (url, personal).

    personal=True, если ссылка подписана и привязана к пользователю.
    Без TITAN_TRACKER_URL ссылки нет. Без секрета возвращается общий адрес.
    """
    base = titan_tracker_url()
    if not base:
        return None
    if not titan_access_secret():
        return base, False

    moment = int(now if now is not None else time.time())
    exp = moment + titan_access_ttl_hours() * 3600
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({"uid": str(user_id), "exp": str(exp), "sig": _sign(user_id, exp)})
    signed = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return signed, True


def verify_titan_access(user_id: int, exp: int, signature: str, now: float | None = None) -> bool:
    """Проверка, которую должен выполнять Титан Трекер, когда получит исходники."""
    secret = titan_access_secret()
    if not secret or not signature:
        return False
    moment = int(now if now is not None else time.time())
    if exp < moment:
        return False
    expected = _sign(user_id, exp)
    return hmac.compare_digest(expected, signature)
