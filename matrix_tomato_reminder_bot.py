#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# A simple chat client for matrix.
# This sample will allow you to connect to a room, and send/recieve messages.
# Args: host:port username password room
# Error Codes:
# 1 - Unknown problem has occured
# 2 - Could not find the server.
# 3 - Bad URL Format.
# 4 - Bad username/password.
# 11 - Wrong room format.
# 12 - Couldn't find room.

import sys
import logging
import time
import json
import os
import pickle
import re
import threading

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import sendemail as mail
import config as conf

client = None
log = None
data={}
lock = None


def save_data(data):
  global log
  log.debug("data_file:%s"%conf.data_file)
  try:
    data_file=open(conf.data_file,"wb")
  except:
    log.error("open(%s) for writing"%conf.data_file)
    return False
    
  try:
    pickle.dump(data,data_file)
    data_file.close()
  except:
    log.error("pickle.dump to '%s'"%conf.data_file)
    return False
  return True

def load_data():
  global log
  tmp_data_file=conf.data_file
  reset=False
  if os.path.exists(tmp_data_file):
    log.debug("Загружаем файл промежуточных данных: '%s'" % tmp_data_file)
    data_file = open(tmp_data_file,'rb')
    try:
      data=pickle.load(data_file)
      data_file.close()
      log.debug("Загрузили файл промежуточных данных: '%s'" % tmp_data_file)
    except:
      log.warning("Битый файл сессии - сброс")
      reset=True
    if not "users" in data:
      log.warning("Битый файл сессии - сброс")
      reset=True
  else:
    log.warning("Файл промежуточных данных не существует")
    reset=True
  if reset:
    log.warning("Сброс промежуточных данных")
    data={}
    save_data(data)
  return data

def process_command(user,room,cmd):
  global client
  global log
  global data
  answer=None
  cur_data=None

  if user not in data:
    data[user]={}
  if room not in data[user]:
    data[user][room]={}
    data[user][room]["lang"]="ru"
    data[user][room]["alarms"]={}

  cur_data=data[user][room]

  
  if cmd == '!?' or cmd.lower() == '!h' or cmd.lower() == '!help':
    answer="""!repeat - повторить текущую задачу
!stop - остановить текущую задачу
!alarm время текст - напомнить в определённое время и показать текст
!напоминание время текст - напомнить в определённое время и показать текст
!ru - russian language
!en - english language
!alarms - показать текущие активные напоминания
!напоминания - показать текущие активные напоминания
"""
    return send_message(room,answer)

  # язык:
  elif cmd == '!ru':
    cur_data["lang"]="ru"
    return send_message(room,"Установил язык Русский")
  elif cmd == '!en':
    cur_data["lang"]="en"
    return send_message(room,"Set language to English")
  
  # Добавить Напоминалки:
  elif re.search('^!*alarm .*', cmd.lower()) is not None or \
    re.search('^!*напомни .*', cmd.lower()) is not None:
    return process_alarm_cmd(user,room,cmd)
  
  # Просмотреть Напоминалки:
  elif re.search('^!*alarms', cmd.lower()) is not None or \
    re.search('^!*напоминания', cmd.lower()) is not None:
    return process_alarm_list_cmd(user,room,cmd)
  
  return True


def process_alarm_list_cmd(user,room,cmd):
  global data
  global client
  global log

  cur_data=data[user][room]
  log.debug("process_alarm_cmd(%s,%s,%s)"%(user,room,cmd))
  time_now=time.time()
  num=0
  for alarm_timestamp in cur_data["alarms"]:
    if alarm_timestamp > time_now:
      num+=1
  if num==0:
    send_message(room,"На данный момент для Вас Нет актывных напоминаний")
  else:
    html="<p><strong>Я напомню Вам о следующих событиях:</strong></p>\n<ul>\n"
    for alarm_timestamp in cur_data["alarms"]:
      if alarm_timestamp > time_now:
        # Выводим только актуаальные:
        print("alarm_timestamp=",alarm_timestamp)
        print("string=",cur_data["alarms"][alarm_timestamp])
        alarm_string=time.strftime("%Y.%m.%d-%T",time.localtime(alarm_timestamp))
        html+="<li>%s: %s!</li>\n"%(alarm_string,cur_data["alarms"][alarm_timestamp])
    html+="</ul>\n<p><em>Надеюсь ничего не забыл :-)</em></p>\n"
    return send_html(room,html)

