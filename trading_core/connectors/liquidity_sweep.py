class LiquiditySweepDetector:
    """Детектор ликвидности для поиска свипов."""

    def __init__(self, symbol, threshold_volume):
        # symbol — торговая пара (например, 'BTCUSDT')
        # threshold_volume — порог срабатывания (например, 1.5 для 1.5x от среднего объёма)
        self.symbol = symbol
        self.threshold_volume = threshold_volume

    def check_anomaly(self, current_volume, avg_volume):
        """Проверяет, превышен ли порог объёма."""
        if avg_volume == 0:
            return False
        return current_volume > (avg_volume * self.threshold_volume)

    def generate_alert(self, price, current_volume):
        """Генерирует текст алерта при обнаружении аномалии."""
        return (f"🚨 АЛЕРТ LIQUIDITY SWEEP!\n"
                f"Пара: {self.symbol}\n"
                f"Цена: {price}\n"
                f"Объём: {current_volume}\n"
                f"Статус: Превышен порог в {self.threshold_volume}x")
