#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import nio
import configparser
import logging
from logging import handlers
import sys
import json
import re
import os
import traceback
import datetime
import time

config = None
client = None
log = None

def get_exception_traceback_descr(e):
  if hasattr(e, '__traceback__'):
    tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
    result=""
    for msg in tb_str:
      result+=msg
    return result
  else:
    return e

def init(log_param,config_param, client_param):
  global log
  global config
  global client
  log = log_param
  config = config_param
  client = client_param
  log.info("success matrix_api module")
  return True

async def send_notice(room,text):
  global config
  global client
  global log
  content = {
        "body": text,
        "msgtype": "m.notice"
      }
  try:
    resp = await client.room_send(room.room_id, message_type="m.room.message", content=content)
    if isinstance(resp, nio.RoomMessagesError):
      log.warning("client.room_send() failed with response = {resp}.")
      return False
    log.debug("send room.message successfully")
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error(f"send room.message failed.")
    return False
  return True

async def send_html(room,formatted_body,body=None):
  global config
  global client
  global log
  try:
    content = {
          "formatted_body": formatted_body,
          "msgtype": "m.text",
          "format": "org.matrix.custom.html",
        }
    if body is not None:
      content["body"]=body
    else:
      content["body"]=re.sub('<[a-zA-Z-_/]>','', formatted_body,0)

    resp = await client.room_send(room.room_id, message_type="m.room.message", content=content)
    if isinstance(resp, nio.RoomMessagesError):
      log.warning("client.room_send() failed with response = {resp}.")
      return False
    log.debug("send room.message successfully")
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error(f"send room.message failed.")
    return False
  return True

async def send_text(room,text):
  global config
  global client
  global log
  content = {
        "body": text,
        "msgtype": "m.text"
      }
  try:
    resp = await client.room_send(room.room_id, message_type="m.room.message", content=content)
    if isinstance(resp, nio.RoomMessagesError):
      log.warning("client.room_send() failed with response = {resp}.")
      return False
    log.debug("send room.message successfully")
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error(f"send room.message failed.")
    return False
  return True

async def send_emotion(room,event,emotion_text):
  global config
  global client
  global log
  content = {
      "m.relates_to": {
        "event_id": event.event_id,
        "key": emotion_text,
        "rel_type": "m.annotation"
      }
    }
  try:
    resp = await client.room_send(room.room_id, message_type="m.reaction", content=content)
    if isinstance(resp, nio.RoomMessagesError):
      log.warning("client.room_send() failed with response = {resp}.")
      return False
    log.debug("set reaction '%s' successfully"%emotion_text)
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error(f"set reaction failed.")
    return False
  return True

async def set_read_marker(room,event):
  global client
  global log
  try:
    resp = await client.room_read_markers(
                  room_id=room.room_id,
                  fully_read_event=event.event_id,
                  read_event=event.event_id,
              )
    if isinstance(resp, nio.RoomReadMarkersError):
      log.warning("room_read_markers failed with response = {resp}.")
      return False
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.warning("room_read_markers failed with response = {resp}.")
    return False
  return True

async def get_event(room,event_id):
  global client
  global log
  try:
    resp = await client.get_event(
                  access_token=client.access_token,
                  room_id=room.room_id,
                  event_id=event_id
              )
    if isinstance(resp, nio.RoomReadMarkersError):
      log.warning("room_read_markers failed with response = {resp}.")
      return None
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.warning("room_read_markers failed with response = {resp}.")
    return None
  return resp

