"""Оплата доступа: счёт, пароль и запись в базу."""

import secrets
from datetime import datetime

from config import paid_terminal_url
from db import (
    activate_paid_access,
    create_payment,
    get_payment,
    get_user,
    mark_payment_notified,
)
from services.robokassa import build_payment_url, result_is_valid, robokassa_ready, same_amount

ACCESS_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"


def new_access_password() -> str:
    tail = "".join(secrets.choice(ACCESS_ALPHABET) for _ in range(6))
    return f"Titan-{tail}"


def user_access(user) -> tuple[str, str] | None:
    if user is None:
        return None
    if user["access_status"] != "активен" or not user["access_password"]:
        return None
    return paid_terminal_url(), user["access_password"]


async def current_access(user_id: int) -> tuple[str, str] | None:
    return user_access(await get_user(user_id))


async def start_checkout(user_id: int, amount: str) -> str | None:
    if not robokassa_ready():
        return None
    inv_id = await create_payment(user_id, amount)
    return build_payment_url(inv_id, user_id, amount)


async def accept_robokassa_result(params: dict[str, str]) -> dict | None:
    """Принимает сигнал Robokassa. Повторный сигнал не выдаёт новый пароль."""
    if not result_is_valid(params):
        return None
    try:
        inv_id = int(params["InvId"])
    except (KeyError, ValueError):
        return None
    payment = await get_payment(inv_id)
    if payment is None:
        return None
    shp_user = params.get("Shp_user")
    if shp_user and str(payment["user_id"]) != str(shp_user):
        return None
    if not same_amount(params.get("OutSum", ""), payment["amount"]):
        return None
    if payment["status"] == "paid":
        user = await get_user(payment["user_id"])
        password = payment["password"] or (user["access_password"] if user else "")
        return {
            "inv_id": inv_id,
            "user_id": payment["user_id"],
            "password": password,
            "needs_send": not bool(payment["notified"]),
        }
    password = new_access_password()
    paid_at = datetime.now().isoformat()
    await activate_paid_access(payment["user_id"], password, paid_at, inv_id)
    return {
        "inv_id": inv_id,
        "user_id": payment["user_id"],
        "password": password,
        "needs_send": True,
    }


async def mark_result_delivered(inv_id: int) -> None:
    await mark_payment_notified(inv_id)
