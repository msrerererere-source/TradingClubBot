import asyncio
import aiohttp
import pandas as pd
import pandas_ta as ta
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Dict, Optional, List, Literal

BYBIT_API_URL = "https://api.bybit.com"

# --- API ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_symbols(session: aiohttp.ClientSession, category: str = "linear") -> List[str]:
    url = f"{BYBIT_API_URL}/v5/market/instruments-info"
    params = {"category": category}
    try:
        async with session.get(url, params=params, timeout=10) as resp:
            data = await resp.json()
            if data.get("retCode") == 0:
                return [item["symbol"] for item in data["result"]["list"]]
            return []
    except Exception as e:
        print(f"Error symbols: {e}")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_klines(session: aiohttp.ClientSession, symbol: str, interval: int, limit: int = 100, category: str = "linear") -> Optional[pd.DataFrame]:
    url = f"{BYBIT_API_URL}/v5/market/kline"
    params = {"category": category, "symbol": symbol, "interval": interval, "limit": limit}
    try:
        async with session.get(url, params=params, timeout=15) as resp:
            data = await resp.json()
            if data.get("retCode") == 0 and data.get("result"):
                df = pd.DataFrame(data["result"]["data"])
                if len(df.columns) < 6:
                    return None
                cols = ["start_time", "open", "high", "low", "close", "volume"]
                df = df.iloc[:, :6]
                df.columns = cols
                df["open_time"] = pd.to_datetime(df["start_time"], unit='ms')
                df.set_index("open_time", inplace=True)
                numeric_cols = ["open", "high", "low", "close", "volume"]
                df[numeric_cols] = df[numeric_cols].astype(float)
                return df
            return None
    except Exception as e:
        print(f"Error klines {symbol}: {e}")
        return None

# --- АНАЛИЗ ---

def get_market_phase(df: pd.DataFrame, timeframe_min: int) -> str:
    if len(df) < 50:
        return "consolidation"
    fast_len = 20 if timeframe_min >= 60 else 9
    slow_len = 50 if timeframe_min >= 60 else 21
    ema_fast = ta.ema(df['close'], length=fast_len)
    ema_slow = ta.ema(df['close'], length=slow_len)
    bb = ta.bbands(df['close'], length=20)
    bandwidth = (bb['BBU'] - bb['BBL']) / bb['BBM']
    last_bw = bandwidth.iloc[-1]
    flat_threshold = 0.01 if timeframe_min >= 60 else 0.015
    if last_bw < flat_threshold:
        return "consolidation"
    trend_mult = 1.005 if timeframe_min >= 60 else 1.002
    if ema_fast.iloc[-1] > ema_slow.iloc[-1] * trend_mult:
        return "uptrend"
    elif ema_fast.iloc[-1] < ema_slow.iloc[-1] / trend_mult:
        return "downtrend"
    else:
        return "consolidation"


def detect_breakout(df: pd.DataFrame) -> Optional[str]:
    """Определяет пробой границ Боллинджера с подтверждением объёмом."""
    if len(df) < 30:
        return None
    bb = ta.bbands(df['close'], length=20)
    upper = bb['BBU'].iloc[-1]
    lower = bb['BBL'].iloc[-1]
    last = df.iloc[-1]
    avg_volume = df['volume'].rolling(20).mean().iloc[-1]

    if pd.isna(avg_volume) or avg_volume == 0:
        return None

    # Пробой вверх: закрытие выше верхней полосы + объём выше среднего
    if last['close'] > upper and last['volume'] > avg_volume * 1.5:
        return "breakout_up"
    # Пробой вниз: закрытие ниже нижней полосы + объём выше среднего
    if last['close'] < lower and last['volume'] > avg_volume * 1.5:
        return "breakout_down"
    return None