def parse_time(date_timestamp,pars,index,cur_data,cmd,room):
  log.debug("parse_time(), date_timestamp=%d, pars[index]='%s'"%(date_timestamp,pars[index]))
  if date_timestamp==0:
    date_timestamp=time.time()
  i=index
  if pars[i].lower()=='утром' or pars[i].lower()=='morning':
    alarm_time=time.strptime(conf.morning, "%H:%M")
    date_time = time.localtime(date_timestamp) 
    cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
    text_index=i+1
  elif pars[i].lower()=='в' and pars[i+1].lower()=='обед' or pars[i].lower()=='at' and pars[i+1].lower()=='lunch':
    alarm_time=time.strptime(conf.lunch_break, "%H:%M")
    date_time = time.localtime(date_timestamp) 
    cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
    text_index=i+2
  elif pars[i].lower()=='после' and pars[i+1].lower()=='работы' or pars[i].lower()=='after' and pars[i+1].lower()=='work':
    alarm_time=time.strptime(conf.after_work, "%H:%M")
    date_time = time.localtime(date_timestamp) 
    cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
    text_index=i+2
  elif pars[i].lower()=='вечером' or pars[i].lower()=='at' and pars[i+1].lower()=='evening':
    alarm_time=time.strptime(conf.evening, "%H:%M")
    date_time = time.localtime(date_timestamp) 
    cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
    if pars[i].lower()=='вечером':
      text_index=i+1
    else:
      text_index=i+2

  elif pars[i].lower()=='в' or pars[i].lower()=='at':
    time_tmp=0
    try:
      time_tmp=pars[i+1].split(':')
    except:
      log.error("error slplit pars[i+1] by : at cmd: %s"%cmd)
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      return None
    if len(time_tmp)<2 or len(time_tmp)>3:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      return None
    try:
      alarm_time=0
      if len(time_tmp)==2:
        alarm_time=time.strptime(pars[i+1], "%H:%M")
      else:
        alarm_time=time.strptime(pars[i+1], "%H:%M:%S")
      date_time = time.localtime(date_timestamp) 
      cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
    except:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      return None
    text_index=4
  else:
    log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
    if cur_data["lang"]=="ru":
      send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
    else:
      send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
    return None

  data={}
  data["result_time"]=cur_time
  data["text_index"]=text_index
  return data

