import asyncio
import aiohttp
import platform
from colorama import Fore, Style, init
from utils.helpers import fetch_symbols, fetch_klines, analyze_pair

init(autoreset=True)

# === НАСТРОЙКИ ===
CATEGORY = "linear"
SELECTED_TIMEFRAME = 30      # 30 или 60
SCAN_INTERVAL_SECONDS = 60
MAX_PAIRS_TO_CHECK = 15
# =================

LIQUID_COINS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "TON", "AVAX",
    "LINK", "MATIC", "DOT", "ADA", "BNB", "LTC", "TRX", "ATOM"
]

def beep():
    try:
        if platform.system() == "Windows":
            import winsound
            winsound.Beep(1000, 300)
            winsound.Beep(1500, 200)
        else:
            print('\a', end='', flush=True)
    except Exception:
        print('\a', end='', flush=True)

async def filter_liquid_symbols(all_symbols: list) -> list:
    filtered = []
    for sym in all_symbols:
        if any(sym.startswith(coin) for coin in LIQUID_COINS):
            filtered.append(sym)
            if len(filtered) >= MAX_PAIRS_TO_CHECK:
                break
    return filtered

async def scan_market(session: aiohttp.ClientSession, symbols: list):
    semaphore = asyncio.Semaphore(5)
    results = []

    async def process_symbol(sym):
        async with semaphore:
            df = await fetch_klines(session, sym, SELECTED_TIMEFRAME, limit=100, category=CATEGORY)
            if df is not None and not df.empty:
                res = analyze_pair(df, sym, SELECTED_TIMEFRAME)
                results.append(res)

    tasks = [process_symbol(sym) for sym in symbols]
    await asyncio.gather(*tasks)

    # Разделяем по категориям
    signals = []
    false_breakouts = []
    flats = []
    trend_waits = []

    for r in results:
        s = r["status"]
        if s in ("SIGNAL_LONG", "SIGNAL_SHORT", "BREAKOUT_LONG", "BREAKOUT_SHORT"):
            signals.append(r)
        elif s == "FALSE_BREAKOUT":
            false_breakouts.append(r)
        elif s == "FLAT_WAIT":
            flats.append(r)
        elif s == "TREND_WAIT":
            trend_waits.append(r)

    # Перевод минут в текст
    tf_text = f"{SELECTED_TIMEFRAME} мин" if SELECTED_TIMEFRAME < 60 else f"{SELECTED_TIMEFRAME // 60} час"

    print("\n" + "=" * 90)
    print(f"{Fore.WHITE}{Style.BRIGHT}📊 ОБЗОР РЫНКА Bybit | Время таймфрейма: {tf_text} | {len(results)} пар{Style.RESET_ALL}")
    print("=" * 90)

    # --- 1. СИГНАЛЫ ---
    if signals:
        beep()
        print(f"\n{Fore.WHITE}{Style.BRIGHT}{'='*60}")
        print(f"  🔔 СИГНАЛЫ — МОЖНО ЗАХОДИТЬ")
        print(f"{'='*60}{Style.RESET_ALL}")

        for r in signals:
            hold_min = r["holding_time_minutes"]
            if hold_min >= 60:
                exp_text = f"{hold_min // 60} час" if hold_min % 60 == 0 else f"{hold_min // 60} час {hold_min % 60} мин"
            else:
                exp_text = f"{hold_min} мин"

            if r["recommendation"] == "LONG":
                color = Fore.GREEN
                arrow = "⬆️⬆️⬆️  ВХОДИ ВВЕРХ (LONG)"
            else:
                color = Fore.RED
                arrow = "⬇️⬇️⬇️  ВХОДИ ВНИЗ (SHORT)"

            # Функция для красивого вывода цен (без лишних нулей)
            def fmt_price(p):
                if p is None:
                    return "—"
                # Округляем до 4 знаков, потом убираем нули справа
                s = f"{p:.4f}".rstrip('0').rstrip('.')
                return s

            entry_str = fmt_price(r['entry'])
            sl_str = fmt_price(r['stop_loss'])
            tp_str = fmt_price(r['take_profit'])

            print(f"\n{color}{Style.BRIGHT}  {arrow}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Пара:{Style.RESET_ALL}            {color}{Style.BRIGHT}{r['symbol']}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Статус:{Style.RESET_ALL}          {r['status_message']}")
            print(f"  {Fore.WHITE}Вход по цене:{Style.RESET_ALL}    {color}{entry_str}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Паттерны:{Style.RESET_ALL}        {', '.join(r['patterns']) if r['patterns'] else '—'}")
            print(f"  {Fore.WHITE}Стоп-Лосс:{Style.RESET_ALL}       {Fore.RED}{Style.BRIGHT}{sl_str}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Тейк-Профит:{Style.RESET_ALL}     {Fore.GREEN}{Style.BRIGHT}{tp_str}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Время экспирации:{Style.RESET_ALL} {Fore.YELLOW}{Style.BRIGHT}{exp_text}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Время таймфрейма:{Style.RESET_ALL} {Fore.YELLOW}{Style.BRIGHT}{tf_text}{Style.RESET_ALL}")
            print(f"  {color}{'─'*55}{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}  ⏳ Сигналов нет. Жди.{Style.RESET_ALL}")

    # --- 2. ЛОЖНЫЕ ПРОБОИ ---
    if false_breakouts:
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}  ⚠️  ЛОЖНЫЕ ПРОБОИ — ЖДИ{Style.RESET_ALL}")
        for r in false_breakouts:
            price_str = f"{r['last_price']:.4f}".rstrip('0').rstrip('.')
            print(f"  {Fore.MAGENTA}  • {r['symbol']}: {r['status_message']} "
                  f"(цена: {price_str}){Style.RESET_ALL}")

    # --- 3. ФЛЭТ ---
    if flats:
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}  💤 ФЛЭТ — ЖДИ ПРОБОЙ{Style.RESET_ALL}")
        for r in flats:
            price_str = f"{r['last_price']:.4f}".rstrip('0').rstrip('.')
            print(f"  {Fore.YELLOW}  • {r['symbol']}: Флет. Жди пробой. "
                  f"(цена: {price_str}){Style.RESET_ALL}")

    # --- 4. ТРЕНД БЕЗ ПОДТВЕРЖДЕНИЯ ---
    if trend_waits:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}  📈 ТРЕНД — ЖДИ ПОДТВЕРЖДЕНИЕ{Style.RESET_ALL}")
        for r in trend_waits:
            price_str = f"{r['last_price']:.4f}".rstrip('0').rstrip('.')
            print(f"  {Fore.CYAN}  • {r['symbol']}: {r['status_message']} "
                  f"(цена: {price_str}){Style.RESET_ALL}")

    print(f"\n{Fore.WHITE}{'='*90}{Style.RESET_ALL}")

