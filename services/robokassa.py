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

OUT_SUM = "15000.00"
PRICE = Decimal("15000.00")
PAY_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def robokassa_ready() -> bool:
    return bool(robokassa_merchant_login() and robokassa_password1() and robokassa_password2())


def amount_is_price(raw: str) -> bool:
    try:
        value = Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, ValueError):
        return False
    return value == PRICE


def _digest(payload: str) -> str:
    algo = robokassa_hash_algo()
    encoded = payload.encode()
    if algo == "sha256":
        return hashlib.sha256(encoded).hexdigest().upper()
    return hashlib.md5(encoded).hexdigest().upper()


def payment_signature(inv_id: int, user_id: int) -> str:
    payload = ":".join(
        [
            robokassa_merchant_login(),
            OUT_SUM,
            str(inv_id),
            robokassa_password1(),
            f"Shp_user={user_id}",
        ]
    )
    return _digest(payload)


def build_payment_url(inv_id: int, user_id: int) -> str:
    params = {
        "MerchantLogin": robokassa_merchant_login(),
        "OutSum": OUT_SUM,
        "InvId": str(inv_id),
        "Description": "Доступ Титан Трекер",
        "SignatureValue": payment_signature(inv_id, user_id),
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
