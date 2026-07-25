async def check_subscription(user_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя активная VIP-подписка.
    Сейчас возвращаем True для всех, чтобы протестировать кнопку.
    """
    print(f"[DEBUG] Проверка подписки для пользователя {user_id}")
    return True
