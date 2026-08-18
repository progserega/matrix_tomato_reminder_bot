#!/bin/bash
# Создаем директории
sudo mkdir -p /opt/matrix_tomato_reminder_bot/data
sudo mkdir -p /opt/matrix_tomato_reminder_bot/logs

# Устанавливаем владельца (обычно root или текущий пользователь)
sudo chown -R $USER:$USER /opt/matrix_tomato_reminder_bot

# Или, если контейнер запускается от root:
sudo chmod 755 /opt/matrix_tomato_reminder_bot/data
sudo chmod 755 /opt/matrix_tomato_reminder_bot/logs
docker-compose down
docker-compose up -d --build