def detect_patterns_and_false_breakouts(df: pd.DataFrame, timeframe_min: int) -> List[str]:
    patterns = []
    highs = df['high']
    lows = df['low']
    closes = df['close']
    last_candle = df.iloc[-1]

    # --- Ложные пробои ---
    lookback = 20 if timeframe_min >= 60 else 10
    prev_high = highs.iloc[-lookback:-1].max()
    if last_candle['high'] > prev_high * 1.005 and last_candle['close'] < prev_high:
        patterns.append("False Breakout Up")
    prev_low = lows.iloc[-lookback:-1].min()
    if last_candle['low'] < prev_low * 0.995 and last_candle['close'] > prev_low:
        patterns.append("False Breakout Down")

    # --- Ретест ---
    if len(df) > 2:
        prev_candle = df.iloc[-2]
        impulse = abs(prev_candle['high'] - prev_candle['low'])
        avg_range = (df['high'] - df['low']).rolling(window=20).mean().iloc[-1]
        if impulse > avg_range * 1.5:
            if abs(last_candle['close'] - prev_candle['open']) < impulse * 0.1:
                patterns.append("Retest")

    # --- Double Top ---
    peaks = highs[(highs.shift(1) < highs) & (highs.shift(-1) < highs)]
    if len(peaks) >= 2:
        top1, top2 = peaks.iloc[-2], peaks.iloc[-1]
        tol = 0.01 if timeframe_min >= 60 else 0.015
        if abs(top1 - top2) / top1 < tol:
            valley = highs.loc[peaks.index[-2]:peaks.index[-1]].min()
            if valley < top1 * 0.96:
                patterns.append("Double Top")

    # --- Double Bottom ---
    valleys = lows[(lows.shift(1) > lows) & (lows.shift(-1) > lows)]
    if len(valleys) >= 2:
        bot1, bot2 = valleys.iloc[-2], valleys.iloc[-1]
        if abs(bot1 - bot2) / bot1 < tol:
            peak = lows.loc[valleys.index[-2]:valleys.index[-1]].max()
            if peak > bot1 * 1.04:
                patterns.append("Double Bottom")

    # --- Pin Bar ---
    body = abs(last_candle['close'] - last_candle['open'])
    range_ = last_candle['high'] - last_candle['low']
    if range_ > 0:
        upper_shadow = last_candle['high'] - max(last_candle['close'], last_candle['open'])
        lower_shadow = min(last_candle['close'], last_candle['open']) - last_candle['low']
        body_thresh = 0.3 if timeframe_min >= 60 else 0.25
        if body < range_ * body_thresh:
            if lower_shadow > body * 2 and last_candle['close'] > last_candle['open']:
                patterns.append("Bullish Pin Bar")
            elif upper_shadow > body * 2 and last_candle['close'] < last_candle['open']:
                patterns.append("Bearish Pin Bar")

    return patterns


def calculate_sl_tp(df: pd.DataFrame, entry_price: float, side: str, timeframe_min: int) -> Dict:
    if len(df) < 14:
        return {"sl": 0, "tp": 0, "hold_min": 0, "candles": 0}
    atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
    if pd.isna(atr) or atr == 0:
        return {"sl": 0, "tp": 0, "hold_min": 0, "candles": 0}
    sl_dist = atr * 1.5
    tp_dist = atr * 2.5
    if side == "long":
        sl = entry_price - sl_dist
        tp = entry_price + tp_dist
    else:
        sl = entry_price + sl_dist
        tp = entry_price - tp_dist
    candles = 2
    hold_min = candles * timeframe_min
    return {"sl": sl, "tp": tp, "hold_min": hold_min, "candles": candles}


