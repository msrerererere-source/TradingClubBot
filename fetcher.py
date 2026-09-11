import requests
import numpy as np

def get_bybit_ohlcv(symbol="BTCUSDT", interval="1h", limit=100):
    """
    Скачивает свечи с публичного API Bybit.
    Сначала пробует категорию 'linear', если пусто - пробует 'spot'.
    """
    url = "https://api.bybit.com/v5/market/kline"
    
    # Пробуем две категории по очереди, если первая не даст данных
    categories_to_try = ["linear", "spot"] 
    
    for category in categories_to_try:
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        print(f"📡 Пробуем категорию: {category}...")
        print(f"📡 Запрос: {url}?{params}")

        try:
            response = requests.get(url, params=params, timeout=10)
            print(f"📡 HTTP Статус: {response.status_code}")
            
            data = response.json()
            ret_code = data.get("retCode")
            ret_msg = data.get("retMsg")

            if ret_code and ret_code != 0:
                print(f"⚠️ Bybit ошибка API ({category}): {ret_msg}")
                continue # Пробуем следующую категорию

            candles = data.get("result", {}).get("list", [])
            
            print(f"📡 Получено свечей ({category}): {len(candles)}")

            if candles:
                # Успех! Данные есть.
                # Структура свечи: [time, open, high, low, close, volume]
                # Берем цену закрытия (индекс 4)
                close_prices = [float(candle) for candle in candles]
                print(f"✅ Данные успешно получены из категории '{category}'.")
                return np.array(close_prices)
            else:
                print(f"⚠️ В категории '{category}' список свечей пуст. Пробуем другую категорию...")
                
        except Exception as e:
            print(f"❌ Ошибка при запросе ({category}): {e}")
            continue

    print("❌ Не удалось получить данные ни из одной категории.")
    return np.array([])

def calculate_sma(prices, window_size=20):
    if len(prices) < window_size:
        return np.array([])
    weights = np.ones(window_size) / window_size
    return np.convolve(prices, weights, mode='valid')