async def main():
    print(f"{Fore.CYAN}{Style.BRIGHT}")
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   🚀 Bybit Trading Assistant v8.1 — Real-Time         ║")
    print("  ║   🔔 Звуковой сигнал при появлении сетапа              ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print(f"{Style.RESET_ALL}")
    print(f"  ⏳ Время таймфрейма: {SELECTED_TIMEFRAME} мин")
    print(f"  🔄 Сканирование каждые: {SCAN_INTERVAL_SECONDS} сек")
    print(f"  💡 Бот анализирует. Ордера НЕ отправляет!")
    print()

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                print(f"{Fore.CYAN}📋 Загрузка пар с Bybit...{Style.RESET_ALL}")
                all_symbols = await fetch_symbols(session, category=CATEGORY)

                if not all_symbols:
                    print("❌ Не удалось получить пары. Повтор через 60 сек.")
                    await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                    continue

                symbols_to_check = await filter_liquid_symbols(all_symbols)
                print(f"✅ Проверяем {len(symbols_to_check)} пар...")

                await scan_market(session, symbols_to_check)

                print(f"\n{Fore.BLUE}⏳ Следующее сканирование через {SCAN_INTERVAL_SECONDS} сек...{Style.RESET_ALL}")
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)

            except Exception as e:
                print(f"{Fore.RED}❌ Ошибка: {e}{Style.RESET_ALL}")
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())
