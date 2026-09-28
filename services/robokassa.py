"""Ссылка на оплату Robokassa и проверка сигнала «оплачено»."""

import hashlib
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from config import (
    robokassa_hash_algo,
    robokassa_is_test,
    robokassa_merchant_login,
    robokassa_password1,
    robokassa_password2,
)

PRIVATE_SUM = "30000.00"
COMPANY_SUM = "250000.00"
PRICES = (Decimal(PRIVATE_SUM), Decimal(COMPANY_SUM))
PAY_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def robokassa_ready() -> bool:
    return bool(robokassa_merchant_login() and robokassa_password1() and robokassa_password2())


def parse_amount(raw: str) -> Decimal | None:
    try:
        return Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def amount_is_price(raw: str) -> bool:
    value = parse_amount(raw)
    return value in PRICES


def same_amount(left: str, right: str) -> bool:
    parsed_left = parse_amount(left)
    parsed_right = parse_amount(right)
    return parsed_left is not None and parsed_left == parsed_right


def format_rubles(raw: str) -> str:
    value = parse_amount(raw)
    if value is None:
        return str(raw)
    grouped = f"{int(value):,}".replace(",", " ")
    return f"{grouped} ₽"


def _digest(payload: str) -> str:
    algo = robokassa_hash_algo()
    encoded = payload.encode()
    if algo == "sha256":
        return hashlib.sha256(encoded).hexdigest().upper()
    return hashlib.md5(encoded).hexdigest().upper()


def payment_signature(inv_id: int, user_id: int, out_sum: str) -> str:
    payload = ":".join(
        [
            robokassa_merchant_login(),
            out_sum,
            str(inv_id),
            robokassa_password1(),
            f"Shp_user={user_id}",
        ]
    )
    return _digest(payload)


def build_payment_url(inv_id: int, user_id: int, out_sum: str) -> str:
    params = {
        "MerchantLogin": robokassa_merchant_login(),
        "OutSum": out_sum,
        "InvId": str(inv_id),
        "Description": "Доступ Титан Трекер",
        "SignatureValue": payment_signature(inv_id, user_id, out_sum),
        "Culture": "ru",
        "Encoding": "utf-8",
        "Shp_user": str(user_id),
    }
    if robokassa_is_test():
        params["IsTest"] = "1"
    return f"{PAY_URL}?{urlencode(params)}"


def result_signature(out_sum: str, inv_id: str, shp: dict[str, str]) -> str:
    parts = [out_sum, str(inv_id), robokassa_password2()]
    for key in sorted(shp):
        parts.append(f"{key}={shp[key]}")
    return _digest(":".join(parts))


def result_is_valid(params: dict[str, str]) -> bool:
    out_sum = params.get("OutSum", "")
    inv_id = params.get("InvId", "")
    signature = params.get("SignatureValue", "")
    if not out_sum or not inv_id or not signature or not robokassa_password2():
        return False
    if not amount_is_price(out_sum):
        return False
    shp = {key: value for key, value in params.items() if key.startswith("Shp_")}
    expected = result_signature(out_sum, inv_id, shp)
    return expected.lower() == signature.strip().lower()