def process_alarm_cmd(user,room,cmd):
  global data
  global client
  global log
  cur_data=data[user][room]
  log.debug("process_alarm_cmd(%s,%s,%s)"%(user,room,cmd))
  pars=cmd.split(' ')
  cur_time=0
  text_index=0
  success=False

  log.debug("pars[1]=%s"%pars[1])
  #=====================  через час: =================
  if pars[1].lower()=='через' and pars[2].lower()=='час' or pars[1].lower()=='via' and pars[2].lower()=='hour':
    time_diff=3600
    cur_time=time.time()+time_diff
    log.debug("cur_time=%f"%cur_time)
    text_index=3
    success=True
  #=====================  через часты и мируты: =================
  elif pars[1].lower()=='через' and len(pars[2].split(':'))>1 or pars[1].lower()=='via' and len(pars[2].split(':'))>1:
    time_tmp=0
    try:
      time_tmp=pars[2].split(':')
    except:
      log.error("error slplit pars[2] by : at cmd: %s"%cmd)
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
    if len(time_tmp)<2 or len(time_tmp)>3:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
    else:
      try:
        alarm_time=0
        if len(time_tmp)==2:
          delta=int(time_tmp[0])*3600+int(time_tmp[1])*60
        else:
          delta=int(time_tmp[0])*3600+int(time_tmp[1])*60+int(time_tmp[2])
        time_now = time.time() 
        cur_time=time_now+delta
        success=True
        text_index=3
      except:
        log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
        if cur_data["lang"]=="ru":
          send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
        else:
          send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))

  #=====================  через несколько мирут или часов: =================
  elif pars[1].lower()=='через' or pars[1].lower()=='via':
    time_tmp=0
    try:
      time_tmp=int(pars[2])
    except:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[2]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      return False
    factor=1
    if "мин" in pars[3] or "min" in pars[3]:
      factor=60
    if "час" in pars[3] or "h" in pars[3]:
      factor=3600
    cur_time=time.time()+int(time_tmp)*factor
    log.debug("factor=%d"%factor)
    log.debug("time_tmp=%d"%int(time_tmp))
    log.debug("cur_time=%f"%cur_time)
    text_index=4
    success=True

  #=====================  завтра: =================
  elif pars[1].lower()=='завтра' or pars[1].lower()=='tomorrow':
    log.debug("tomorrow process")
    cur_time=time.time()+24*3600
    text_index=2
    result=parse_time(cur_time,pars,text_index,cur_data,cmd,room)
    if result==None:
      log.warning("parse_time(%s)"%cmd)
    else:
      text_index=result["text_index"]
      cur_time=result["result_time"]
      success=True

  #=====================  послезавтра: =================
  elif pars[1].lower()=='послезавтра':
    cur_time=time.time()+2*24*3600
    text_index=2
    result=parse_time(cur_time,pars,text_index,cur_data,cmd,room)
    if result==None:
      log.warning("parse_time(%s)"%cmd)
    else:
      text_index=result["text_index"]
      cur_time=result["result_time"]
      success=True

  #=====================  дата: =================
  elif len(pars[1].split('.'))>1:
    date_tmp=0
    try:
      date_tmp=pars[1].split('.')
    except:
      log.error("error slplit pars[1] by : at cmd: %s"%cmd)
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение даты"%(cmd,pars[1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as date"%(cmd,pars[1]))
      return False
    if len(date_tmp)<2 or len(date_tmp)>3:
      log.warning("error pars cmd: '%s' at '%s' as date"%(cmd,pars[1]))
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение даты"%(cmd,pars[1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[1]))
      return False
    try:
      alarm_time=0
      if len(date_tmp)==2:
        if cur_data["lang"]=="ru":
          alarm_date=time.strptime(pars[1], "%d.%m")
        else:
          alarm_date=time.strptime(pars[1], "%m.%d")
        time_now=time.localtime(time.time())
        cur_time=time.mktime(time.struct_time(time_now[:1] + alarm_date[1:3] + time_now[3:]))
      else:
        if cur_data["lang"]=="ru":
          if len(pars[1].split('.')[2])>2:
            alarm_date=time.strptime(pars[1], "%d.%m.%Y")
          else:
            alarm_date=time.strptime(pars[1], "%d.%m.%y")
        else:
          if len(pars[1].split('.')[0])>2:
            alarm_date=time.strptime(pars[1], "%Y.%m.%d")
          else:
            alarm_date=time.strptime(pars[1], "%y.%m.%d")
        time_now=time.localtime(time.time())
        cur_time=time.mktime(time.struct_time(alarm_date[:3] + time_now[3:]))

      text_index=2
      result=parse_time(cur_time,pars,text_index,cur_data,cmd,room)
      if result==None:
        log.warning("parse_time(%s)"%cmd)
      else:
        text_index=result["text_index"]
        cur_time=result["result_time"]
        success=True
    except:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      if cur_data["lang"]=="ru":
        send_message(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
      else:
        send_message(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))

  else:
    #============== пробуем время без даты: ============
    result=parse_time(0,pars,1,cur_data,cmd,room)
    if result==None:
      log.warning("parse_time(%s)"%cmd)
    else:
      text_index=result["text_index"]
      cur_time=result["result_time"]
      success=True

  if success==False:
    # не смог распознать время:
    if cur_data["lang"]=="ru":
      send_message(room,"Не смог распознать в команде '%s' слово '%s' как предлог"%(cmd,pars[1]))
    else:
      send_message(room,"error pars cmd: '%s' at '%s' as predicate"%(cmd,pars[1]))
    return False
    

