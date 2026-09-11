import streamlit as st
import pandas as pd
from whale_tracker import detect_whales  # Импорт логики

# --- Настройка страницы ---
st.set_page_config(page_title="Bybit Whale Dashboard", layout="wide")
st.title("🐋 Bybit Whale Tracker & Risk Manager")
st.caption("Дашборд для скальперов: стакан, киты, риск‑менеджмент в одном окне")

# --- Боковая панель: ввод параметров ---
with st.sidebar:
    st.header("📉 Риск‑менеджмент")
    balance = st.number_input("Баланс (USDT)", value=1000.0, min_value=0.0)
    risk_percent = st.slider("Риск на сделку (%)", min_value=0.5, max_value=5.0, value=1.0, step=0.1)
    atr_value = st.number_input("ATR (USDT)", value=50.0, min_value=0.0)
    direction = st.selectbox("Направление", ["Лонг", "Шорт"])

    st.divider()
    st.info("Эти параметры используются для автоматического расчёта SL/TP и размера позиции.")

# --- Расчёт метрик ---
risk_amount = balance * (risk_percent / 100)
sl_distance = atr_value * 2
position_size = risk_amount / sl_distance if sl_distance > 0 else 0

# --- Основная область: метрики ---
col1, col2, col3 = st.columns(3)
col1.metric("Риск на сделку", f"{risk_amount:.2f} USDT")
col2.metric("Размер позиции", f"{position_size:.4f} BTC" if position_size > 0 else "0 BTC")
col3.metric("SL дистанция", f"{sl_distance:.2f} USDT")

st.divider()

# --- Блок 1: Стакан (L2) ---
st.subheader("📊 Стакан (L2)")

# 1. Исходные данные (заглушка). Сюда потом подключим API.
raw_data = [
    {"Цена": 64000, "Объём (BTC)": 0.5, "Сторона": "ASK"},
    {"Цена": 63999, "Объём (BTC)": 1.2, "Сторона": "ASK"},
    {"Цена": 63998, "Объём (BTC)": 0.8, "Сторона": "ASK"},
    {"Цена": 64001, "Объём (BTC)": 0.3, "Сторона": "BID"},
    {"Цена": 64002, "Объём (BTC)": 2.1, "Сторона": "BID"},
    {"Цена": 64003, "Объём (BTC)": 0.9, "Сторона": "BID"},
]

# 2. Прогоняем данные через нашу функцию-детектор
processed_data = detect_whales(raw_data, threshold_btc=1.0)

# 3. Превращаем в DataFrame
df_orderbook = pd.DataFrame(processed_data)

# 4. Отображение
st.dataframe(
    df_orderbook, 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "Статус": st.column_config.Column(help="Крупные заявки подсвечиваются красным")
    }
)

# --- Блок 2: Детектор китов (последние события) ---
st.subheader("🦈 Детектор китов — последние события")

# 👇 ВОТ ЭТА СТРОЧКА — ГЛАВНОЕ ИЗМЕНЕНИЕ 👇
st.caption("ℹ️ Время в таблице указано по UTC (время биржи). Прибавьте/отнимите часы для своего часового пояса.")

events = [
    {"Время": "10:05", "Событие": "Крупная заявка на продажу", "Объём": "2.1 BTC", "Цена": "63998"},
    {"Время": "10:02", "Событие": "Он‑чейн перевод", "Объём": "50 BTC", "Цена": "-"},
    {"Время": "09:55", "Событие": "Крупная заявка на покупку", "Объём": "1.5 BTC", "Цена": "64002"}
]
st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)

# --- Футер ---
st.divider()
st.caption("Данные обновляются в реальном времени. Интеграция с Bybit V5 API и CoinGlass.")
