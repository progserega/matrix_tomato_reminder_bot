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

import asyncio
import nio
import configparser

import sys
import traceback
import logging
from logging import handlers
import time
import datetime
import json
import os
import re
import matrix_api
import commands

client = None
log = None
data={}
lock = None

week_days={
  "понедельник":1,
  "вторник":2,
  "среду":3,
  "четверг":4,
  "пятницу":5,
  "субботу":6,
  "воскресенье":7
}

def get_exception_traceback_descr(e):
  if hasattr(e, '__traceback__'):
    tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
    result=""
    for msg in tb_str:
      result+=msg
    return result
  else:
    return e

def save_data(data):
  global log
  log.debug("save to data_file:%s"%conf.data_file)
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
    data["users"]={}
    save_data(data)
  return data

async def unknown_cb(room, event):
  global config
  global client
  global log
  #if room.display_name == "Сергей2":
  log.debug(room.room_id)
  log.debug(event)

def check_allow_invite(user):
  global config
  global log
  try:
    # проверка на разрешение по конфигу
    allow=False
    allow_mask=False
    allow_domains_list = config["invites"]["allow_domains"].split(' ')
    allow_users_list = config["invites"]["allow_users"].split(' ')
    deny_domains_list = config["invites"]["deny_domains"].split(' ')
    deny_users_list = config["invites"]["deny_users"].split(' ')

    if len(allow_domains_list)>0:
      for domain in allow_domains_list:
        if re.search('.*:%s$'%domain.lower(), user.lower()) is not None:
          allow=True
          allow_mask=False
          log.info("user: %s from allow domain: %s - allow invite"%(user, domain))
          break
        if allow_domain == '*':
          allow=True
          allow_mask=True
          break
    # если разрешение было только через маску, то его может отменить запрет конкретного домена:
    if allow_mask == True:
      if len(deny_domains_list)>0:
        for domain in deny_domains_list:
          if re.search('.*:%s$'%domain.lower(), user.lower()) is not None:
            allow = False
            log.info("user: %s from deny domain: %s - deny invite"%(user, domain))
            break
          # не используется, т.к. звёздочка из allow_domains перекрывает эту опцию.
          # А иначе - по умолчанию всё равно запрещён доступ:
          #if domain == '*':
          #  allow_mask=False
          #  break

    if len(deny_users_list)>0:
      for deny_user in deny_users_list:
        if deny_user.lower() == user.lower():
          allow = False
          log.info("user: %s from deny users - deny invite"%user)
          break

    # разрешение конкретного пользователя может перекрывать всё:
    if len(allow_users_list)>0:
      for allow_user in allow_users_list:
        if allow_user.lower() == user.lower():
          allow=True
          log.info("user: %s from allow users - allow invite"%user)
          break
    log.info("result check allow invite = %s"%allow)
    return allow
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

async def sync():
  global config
  global client
  global log
  global session
  try:
    if "token" in session:
      token = session["token"]
      resp = await client.sync(full_state=True, since=session['token'])
    else:
      resp = await client.sync(timeout=500,full_state=True)
    session["token"] = resp.next_batch
    return resp
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

async def invite_cb(room: nio.MatrixRoom, event: nio.InviteEvent):
  global config
  global client
  global log
  global session

  try:
    log.debug("start function")

    if check_allow_invite(event.sender) == False:
      log.warning("%s not allowed to invite bot"%event.sender)
      return True

    resp = await client.join(room.room_id)
    if isinstance(resp, nio.JoinError):
      log.error("client.join()")
      return False

    # обновляем список комнат в которых мы есть:
    resp = await sync()
    if resp is None:
      log.error("sync()")
      log.info("join to room %s by invite from %s"%(room.room_id, event.sender))
    else:
      cur_room = client.rooms[room.room_id]
      log.info("join to room %s by invite from %s"%(cur_room.name, event.sender))

    # save sync token
    session["token"] = client.next_batch
    if write_details_to_disk(session) == False:
      log.error("write session to disk - at write_details_to_disk()")
      return False
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

async def sync_cb(response):
  print(f"We synced, token: {response}")