def analyze_pair(df: pd.DataFrame, symbol: str, timeframe_min: int) -> Dict:
    """
    Полный анализ пары. Возвращает статус для каждой пары:
    - SIGNAL_LONG / SIGNAL_SHORT  → можно заходить
    - BREAKOUT_LONG / BREAKOUT_SHORT → пробой, можно заходить
    - FALSE_BREAKOUT → ложный пробой, жди
    - FLAT_WAIT → флет, жди пробой
    - TREND_WAIT → тренд есть, но нет подтверждения, жди
    """
    phase = get_market_phase(df, timeframe_min)
    patterns = detect_patterns_and_false_breakouts(df, timeframe_min)
    breakout = detect_breakout(df)
    last_price = df['close'].iloc[-1]

    result = {
        "symbol": symbol,
        "phase": phase,
        "patterns": patterns,
        "recommendation": "NEUTRAL",
        "status": "",
        "status_message": "",
        "entry": None,
        "stop_loss": None,
        "take_profit": None,
        "holding_time_minutes": 0,
        "reason": "",
        "last_price": last_price
    }

    has_false_breakout_up = "False Breakout Up" in patterns
    has_false_breakout_down = "False Breakout Down" in patterns
    has_bullish = "Bullish Pin Bar" in patterns or "Double Bottom" in patterns
    has_bearish = "Bearish Pin Bar" in patterns or "Double Top" in patterns

    # --- КОНСОЛИДАЦИЯ (ФЛЭТ) ---
    if phase == "consolidation":
        bb = ta.bbands(df['close'], length=20)
        lower_band = bb['BBL'].iloc[-1]
        upper_band = bb['BBU'].iloc[-1]

        # Ложный пробой — жди
        if has_false_breakout_up:
            result["status"] = "FALSE_BREAKOUT"
            result["status_message"] = "Ложный пробой вверх. Жди."
            return result
        if has_false_breakout_down:
            result["status"] = "FALSE_BREAKOUT"
            result["status_message"] = "Ложный пробой вниз. Жди."
            return result

        # Пробой с объёмом — можно заходить
        if breakout == "breakout_up":
            result["status"] = "BREAKOUT_LONG"
            result["status_message"] = "Пробой вверх! Заходи LONG"
            result["recommendation"] = "LONG"
            result["entry"] = last_price
            result["reason"] = "Breakout above BB with volume"
            levels = calculate_sl_tp(df, last_price, "long", timeframe_min)
            result["stop_loss"] = levels["sl"]
            result["take_profit"] = levels["tp"]
            result["holding_time_minutes"] = levels["hold_min"]
            return result
        if breakout == "breakout_down":
            result["status"] = "BREAKOUT_SHORT"
            result["status_message"] = "Пробой вниз! Заходи SHORT"
            result["recommendation"] = "SHORT"
            result["entry"] = last_price
            result["reason"] = "Breakout below BB with volume"
            levels = calculate_sl_tp(df, last_price, "short", timeframe_min)
            result["stop_loss"] = levels["sl"]
            result["take_profit"] = levels["tp"]
            result["holding_time_minutes"] = levels["hold_min"]
            return result

        # Отскок от границы Боллинджера + паттерн — сигнал
        if last_price <= lower_band * 1.01 and has_bullish:
            result["status"] = "SIGNAL_LONG"
            result["status_message"] = "Отскок от нижней границы + паттерн. Заходи LONG"
            result["recommendation"] = "LONG"
            result["entry"] = last_price
            result["reason"] = f"Bounce from Lower BB + {patterns}"
            levels = calculate_sl_tp(df, last_price, "long", timeframe_min)
            result["stop_loss"] = levels["sl"]
            result["take_profit"] = levels["tp"]
            result["holding_time_minutes"] = levels["hold_min"]
            return result
        if last_price >= upper_band * 0.99 and has_bearish:
            result["status"] = "SIGNAL_SHORT"
            result["status_message"] = "Отскок от верхней границы + паттерн. Заходи SHORT"
            result["recommendation"] = "SHORT"
            result["entry"] = last_price
            result["reason"] = f"Rejection from Upper BB + {patterns}"
            levels = calculate_sl_tp(df, last_price, "short", timeframe_min)
            result["stop_loss"] = levels["sl"]
            result["take_profit"] = levels["tp"]
            result["holding_time_minutes"] = levels["hold_min"]
            return result

        # Просто флет — жди
        result["status"] = "FLAT_WAIT"
        result["status_message"] = "Флет. Жди пробой."
        return result

    # --- ВОСХОДЯЩИЙ ТРЕНД ---
    if phase == "uptrend":
        if has_bullish or has_false_breakout_down:
            result["status"] = "SIGNAL_LONG"
            result["status_message"] = "Восходящий тренд + паттерн. Заходи LONG"
            result["recommendation"] = "LONG"
            result["entry"] = last_price
            result["reason"] = f"Uptrend + {patterns}"
            levels = calculate_sl_tp(df, last_price, "long", timeframe_min)
            result["stop_loss"] = levels["sl"]
            result["take_profit"] = levels["tp"]
            result["holding_time_minutes"] = levels["hold_min"]
            return result
        result["status"] = "TREND_WAIT"
        result["status_message"] = "Восходящий тренд. Жди подтверждение (паттерн)."
        return result

    # --- НИСХОДЯЩИЙ ТРЕНД ---
    if phase == "downtrend":
        if has_bearish or has_false_breakout_up:
            result["status"] = "SIGNAL_SHORT"
            result["status_message"] = "Нисходящий тренд + паттерн. Заходи SHORT"
            result["recommendation"] = "SHORT"
            result["entry"] = last_price
            result["reason"] = f"Downtrend + {patterns}"
            levels = calculate_sl_tp(df, last_price, "short", timeframe_min)
            result["stop_loss"] = levels["sl"]
            result["take_profit"] = levels["tp"]
            result["holding_time_minutes"] = levels["hold_min"]
            return result
        result["status"] = "TREND_WAIT"
        result["status_message"] = "Нисходящий тренд. Жди подтверждение (паттерн)."
        return result

    result["status"] = "FLAT_WAIT"
    result["status_message"] = "Неопределённое состояние. Жди."
    return result 