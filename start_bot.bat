@echo off
chcp 65001 >nul
echo ==========================================
echo   Запуск Crypto Dashboard...
echo ==========================================
echo.
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Ошибка! Проверьте, установлен ли Python и зависимости (pip install -r requirements.txt)
    pause
) else (
    pause
)
