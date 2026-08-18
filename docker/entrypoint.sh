#!/bin/sh
set -e

echo "Генерация config.ini из переменных окружения..."

cat <<EOF > /app/config.ini
[matrix]
matrix_server = ${MATRIX_SERVER:-https://matrix.org}
matrix_login = ${MATRIX_LOGIN}
matrix_passwd = ${MATRIX_PASSWORD:-}
matrix_token = ${MATRIX_TOKEN:-}
matrix_device_id = ${MATRIX_DEVICE_ID:-TOMATO_BOT}
session_store_path = /var/spool/matrix_bot/session.json

[storage]
data_file = /var/spool/matrix_bot/data.json

[logging]
log_path = /var/log/matrix_bot/matrix_tomato_reminder_bot.log
debug = ${DEBUG_MODE:-no}
log_backup_count = 30
log_backup_when = midnight
EOF

echo "Конфигурация создана. Запуск бота..."
exec python bot.py /app/config.ini