def detect_whales(orderbook_data, threshold_btc=1.0):
    """
    Анализирует стакан и помечает крупные заявки.
    
    Args:
        orderbook_data: список словарей с данными стакана.
        threshold_btc: порог объёма в BTC для определения кита.
    
    Returns:
        Список словарей с добавленными полями 'Статус' и 'is_whale'.
    """
    result = []
    for row in orderbook_data:
        # Безопасное получение объёма (на случай, если ключа нет)
        volume = float(row.get("Объём (BTC)", 0))
        is_whale = volume >= threshold_btc
        
        if is_whale:
            status = "🔴 Крупная заявка (Кит!)"
        else:
            status = "🟢 Обычная заявка"
        
        # Создаем новую строку, чтобы не менять исходные данные
        new_row = row.copy()
        new_row["Статус"] = status
        new_row["is_whale"] = is_whale
        result.append(new_row)
    
    return result
