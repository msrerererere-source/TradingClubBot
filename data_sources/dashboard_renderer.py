# dashboard_renderer.py
import os
from datetime import datetime

def generate_html(state: dict, path: str):
    trend = state.get("last_trend", "UNKNOWN")
    price = state.get("prices",)[-1]
    sma = state.get("sma",)[-1]
    rsi = state.get("rsi",)[-1]
    whale_count = len(state.get("whale_trades", []))
    last_update = datetime.fromtimestamp(state.get("last_update", 0)).strftime("%Y-%m-%d %H:%M:%S")

    # Цвета для тренда
    if trend == "UP":
        trend_color = "#2ecc71"
        trend_icon = "🟢"
    elif trend == "DOWN":
        trend_color = "#e74c3c"
        trend_icon = "🔴"
    else:
        trend_color = "#f39c12"
        trend_icon = "⚪"

    # RSI цвет
    if rsi > 70:
        rsi_color = "#e74c3c"
    elif rsi < 30:
        rsi_color = "#2ecc71"
    else:
        rsi_color = "#34495e"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Bybit Dashboard</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f4f6f8; padding: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 15px; }}
            .trend-big {{ font-size: 28px; font-weight: bold; color: {trend_color}; }}
            .metric {{ font-size: 18px; margin: 8px 0; }}
            .label {{ color: #7f8c8d; }}
            .last-update {{ font-size: 13px; color: #95a5a6; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <h1>Bybit Dashboard — {os.environ.get("SYMBOL", "BTCUSDT")}</h1>
        <div class="card">
            <div class="trend-big">{trend_icon} Тренд: {trend.upper()}</div>
            <div class="metric"><span class="label">Цена:</span> {price:.2f}</div>
            <div class="metric"><span class="label">SMA:</span> {sma:.2f}</div>
            <div class="metric"><span class="label">RSI:</span> <span style="color:{rsi_color}">{rsi:.2f}</span></div>
            <div class="metric"><span class="label">Киты (сделки):</span> {whale_count}</div>
            <div class="last-update">Обновлено: {last_update}</div>
        </div>
    </body>
    </html>
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
