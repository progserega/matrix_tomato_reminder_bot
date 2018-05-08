#!/usr/bin/env python
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

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import sendemail as mail
import config as conf

client = None
log = None


def save_data(data):
  global log
  log.debug("data_file:%s"%conf.data_file)
  try:
    data_file=open(conf.data_file,"wb")
  except:
    log.error("open(%s) for writing"%conf.data_file)
    return False
    
  pickle.dump(data,data_file)
  data_file.close()

def load_data():
  tmp_data_file=conf.data_file
  data={}
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
    data["users"]={}
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

  
  if cmd == '!?' or cmd == '!h' or cmd == '!help':
    answer="""!repeat - повторить текущую задачу
!stop - остановить текущую задачу
!alarm время текст - напомнить в определённое время и показать текст
!ru - russian language
!en - english language
"""
    return send_message(room,answer)

  # язык:
  elif cmd == '!ru':
    cur_data["lang"]="ru"
    return send_message(room,"Установил язык Русский")
  elif cmd == '!en':
    cur_data["lang"]="en"
    return send_message(room,"Set language to English")
  
  # Напоминалки:
  elif re.search('^!*alarm .*', cmd) is not None or \
    re.search(u'^!*напомни .*', cmd) is not None:
    return process_alarm_cmd(user,room,cmd)
  
  return True

def process_alarm_cmd(user,room,cmd):
  cur_data=data[user][room]
  log.debug("process_alarm_cmd(%s,%s,%s)"%(user,room,cmd))
  pars=cmd.split(' ')
  cur_time=0
  log.debug("pars[1]=%s"%pars[1])
  if pars[1]==u'через' or pars[1]=='via':
    time_tmp=0
    try:
      time_tmp=int(pars[2])
    except:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      if cur_data["lang"]=="ru":
        send_message("Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[2]))
      else:
        send_message("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      return False
    factor=1
    if u"мин" in pars[3] or "min" in pars[3]:
      factor=60
    if u"час" in pars[3] or "h" in pars[3]:
      factor=3600
    cur_time=time.time()+int(time_tmp)*factor
    log.debug("factor=%d"%factor)
    log.debug("time_tmp=%d"%int(time_tmp))
    log.debug("cur_time=",cur_time)
  elif pars[1]==u'в' or pars[1]=='in':
    time_tmp=0
    try:
      time_tmp=pars[2].split(':')
    except:
      log.error("error slplit pars[2] by : at cmd: %s"%cms)
      if cur_data["lang"]=="ru":
        send_message("Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[2]))
      else:
        send_message("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      return False
    if len(time_tmp)<2 or len(time_tmp)>3:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      if cur_data["lang"]=="ru":
        send_message("Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[2]))
      else:
        send_message("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      return False
    try:
      if len(time_tmp)==2:
        cur_time=time.strptime(pars[2], "%H:%M")
      else:
        cur_time=time.strptime(pars[2], "%H:%M:%S")
    except:
      log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      if cur_data["lang"]=="ru":
        send_message("Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[2]))
      else:
        send_message("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
      return False
  else:
    if cur_data["lang"]=="ru":
      send_message("Не смог распознать в команде '%s' слово '%s' как предлог"%(cmd,pars[1]))
    else:
      send_message("error pars cmd: '%s' at '%s' as predicate"%(cmd,pars[1]))
    return False
    

# Время получили, устанавливаем таймер:
  print("cur_time=",cur_time)
  #timestamp=time.mktime(cur_time)
  # TODO:
  alarm_text=pars[3:]
  cur_data["alarms"][int(cur_time)]=alarm_text
  if cur_data["lang"]=="ru":
    return send_message(room,u"Установил напоминание на %s, с текстом: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )
  else:
    return send_message(room,u"set alarm at %s, with text: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )


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
    print(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False,encoding="utf-8"))
    if event['type'] == "m.room.member":
        if event['membership'] == "join":
            print("{0} joined".format(event['content']['displayname']))
    elif event['type'] == "m.room.message":
        if event['content']['msgtype'] == "m.text":
            print("{0}: {1}".format(event['sender'], event['content']['body'].encode('utf8')))
            if process_command(event['sender'], event['room_id'],event['content']['body']) == False:
              log.error("error process command: '%s'"%event['content']['body'].encode('utf8'))
              return False
    else:
      print(event['type'])
    return True

def on_event(event):
    print("event:")
    print(event)
    print(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False,encoding="utf-8"))

def on_invite(room, event):
    global client
    global log

    if conf.debug:
      print("invite:")
      print("room_data:")
      print(room)
      print("event_data:")
      print(event)
      print(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False,encoding="utf-8"))

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
        #msg = samples_common.get_input()
        #if msg == "/quit":
        #    break
        #else:
        #    room.send_text(msg)
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
    stdout = logging.FileHandler("/dev/stdout")
    stdout.setFormatter(formatter)
    log.addHandler(stdout)



  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")
  main()
  log.info("Program exit!")
