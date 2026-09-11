import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Union

class Analyzer:
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Заполняем NaN значениями по умолчанию (если данных мало)
        rsi = rsi.fillna(50.0) 
        return float(rsi.iloc[-1])

    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> float:
        ema = prices.ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1])

    @staticmethod
    def analyze_market(candles: List[Union[List, Dict]]) -> Optional[Dict[str, Any]]:
        if not candles:
            print("[WARNING] Нет данных для анализа (пустой список свечей).")
            return None
        
        # Требуем минимум 50 свечей для надежного EMA/RSI
        if len(candles) < 50:
            print(f"[WARNING] Мало данных для анализа: {len(candles)} свечей. Требуется минимум 50.")
            return None

        try:
            # Нормализация данных
            if isinstance(candles, dict):
                df = pd.DataFrame(candles)
                required_cols = {'open', 'high', 'low', 'close', 'volume'}
                if not required_cols.issubset(df.columns):
                    print("[ERROR] В свечах отсутствуют необходимые колонки.")
                    return None
            else:
                # Bybit отдает списки: [time, open, high, low, close, volume]
                df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

            # Проверка на NaN и приведение к float
            if df['close'].isnull().any():
                print("[WARNING] Обнаружены пустые значения цен (NaN). Пропускаем анализ.")
                return None
            
            close_prices = df['close'].astype(float)

            # Расчет индикаторов
            rsi = Analyzer.calculate_rsi(close_prices, 14)
            ema_short = Analyzer.calculate_ema(close_prices, 9)
            ema_long = Analyzer.calculate_ema(close_prices, 21)
            current_price = float(close_prices.iloc[-1])

            # Логика сигналов
            signal = "HOLD"
            reason = "Нет четкого сигнала"
            
            # BUY: Цена выше обеих EMA, RSI не в зоне перекупленности
            if current_price > ema_short > ema_long and rsi < 70:
                signal = "BUY"
                reason = "Цена выше EMA 9 и 21, тренд восходящий, RSI < 70"
            
            # SELL: Цена ниже обеих EMA, RSI не в зоне перепроданности
            elif current_price < ema_short < ema_long and rsi > 30:
                signal = "SELL"
                reason = "Цена ниже EMA 9 и 21, тренд нисходящий, RSI > 30"

            return {
                "signal": signal,
                "reason": reason,
                "metrics": {
                    "current_price": current_price,
                    "ema_9": ema_short,
                    "ema_21": ema_long,
                    "rsi_14": rsi
                }
            }
        except Exception as e:
            print(f"[CRITICAL ERROR] Критическая ошибка в Analyzer: {e}")
            return None
