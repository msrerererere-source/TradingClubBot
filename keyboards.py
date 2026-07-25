from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_vip_keyboard():
    builder = InlineKeyboardBuilder()
    
    # Создаём кнопку с нужным callback_data
    builder.button(
        text="📈 VIP Сигналы", 
        callback_data="vip_signals"
    )
    
    # Настраиваем вид клавиатуры (чтобы кнопка была по центру или в ряд)
    builder.adjust(1)
    
    return builder.as_markup()