async def message_cb(room, event):
  global config
  global client
  global log

  try:
    log.debug("start function")
    log.debug(room.room_id)
    #FIXME
    log.debug(event)
    log.debug(room.power_levels)

    # проверяем, что обращаются к нам (значит команда):
    nick_name = room.user_name(session["user_id"])
    log.debug("nick_name=%s"%nick_name)
    if re.search('^ *%s *'%nick_name,event.body) is not None:
      command = re.sub('^ *%s *:* *'%nick_name, '', event.body)
      if await commands.process_command(room, event, command) == False:
        log.error("commands.process_command()")
        return False

    # обычное сообщение:
    log.debug("обычное сообщение от: %s"%event.sender)
    # TODO

    if await matrix_api.set_read_marker(room,event) == False:
      log.error("matrix_api.set_read_marker()")
      return False

    # save sync token
    session["token"] = client.next_batch
    if write_details_to_disk(session) == False:
      log.error("write session to disk - at write_details_to_disk()")
      return False

    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

def write_details_to_disk(session) -> None:
  global config
  global log
  log.debug("start function")
  try:
    # open the config file in write-mode
    with open(config["matrix"]["session_store_path"], "w") as f:
      # write the login details to disk
      json.dump(session,f)
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

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

  #FIXME отладка парсера
  #print("message=%s"%message)
  #return True

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

def send_notice(room_id,message):
  global client
  global log
  log.debug("=start function=")
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
    room.send_notice(message)
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error("Unknown error at send notice message '%s' to room '%s'"%(message,room_id))
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
            reply_to_id=None
            if "m.relates_to" in  event['content']:
              # это ответ на сообщение:
              try:
                reply_to_id=event['content']['m.relates_to']['m.in_reply_to']['event_id']
              except:
                log.error("bad formated event reply - skip")
                send_message(event['room_id'],"Внутренняя ошибка разбора сообщения - обратитесь к разработчику")
                return False
            formatted_body=None
            format_type=None
            if "formatted_body" in event['content'] and "format" in event['content']:
              formatted_body=event['content']['formatted_body']
              format_type=event['content']['format']
            log.debug("{0}: {1}".format(event['sender'], event['content']['body'].encode('utf8')))
            log.debug("try lock before mbl.process_message()")
             
            log.debug("try lock before process_command()")
            with lock:
              log.debug("success lock before process_command()")
              if process_command(
                event['sender'],\
                event['room_id'],\
                event['content']['body'],\
                formated_message=formatted_body,\
                format_type=format_type,\
                reply_to_id=reply_to_id\
                ) == False:
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
          room = client.join_room(room)
          room.send_text("Спасибо за приглашение! Недеюсь быть Вам полезным. :-)")
          room.send_text("Для справки по доступным командам - неберите: '!help' (или '!?', или '!h')")
          log.info("New user: '%s'"%event_item["sender"])



def main_old():
    global client
    global data
    global log
    global lock

    lock = threading.RLock()

    log.debug("try lock before main load_data()")
    with lock:
      log.debug("success lock before main load_data()")
      data=load_data()

    #FIXME отладка парсера
    #data["users"]["@progserega:matrix.org"]={}
    #data["users"]["@progserega:matrix.org"]["test"]={}
    #data["users"]["@progserega:matrix.org"]["test"]["alarms"]=[]
    #data["users"]["@progserega:matrix.org"]["test"]["lang"]="ru"
    #print(process_alarm_cmd("@progserega:matrix.org","test","напомни послезавтра после работы проверить звук в машине и подтёки масла, т.к. 11 июня закончится гарантия."))
    #sys.exit(1)

    log.info("try init matrix-client")
    client = MatrixClient(conf.server)
    log.info("success init matrix-client")

    try:
        log.info("try login matrix-client")
        client.login_with_password(username=conf.username, password=conf.password)
        log.info("success login matrix-client")
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

    log.info("try init listeners")
    client.add_listener(on_message)
    client.add_ephemeral_listener(on_event)
    client.add_invite_listener(on_invite)
#client.start_listener_thread()
    # Слушанье сокета и пересоединение в случае сбоя:
#client.listen_forever(timeout_ms=30000, exception_handler=exception_handler,bad_sync_timeout=5)
    client.start_listener_thread(exception_handler=exception_handler)
