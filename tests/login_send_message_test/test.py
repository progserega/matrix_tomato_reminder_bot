#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import traceback
import datetime
import logging
import json
from logging import handlers
import configparser
import asyncio
import nio
#from nio import AsyncClient, MatrixRoom, RoomMessageText


log=None
config=None


def get_exception_traceback_descr(e):
  if hasattr(e, '__traceback__'):
    tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
    result=""
    for msg in tb_str:
      result+=msg
    return result
  else:
    return e

async def message_callback(room: nio.MatrixRoom, event: nio.RoomMessageText) -> None:
    print(
        f"Message received in room {room.display_name}\n"
        f"{room.user_name(event.sender)} | {event.body}"
    )

async def main_loop():
  global log
  global config
  try:
    client = nio.AsyncClient(config["main"]["server"], config["main"]["username"])
    client.add_event_callback(message_callback, nio.RoomMessageText)
    ret = await client.login(config["main"]["password"],device_name=config["main"]["device_name"])
    if (isinstance(ret, nio.LoginResponse)):
      log.info("login success")
    else:
      log.info("login error")
      sys.exit(1)

    await client.sync_forever(timeout=30000,full_state=True) # milliseconds
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    sys.exit(1)

def main():
  global log
  global config
  try:
    asyncio.get_event_loop().run_until_complete(main_loop())
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    sys.exit(1)

def loadConfig(file_name):
  config = configparser.ConfigParser()
  config.read(file_name)
  return config

if __name__ == '__main__':
  #global log
  #global config

  if len(sys.argv) < 2:
    print("need 1 param - config file")
    print("load default config: config.ini")
    config=loadConfig("config.ini")
  else:
    config=loadConfig(sys.argv[1])

  log=logging.getLogger("login_test")
  if config["logging"]["debug"].lower()=="yes":
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  #fh = logging.FileHandler(config.log_path)
  fh = logging.handlers.TimedRotatingFileHandler(config["logging"]["log_path"], when=config["logging"]["log_backup_when"], backupCount=int(config["logging"]["log_backup_count"]), encoding='utf-8')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

  # логирование в консоль:
  stdout = logging.StreamHandler(sys.stdout)
  stdout.setFormatter(formatter)
  log.addHandler(stdout)

  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")
  log.info("python version=%s"%sys.version)

  if main()==False:
    log.error("error main()")
    sys.exit(1)
  log.info("Program SUCCESS exit")
