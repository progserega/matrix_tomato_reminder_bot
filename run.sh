#!/bin/bash
index=0
while /bin/true
do
  /opt/matrix_tomato_reminder_bot/matrix_tomato_reminder_bot.py &> /var/log/matrix/matrix_tomato_reminder_bot_runner_iter_$index.log
  index=`expr $index + 1`
done

