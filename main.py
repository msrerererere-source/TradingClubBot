import requests
import numpy as np

print("🚀 DEBUG: скрипт начал выполнение")

def get_bybit_ohlcv_futures(symbol="BTCUSDT", interval_minutes=60, limit=200):
    """
    Получает свечи ТОЛЬКО с рынка фьючерсов (linear / USDT Perpetual).
    interval_minutes: передавай сразу число минут (60 для 1ч, 240 для 4ч).
    Возвращает массив NumPy с ценами закрытия (close).
    """
    url = "https://api.bybit.com/v5/market/kline"
    
    params = {
        "category": "linear",       # ВАЖНО: только фьючерсы
        "symbol": symbol,           # BTCUSDT
        "interval": interval_minutes,  # ВАЖНО: число (60), а не строка '1h'
        "limit": limit              # Лимит свечей
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Проверка на HTTP ошибки (404, 500 и т.д.)
        
        data = response.json()
        ret_code = data.get("retCode")
        
        if ret_code != 0:
            print(f"❌ API ошибка Bybit: {data.get('retMsg')}")
            return np.array([])

        # Получаем свечи (только один раз!)
        candles = data.get("result", {}).get("list", [])

        if not candles:
            print("⚠️ Предупреждение: получено 0 свечей. Возможно, лимит слишком мал или рынок не активен.")
            return np.array([])

        # ВРЕМЕННАЯ ОТЛАДКА: смотрим структуру первых 2 свечей
        print("🔍 Первые 2 свечи (для проверки структуры):")
        for i, c in enumerate(candles[:2]):
            print(f"  Свеча {i}: {c}")

        # ИСПРАВЛЕНИЕ: берём только цену закрытия (индекс 4) из каждой свечи
        # Свеча от Bybit: [time, open, high, low, close, volume]
        close_prices = [float(candle) for candle in candles]
        
        print(f"✅ Успешно! Получено {len(close_prices)} цен закрытия.")
        return np.array(close_prices)

    except Exception as e:
        print(f"❌ Критическая ошибка соединения: {e}")
        return np.array([])

if __name__ == "__main__":
    print("🚀 Запуск получения свечей...")
    close_data = get_bybit_ohlcv_futures()
    
    if close_data.size > 0:
        print(f"📊 Первые 5 цен закрытия: {close_data[:5]}")
        print(f"📈 Средняя цена закрытия: {close_data.mean():.2f}")
    else:
        print("⚠️ Не удалось получить данные для анализа.")