# Время получили, устанавливаем таймер:
  print("cur_time=",cur_time)
  #timestamp=time.mktime(cur_time)
  # TODO:
  alarm_text=""

  while text_index < len(pars):
    alarm_text+=pars[text_index]
    alarm_text+=" "
    text_index+=1
  alarm_text=alarm_text.strip()

  cur_data["alarms"][int(cur_time)]=alarm_text
  # Сохраняем в файл данных:
  save_data(data)
  if cur_data["lang"]=="ru":
    return send_message(room,"Установил напоминание на %s, с текстом: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )
  else:
    return send_message(room,"set alarm at %s, with text: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )


def send_html(room_id,html):
  global client
  global log

  room=None
  try:
    room = client.join_room(room_id)
  except MatrixRequestError as e:
    print(e)
    if e.code == 400:
      log.error("Room ID/Alias in the wrong format")
      return False
    else:
      log.error("Couldn't find room.")
      return False
  try:
    room.send_html(html)
  except:
    log.error("Unknown error at send message '%s' to room '%s'"%(html,room_id))
    return False
  return True

def send_message(room_id,message):
  global client
  global log

  room=None
  try:
    room = client.join_room(room_id)
  except MatrixRequestError as e:
    print(e)
    if e.code == 400:
      log.error("Room ID/Alias in the wrong format")
      return False
    else:
      log.error("Couldn't find room.")
      return False
  try:
    room.send_text(message)
  except:
    log.error("Unknown error at send message '%s' to room '%s'"%(message,room_id))
    return False
  return True

# Called when a message is recieved.
def on_message(event):
    global client
    global log
    global lock
    print(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False))
    if event['type'] == "m.room.member":
        if event['membership'] == "join":
            print("{0} joined".format(event['content']['displayname']))
    elif event['type'] == "m.room.message":
        if event['content']['msgtype'] == "m.text":
            print("{0}: {1}".format(event['sender'], event['content']['body']))
            log.debug("try lock before process_command()")
            with lock:
              log.debug("success lock before process_command()")
              if process_command(event['sender'], event['room_id'],event['content']['body']) == False:
                log.error("error process command: '%s'"%event['content']['body'])
                return False
    else:
      print(event['type'])
    return True

def on_event(event):
    print("event:")
    print(event)
    print(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False))

def on_invite(room, event):
    global client
    global log

    if conf.debug:
      print("invite:")
      print("room_data:")
      print(room)
      print("event_data:")
      print(event)
      print(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False))

    # Просматриваем сообщения:
    for event_item in event['events']:
      if event_item['type'] == "m.room.join_rules":
        if event_item['content']['join_rule'] == "invite":
          # Приглашение вступить в комнату:
          print("TODO join to room: %s"%room)
          room = client.join_room(room)
          room.send_text("Спасибо за приглашение! Недеюсь быть Вам полезным. :-)")
          room.send_text("Для справки по доступным командам - неберите: '!help' (или '!?', или '!h')")

def main():
    global client
    global data
    global log
    global lock

    lock = threading.RLock()

    log.debug("try lock before main load_data()")
    with lock:
      log.debug("success lock before main load_data()")
      data=load_data()

    client = MatrixClient(conf.server)

    try:
        client.login_with_password(username=conf.username, password=conf.password)
    except MatrixRequestError as e:
        print(e)
        log.debug(e)
        if e.code == 403:
            log.error("Bad username or password.")
            sys.exit(4)
        else:
            log.error("Check your sever details are correct.")
            sys.exit(2)
    except MissingSchema as e:
        log.error("Bad URL format.")
        print(e)
        log.debug(e)
        sys.exit(3)

    client.add_listener(on_message)
    client.add_ephemeral_listener(on_event)
    client.add_invite_listener(on_invite)
    client.start_listener_thread()

    x=0
    while True:
      # Проверяем уведомления:
      log.debug("try lock before main loop")
      with lock:
        log.debug("success lock before main loop")
        for user in data:
          for room in data[user]:
            for alarm_timestamp in data[user][room]["alarms"]:
              time_now=time.time()
              if alarm_timestamp < time_now:
                # Уведомляем:
                html="<p><strong>Напоминаю Вам:</strong></p>\n<ul>\n"
                html+="<li>%s</li>\n"%data[user][room]["alarms"][alarm_timestamp]
                html+="</ul>\n"
                if send_html(room,html)==True:
                  del data[user][room]["alarms"][alarm_timestamp]
                  save_data(data)
                  break # выходим из текущего цикла, т.к. изменили количество в маассиве (валится в корку) - следующей проверкой проверим оставшиеся
                else:
                  log.error("error send alarm at '%s' with text: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(alarm_timestamp)),data[user][room]["alarms"][alarm_timestamp]) )

      print("step %d"%x)
      x+=1
      time.sleep(10)


if __name__ == '__main__':
  log= logging.getLogger("matrix_tomato_reminder_bot")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.FileHandler(conf.log_path)
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

  if conf.debug:
    # логирование в консоль:
    #stdout = logging.FileHandler("/dev/stdout")
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    log.addHandler(stdout)



  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")
  main()
  log.info("Program exit!")
