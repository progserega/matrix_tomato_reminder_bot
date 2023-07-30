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
import bot_logic

client = None
config = None
log = None
lock = None
session = {}

def get_exception_traceback_descr(e):
  if hasattr(e, '__traceback__'):
    tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
    result=""
    for msg in tb_str:
      result+=msg
    return result
  else:
    return e

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
  bot_logic.proccess_alarms()

async def message_cb(room, event):
  global config
  global client
  global log

  try:
    log.debug("start function")
    log.debug(room.room_id)
    #FIXME
    log.debug(event)
    log.debug(json.dumps(event.source, indent=4, sort_keys=True,ensure_ascii=False))
    log.debug(event.formatted_body)
    log.debug(event.body)
    log.debug(event.format)
   # log.debug(event.msgtype)
    #log.debug(event.content)
    #log.debug(event.type)
    log.debug(room.power_levels)

    # проверяем, что обращаются к нам (значит команда):
    nick_name = room.user_name(session["user_id"])
    log.debug("nick_name=%s"%nick_name)
    reply_to_id = None
    if "m.relates_to" in event.source["content"]:
      try:
        reply_to_id = event.source["content"]["m.relates_to"]["m.in_reply_to"]["event_id"]
      except:
        log.error("bad formated event reply - skip")
        matrix_api.send_message(room.room_id,"Внутренняя ошибка разбора сообщения - обратитесь к разработчику")
        return False

    proccess_command = False
    log.debug("room member count = %d"%room.member_count)
    if room.member_count > 2:
      # если участников более 2-х, то к боту нужно обращаться по имени:
      if re.search('^ *%s *'%nick_name,event.body) is not None:
        command = re.sub('^ *%s *:* *'%nick_name, '', event.body)
        # и тогда он воспримет команду
        process_command = True
    else:
      # приватный чат на двоих с пользователем - воспринимаем все команды пользователя, не требуя 
      # обращения по имени:
      proccess_command = True
    if proccess_command == True:
      if await bot_logic.process_command(\
          event.source["sender"],\
          room,\
          event.body,\
          formated_message = event.formatted_body,\
          format_type = event.format,\
          reply_to_id = reply_to_id) == False:
        log.error("bot_logic.process_command()")
        return False

    # обычное сообщение:
    log.debug("обычное сообщение от: %s"%event.sender)

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
    if bot_logic.init(log,config,client) == False:
      log.error("bot_logic.init()")
      return False
    log.info("bot_logic.init()")
    if matrix_api.init(log,config,client) == False:
      log.error("matrix_api.init()")
      return False
    log.info("matrix_api.init()")
    if bot_logic.init(log,config,client) == False:
      log.error("bot_logic.init()")
      return False
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

