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
import simplematrixbotlib as botlib

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


def main():
  global log
  global config

  try:
    # https://simple-matrix-bot-lib.readthedocs.io/en/latest/quickstart.html#quickstart
    # Create a Creds object with your login credentials.
    creds = botlib.Creds(config["main"]["server"], config["main"]["username"], config["main"]["password"])
    # Create a bot object. This will be used as a handle throughout your project.
    bot = botlib.Bot(creds)
    PREFIX = config["main"]["bot_cmd_prefix"]

    # Create a command by defining a function. The function must be an “async” function with two arguments.
    # Recommended argument names are (room, message) or (room, event)
    @bot.listener.on_message_event
    async def exit_fun(room, message):
      log.debug("exit_fun function")
      try:
        # Creating a MessageMatch object is optional, but useful for handling messages.
        # The prefix argument is optional, but is needed when matching prefixes.
        match = botlib.MessageMatch(room, message, bot, PREFIX)
        
        #if match.is_not_from_this_bot() and match.prefix() and match.command("exit"):
        # смотрим и свои команды:
        if match.prefix() and match.command("exit"):
          # This part of the handler is responsible for sending the response message. 
          # The rest of the message following “!echo” will be sent to the same room as the message.
          log.info("exit cmd")
          log.info("success receive exit command")
          sys.exit(0)
          return True
      except Exception as e:
        log.error(get_exception_traceback_descr(e))
        sys.exit(1)

    @bot.listener.on_startup
    async def room_joined(room_id):
      log.info("send exit command")
      await bot.api.send_text_message(
        room_id, "!exit"
      )

    # Before creating a function handler for a command, it is necessary to add a listener.
    bot.run()
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
