from db import check_vip_status


async def check_subscription(user_id: int) -> bool:
    """Активный VIP: флаг включён и срок ещё не вышел."""
    status = await check_vip_status(user_id)
    return status["is_vip"] and not status["is_expired"]
