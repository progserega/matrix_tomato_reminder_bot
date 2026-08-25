#!/bin/sh
set -e

echo "Генерация config.ini из переменных окружения..."

mkdir /app/config

cat <<EOF > /app/config/config.ini
[matrix]
matrix_server = ${MATRIX_SERVER:-https://matrix.org}
matrix_login = ${MATRIX_LOGIN}
matrix_passwd = ${MATRIX_PASSWORD:-}
matrix_token = ${MATRIX_TOKEN:-}
matrix_device_id = ${MATRIX_DEVICE_ID:-TOMATO_BOT}
session_store_path = /var/spool/matrix_bot/session.json

[storage]
data_file = /var/spool/matrix_bot/data.json

[time_presets]
morning = 7:00
on_work = 8:00
lunch_break = 12:00
after_lunch = 13:00
after_work = 17:00
evening = 21:00

[invites]
# for disable some options - live in empty.
# invite rules - who can invite this bot (mxid users and its domain) - this
# options override all other options in this block:
allow_users = ${ALLOW_USERS}
# allow whole domain (or all domains: *):
allow_domains = ${ALLOW_DOMAINS}
# disable some users. Also from allowed domains:
deny_users = ${DENY_USERS}
# can disable some domains if allow was by mask '*':
deny_domains = ${DENY_DOMAINS}

[logging]
log_path = /var/log/matrix_bot/matrix_tomato_reminder_bot.log
debug = ${DEBUG_MODE:-no}
log_backup_count = 30
log_backup_when = midnight
EOF

echo "Конфигурация создана. Запуск бота..."
exec python bot.py /app/config/config.ini