#client.listen_forever(timeout_ms=30000, exception_handler=exception_handler,bad_sync_timeout=5)
    #client.listen_forever()
    log.info("success init listeners")

    x=0
    log.info("enter main loop")
    while True:
      # Проверяем уведомления:
      log.debug("try lock before main loop")
      with lock:
        log.debug("success lock before main loop")
        for user in data["users"]:
          for room in data["users"][user]:
            for item in data["users"][user][room]["alarms"]:
              alarm_timestamp=item["time"]
              alarm_text=item["text"]
              time_now=time.time()
              if alarm_timestamp < time_now:
                # Уведомляем:
                html="<p><strong>Напоминаю Вам:</strong></p>\n<ul>\n"
                html+="<li>%s</li>\n"%alarm_text
                html+="</ul>\n"
                if send_html(room,html)==True:
                  data["users"][user][room]["alarms"].remove(item)
                  save_data(data)
                  break # выходим из текущего цикла, т.к. изменили количество в маассиве (валится в корку) - следующей проверкой проверим оставшиеся
                else:
                  log.error("error send alarm at '%s' with text: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(alarm_timestamp)),alarm_text) )

      #print("step %d"%x)
      #x+=1
      time.sleep(10)
    log.info("exit main loop")


def get_event(log, client, room_id, event_id):
  log.debug("=== start function ===")
  """Perform GET /rooms/$room_id/event/$event_id

  Args:
      room_id(str): The room ID.
      event_id(str): The event ID.

  Raises:
      MatrixRequestError(code=404) if the event is not found.
  """
  return client.api._send("GET", "/rooms/{}/event/{}".format(quote(room_id), quote(event_id)))

async def main():
  global config
  global client
  global session

  session = {}

  try:
    # If there are no previously-saved credentials, we'll use the password
    if not os.path.exists(config["matrix"]["session_store_path"]):
      client = nio.AsyncClient(config["matrix"]["matrix_server"], config["matrix"]["matrix_login"])

      resp = await client.login(config["matrix"]["matrix_passwd"])
      # check that we logged in succesfully
      if isinstance(resp, nio.LoginResponse):
        session["homeserver"] = config["matrix"]["matrix_server"]  # e.g. "https://matrix.example.org"
        session["user_id"] = resp.user_id  # e.g. "@user:example.org"
        session["device_id"] = resp.device_id  # device ID, 10 uppercase letters
        session["access_token"] = resp.access_token  # cryptogr. access token
        log.info("login by password")
    else:
      # open the file in read-only mode
      with open(config["matrix"]["session_store_path"], "r") as f:
        session = json.load(f)
        client = nio.AsyncClient(session["homeserver"])
        client.access_token = session["access_token"]
        client.user_id = session["user_id"]
        client.device_id = session["device_id"]

        resp = client.restore_login(
          user_id=session["user_id"],
          device_id=session["device_id"],
          access_token=session["access_token"],
        )  # returns always None, on success or failure
      log.info("login by session")

    client.add_event_callback(message_cb, nio.RoomMessageText)
    client.add_event_callback(invite_cb, nio.InviteEvent)
    # обработчик, вызываемый после каждого успешного синка в функции sync_forever().
    # есть функция sync(), но почему-то она не вызывает обработчики сообщений
    client.add_response_callback(sync_cb)

    #client.add_event_callback(unknown_cb, nio.RoomMessage)

    # инициализация модулей:
    if commands.init(log,config) == False:
      log.error("commands.init()")
      return False
    log.info("commands.init()")
    if matrix_api.init(log,config,client) == False:
      log.error("matrix_api.init()")
      return False
    log.info("matrix_api.init()")
    # бесконечный внутренний цикл опроса состояния:
    if 'token' in session:
      await client.sync_forever(timeout=300,full_state=True,since=session['token'],loop_sleep_time=3000)
    else:
      await client.sync_forever(timeout=300,full_state=True,loop_sleep_time=3000)
    return True
    
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

def loadConfig(file_name):
  config = configparser.ConfigParser()
  config.read(file_name)
  return config

if __name__ == '__main__':
  if len(sys.argv) < 2:
    print("need 1 param - config file")
    sys.exit(1)
  else:
    config=loadConfig(sys.argv[1])
  log= logging.getLogger("matrix_tomato_reminder_bot")

  if config["logging"]["debug"].lower()=="yes":
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  #fh = logging.FileHandler(config.log_path)
  fh = logging.handlers.TimedRotatingFileHandler(config["logging"]["log_path"], when=config["logging"]["log_backup_when"], backupCount=int(config["logging"]["log_backup_count"]), encoding='utf-8')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

#  if config["logging"]["debug"].lower()=="yes":
  # логирование в консоль:
  stdout = logging.StreamHandler(sys.stdout)
  stdout.setFormatter(formatter)
  log.addHandler(stdout)

  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")
  log.info("python version=%s"%sys.version)

  asyncio.get_event_loop().run_until_complete(main())
  #if main()==False:
  #  log.error("error main()")
  #  sys.exit(1)
  log.info("program exit success")

