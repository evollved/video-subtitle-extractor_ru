#!/bin/bash

# Упрощенная версия скрипта для запуска Python скрипта

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR"

PYTHON_SCRIPT="main_gui.py"  # Замените на имя вашего скрипта

# Проверки
[ ! -f "$PYTHON_SCRIPT" ] && echo "Ошибка: $PYTHON_SCRIPT не найден" && exit 1
! command -v python3 &> /dev/null && echo "Ошибка: Python3 не найден" && exit 1

# Создание/активация venv
[ ! -d "venv" ] && echo "Создание venv..." && python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
[ -f "requirements.txt" ] && {
    pip install --upgrade pip
    pip install -r requirements.txt
}

# Запуск скрипта
python "$PYTHON_SCRIPT"
EXIT_CODE=$?

deactivate
exit $EXIT_CODE