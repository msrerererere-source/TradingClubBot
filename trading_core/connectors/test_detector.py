from trading_core.detectors.liquidity_sweep import LiquiditySweepDetector

def run_test():
    print("🚀 Запуск теста детектора ликвидности...\n")
    
    # 1. Инициализируем детектор для пары BTCUSDT
    # Порог установлен на 1.5x (то есть если объём в 1.5 раза выше среднего — это алерт)
    detector = LiquiditySweepDetector(symbol="BTCUSDT", threshold_volume=1.5)
    
    # 2. Тестовые данные
    current_volume = 100.0   # Текущий объём сделки
    avg_volume = 40.0        # Средний объём за период (например, за 5 минут)
    price = 65000.0          # Текущая цена
    
    print(f"📊 Данные для теста:")
    print(f"   Символ: {detector.symbol}")
    print(f"   Порог срабатывания: {detector.threshold_volume}x")
    print(f"   Текущий объём: {current_volume}")
    print(f"   Средний объём: {avg_volume}")
    print(f"   Цена: {price}\n")
    
    # 3. Проверка на аномалию
    is_anomaly = detector.check_anomaly(current_volume, avg_volume)
    
    if is_anomaly:
        print("✅ Условие выполнено! Объём превысил порог.")
        alert_message = detector.generate_alert(price, current_volume)
        print("\n📢 Сгенерированный алерт:")
        print(alert_message)
    else:
        print("❌ Аномалий не найдено. Объём в пределах нормы.")

if __name__ == "__main__":
    run_test()
