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

def init(log_param,config_param):
  global log
  global config
  log = log_param
  config = config_param

  # локализация. Стандартный вариант, без переключения локали на-лету. Опция языка берётся из переменных 
  # окружения LC_*:
  # переводимые строки заключать в символы _("english text id")
  # https://habr.com/ru/post/73554/
  # https://docs.python.org/3/library/gettext.html
  #
  #gettext.install('commands', './locale')

  log.info("success init bot_logic module")
  return True


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
