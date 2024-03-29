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
import pickle
import os
import re
import matrix_api as ma

config = None
client = None
log = None
data = None

week_days={
  "понедельник":1,
  "вторник":2,
  "среду":3,
  "четверг":4,
  "пятницу":5,
  "субботу":6,
  "воскресенье":7
}

def init(log_param,config_param, client_param):
  global log
  global config
  global client
  global data
  try:
    log = log_param
    config = config_param
    client = client_param
    data = load_data()
    if data is None:
      log.error("load_data()")
      return False
    log.info("success init bot_logic module")
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False
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
  log.debug("save to data_file:%s"%config["storage"]["data_file"])
  try:
    data_file=open(config["storage"]["data_file"],"wb")
    pickle.dump(data,data_file)
    data_file.close()
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False
  return True

def load_data():
  global log
  global config
  try:
    tmp_data_file=config["storage"]["data_file"]
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
      if save_data(data) == False:
        log.error("save_data()")
        return None
    return data
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

async def process_command(user,room,cmd,formated_message,format_type,reply_to_id):
  global client
  global log
  global data
  answer=None
  cur_data=None
  source_message=None
  source_cmd=None
  source_event_text=None

  log.debug("=== start function ===")

  try:
    if reply_to_id!=None and format_type=="org.matrix.custom.html" and formated_message!=None:
      # разбираем, чтобы получить исходное сообщение и ответ
      # получаем цитируемое сообщение по его id:
      try:
        source_event=await ma.get_event(room, reply_to_id)
        log.debug(source_event)
      except Exception as e:
        log.error(get_exception_traceback_descr(e))
        await ma.send_text(room,"ошибка получения исходного сообщения с event_id=%s - обратитесь к разработчику."%reply_to_id)
        source_event=None
      if source_event != None:
        log.debug("success get source message by reply_to_id")
        source_message = source_event["content"]["body"].replace('<br/>','\n')
      else:
        log.debug("get source message from formated_message")
        source_message=re.sub('<mx-reply><blockquote>.*<\/a><br>','', formated_message)
        source_message=re.sub('</blockquote></mx-reply>.*','', source_message)
      log.debug("source=%s"%source_message)
      source_cmd=re.sub(r'.*</blockquote></mx-reply>','', formated_message.replace('\n',''))
      log.debug("cmd=%s"%source_cmd)
      message=source_cmd
      source_event_text=re.sub('.*\n*.*<ul>\n<li>','', source_message)
      source_event_text=re.sub('</li>\n</ul>$','', source_event_text)
      if 'Напоминаю Вам:' in source_event_text:
        source_event_text=re.sub('Напоминаю Вам:\n*','', source_event_text)
      # если цитировали сам факт установки напоминания:
      if 'Установил напоминание на' in source_event_text:
        source_event_text=re.sub("Установил напоминание на .* с текстом: '",'', source_event_text)
        source_event_text=re.sub("'$",'', source_event_text)
      log.debug("source_event_text=%s"%source_event_text)
      cmd=source_cmd + " " + source_event_text

    if user not in data["users"]:
      data["users"][user]={}
    if room not in data["users"][user]:
      data["users"][user][room]={}
      data["users"][user][room]["lang"]="ru"
      data["users"][user][room]["alarms"]=[]

    cur_data=data["users"][user][room]

    
    if re.search('^!*\?$', cmd.lower()) is not None or \
      re.search('^!*h$', cmd.lower()) is not None or \
      re.search('^!*помоги', cmd.lower()) is not None or \
      re.search('^!*помощь', cmd.lower()) is not None or \
      re.search('^!*справка', cmd.lower()) is not None or \
      re.search('^!*faq', cmd.lower()) is not None or \
      re.search('^!*help', cmd.lower()) is not None:
      answer="""!repeat - повторить текущую задачу. Выберите любое моё напоминание и в ответе напишите 'повтори' и обычный формат времени даты 
  !stop - остановить текущую задачу (не реализовано)
  !alarm at время текст - напомнить в определённое время и показать текст
  !напомни в время текст - напомнить в определённое время (сегодня) и показать текст
  !напомни [сегодня|завтра|послезавтра|дата] [в время] текст - напомнить текст. Если время опущено, то будет напомнено в такое же время. Взамен "в время" можно написать "в обед" - %(lunch_break)s или "после работы" - %(after_work)s или "вечером" - %(evening)s или "утром" - %(morning)s.
  !напомни через число минут|часов текст - напомнить текст через указанное количество часов или минут.
  !напомни через время текст - напомнить текст через указанное количество времени
  !40 - напомни через 40 минут текстом '40 минут прошло'
  !5 - напомни через 5 минут текстом '5 минут прошло'
  Время предполагается вида: 13:23, дата: 30.04 или 30.04.18 или 30.04.2018 (в режиме английского языка - наоборот: 2018.04.30)
  !ru - russian language
  !en - english language
  !alarms - показать текущие активные напоминания (псевдонимы: 'все', 'всё', 'all', 'list', 'список', 'напоминания')

  Восклицательный знак в начале команды можно опустить.

  Примеры:

  напомни вечером позвонить другу
  напомни 23.06 в 14:25 сделать дело 
  напомни в 14:25 сделать дело 
  напомни в пятницу в 14:25 сделать дело 
  напомни во вторник на работе сделать дело 
  напомни через 20 минут сними кашу 
  напомни послезавтра после работы сделать дело 
  """ % {"morning":config["time_presets"]["morning"], "lunch_break":config["time_presets"]["lunch_break"], "after_work":config["time_presets"]["after_work"], "evening":config["time_presets"]["evening"]}
      return await ma.send_text(room,answer)

    # язык:
    elif cmd == '!ru':
      cur_data["lang"]="ru"
      return await ma.send_text(room,"Установил язык Русский")
    elif cmd == '!en':
      cur_data["lang"]="en"
      return await ma.send_text(room,"Set language to English")
    
    # Добавить Напоминалки:
    elif re.search('^!*alarm .*', cmd.lower()) is not None or \
      re.search('^!*напомни .*', cmd.lower()) is not None:
      return await process_alarm_cmd(user,room,cmd)

    # повторение
    elif re.search('^!*retry .*', cmd.lower()) is not None and reply_to_id != None or \
      re.search('^!*повтори .*', cmd.lower()) is not None and reply_to_id != None:
      return await process_alarm_cmd(user,room,cmd)

    # повторение
    elif re.search('^!*retry .*', cmd.lower()) is not None and reply_to_id == None or \
      re.search('^!*повтори .*', cmd.lower()) is not None and reply_to_id == None:
      answer="Выделите одно из моих напоминаний и в ответе напишите 'повторить дата/время'"
      return await ma.send_text(room,answer)
    
    # Просмотреть Напоминалки:
    elif re.search('^!*alarms', cmd.lower()) is not None or \
      re.search('^!*все', cmd.lower()) is not None or \
      re.search('^!*всё', cmd.lower()) is not None or \
      re.search('^!*all', cmd.lower()) is not None or \
      re.search('^!*list', cmd.lower()) is not None or \
      re.search('^!*список', cmd.lower()) is not None or \
      re.search('^!*напоминания', cmd.lower()) is not None:
      return await process_alarm_list_cmd(user,room,cmd)

    # простой числовой таймер (от пользователя передано только число):
    elif re.search('^!*[0-9]+$', cmd.lower()) is not None:
      minutes_string=cmd.replace('!','')
      try:
        minutes=int(minutes_string)
      except:
        log.warning("convert minutes to in in simple_timer prepare")
        return False
      return await process_simple_timer_cmd(user,room,minutes)

    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

async def process_alarm_list_cmd(user,room,cmd):
  global data
  global client
  global log

  try:
    cur_data=data["users"][user][room]
    log.debug("process_alarm_cmd(%s,%s,%s)"%(user,room,cmd))
    time_now=time.time()
    num=0
    for item in cur_data["alarms"]:
      alarm_timestamp=item["time"]
      if alarm_timestamp > time_now:
        num+=1
    if num==0:
      await ma.send_text(room,"На данный момент для Вас нет активных напоминаний")
    else:
      html="<p><strong>Я напомню Вам о следующих событиях:</strong></p>\n<ul>\n"
      for item in cur_data["alarms"]:
        alarm_timestamp=item["time"]
        text=item["text"]
        if alarm_timestamp > time_now:
          # Выводим только актуаальные:
          print("alarm_timestamp=",alarm_timestamp)
          print("string=",text)
          alarm_string=time.strftime("%Y.%m.%d-%T",time.localtime(alarm_timestamp))
          html+="<li>%s: %s!</li>\n"%(alarm_string,text)
      html+="</ul>\n<p><em>Надеюсь ничего не забыл :-)</em></p>\n"
      return await ma.send_html(room,html)
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

async def parse_time(date_timestamp,pars,index,cur_data,cmd,room):
  try:
    log.debug("parse_time(), date_timestamp=%d, pars[index]='%s'"%(date_timestamp,pars[index]))
    if date_timestamp==0:
      date_timestamp=time.time()
    i=index
    if pars[i].lower()=='утром' or pars[i].lower()=='morning':
      alarm_time=time.strptime(config["time_presets"]["morning"], "%H:%M")
      date_time = time.localtime(date_timestamp)
      cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
      text_index=i+1
    elif pars[i].lower()=='на' and pars[i+1].lower()=='работе' or pars[i].lower()=='at' and pars[i+1].lower()=='work':
      alarm_time=time.strptime(config["time_presets"]["on_work"], "%H:%M")
      date_time = time.localtime(date_timestamp)
      cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
      text_index=i+2
    elif pars[i].lower()=='в' and pars[i+1].lower()=='обед' or pars[i].lower()=='at' and pars[i+1].lower()=='lunch':
      alarm_time=time.strptime(config["time_presets"]["lunch_break"], "%H:%M")
      date_time = time.localtime(date_timestamp)
      cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
      text_index=i+2
    elif pars[i].lower()=='после' and pars[i+1].lower()=='обеда' or pars[i].lower()=='after' and pars[i+1].lower()=='lunch':
      alarm_time=time.strptime(config["time_presets"]["after_lunch"], "%H:%M")
      date_time = time.localtime(date_timestamp)
      cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
      text_index=i+2
    elif pars[i].lower()=='после' and pars[i+1].lower()=='работы' or pars[i].lower()=='after' and pars[i+1].lower()=='work':
      alarm_time=time.strptime(config["time_presets"]["after_work"], "%H:%M")
      date_time = time.localtime(date_timestamp)
      cur_time=time.mktime(time.struct_time(date_time[:3] + alarm_time[3:]))
      text_index=i+2
    elif pars[i].lower()=='вечером' or pars[i].lower()=='at' and pars[i+1].lower()=='evening':
      alarm_time=time.strptime(config["time_presets"]["evening"], "%H:%M")
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
          await ma.send_text(room,"(1) Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
        else:
          await ma.send_text(room,"(1) error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
        return None
      if len(time_tmp)<2 or len(time_tmp)>3:
        log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
        if cur_data["lang"]=="ru":
          await ma.send_text(room,"(2) Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
        else:
          await ma.send_text(room,"(2) error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
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
          await ma.send_text(room,"(3) Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
        else:
          await ma.send_text(room,"(3) error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
        return None
      text_index=i+2
    else:
      log.warning("error pars cmd: '%s' at '%s' as predlog"%(cmd,pars[i]))
      return None

    data={}
    data["result_time"]=cur_time
    data["text_index"]=text_index
    return data
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

async def process_alarm_cmd(user,room,cmd):
  global data
  global client
  global log
  try:
    cur_data=data["users"][user][room]
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
    #=====================  через день: =================
    elif pars[1].lower()=='через' and pars[2].lower()=='день' or pars[1].lower()=='via' and pars[2].lower()=='day':
      time_diff=3600*24
      cur_time=time.time()+time_diff
      log.debug("cur_time=%f"%cur_time)
      text_index=3
      success=True
    #=====================  через неделю: =================
    elif pars[1].lower()=='через' and pars[2].lower()=='неделю' or pars[1].lower()=='via' and pars[2].lower()=='week':
      time_diff=3600*24*7
      cur_time=time.time()+time_diff
      log.debug("cur_time=%f"%cur_time)
      text_index=3
      success=True
    #=====================  через месяц: =================
    elif pars[1].lower()=='через' and pars[2].lower()=='месяц' or pars[1].lower()=='via' and pars[2].lower()=='month':
      time_diff=3600*24*30
      cur_time=time.time()+time_diff
      log.debug("cur_time=%f"%cur_time)
      text_index=3
      success=True
    #=====================  через год: =================
    elif pars[1].lower()=='через' and pars[2].lower()=='год' or pars[1].lower()=='via' and pars[2].lower()=='year':
      time_diff=3600*24*365
      cur_time=time.time()+time_diff
      log.debug("cur_time=%f"%cur_time)
      text_index=3
      success=True
    #=====================  через часты и минуты: =================
    elif pars[1].lower()=='через' and len(pars[2].split(':'))>1 or pars[1].lower()=='via' and len(pars[2].split(':'))>1:
      time_tmp=0
      try:
        time_tmp=pars[2].split(':')
      except:
        log.error("error slplit pars[2] by : at cmd: %s"%cmd)
        if cur_data["lang"]=="ru":
          await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
        else:
          await ma.send_text(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
      if len(time_tmp)<2 or len(time_tmp)>3:
        log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
        if cur_data["lang"]=="ru":
          await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
        else:
          await ma.send_text(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
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
            await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
          else:
            await ma.send_text(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))

    #=====================  через несколько мирут, часов, дней, недель, месяцев, лет: =================
    elif pars[1].lower()=='через' or pars[1].lower()=='via':
      time_tmp=0
      try:
        time_tmp=int(pars[2])
      except:
        log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
        if cur_data["lang"]=="ru":
          await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[2]))
        else:
          await ma.send_text(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[2]))
        return False
      factor=1
      if "мин" in pars[3] or "min" in pars[3]:
        factor=60
      elif "час" in pars[3] or "h" in pars[3]:
        factor=3600
      elif "дня" in pars[3] or\
            "дней" in pars[3] or\
            "day" in pars[3]:
        factor=3600*24
      elif "недел" in pars[3] or\
            "week" in pars[3]:
        factor=3600*24*7
      elif "месяц" in pars[3] or\
            "month" in pars[3]:
        factor=3600*24*30
      elif "год" in pars[3] or\
            "year" in pars[3]:
        factor=3600*24*365
      cur_time=time.time()+int(time_tmp)*factor
      log.debug("factor=%d"%factor)
      log.debug("time_tmp=%d"%int(time_tmp))
      log.debug("cur_time=%f"%cur_time)
      text_index=4
      success=True

    #=====================  сегодня: =================
    elif pars[1].lower()=='сегодня' or pars[1].lower()=='today':
      log.debug("today process")
      cur_time=time.time()
      text_index=2
      result= await parse_time(cur_time,pars,text_index,cur_data,cmd,room)
      if result==None:
        log.warning("parse_time(%s)"%cmd)
      else:
        text_index=result["text_index"]
        cur_time=result["result_time"]
        success=True

    #=====================  завтра: =================
    elif pars[1].lower()=='завтра' or pars[1].lower()=='tomorrow':
      log.debug("tomorrow process")
      cur_time=time.time()+24*3600
      text_index=2
      result=await parse_time(cur_time,pars,text_index,cur_data,cmd,room)
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
      result=await parse_time(cur_time,pars,text_index,cur_data,cmd,room)
      if result==None:
        log.warning("parse_time(%s)"%cmd)
      else:
        text_index=result["text_index"]
        cur_time=result["result_time"]
      success=True

    #===================== день недели: =================
    elif (pars[1].lower()=='в' or pars[1].lower()=='во') and pars[2].lower() in week_days:
      diff_day=0
      at_day=week_days[pars[2].lower()]
      cur_day=datetime.datetime.today().isoweekday()

      if at_day>cur_day:
        diff_day=at_day-cur_day
      elif at_day<cur_day:
        diff_day=diff_day=7-cur_day+at_day
      else:
        # at_day=cur_day 
        # если указанный день совпадает с текущим днём, то счиатем, что напомниание ставим на этот
        # день, но уже на следующией недели:
        diff_day=7

      cur_time=time.time()+diff_day*24*3600
      text_index=3
      result=await parse_time(cur_time,pars,text_index,cur_data,cmd,room)
      if result==None:
        log.warning("parse_time(%s)"%cmd)
      else:
        text_index=result["text_index"]
        cur_time=result["result_time"]
      success=True

    #=====================  дата: =================
    elif len(pars[1].split('.'))>1:
      log.debug("parse date: %s"%pars[1])
      date_tmp=0
      try:
        date_tmp=pars[1].split('.')
      except:
        log.error("error slplit pars[1] by : at cmd: %s"%cmd)
        if cur_data["lang"]=="ru":
          await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как значение даты"%(cmd,pars[1]))
        else:
          await ma.send_text(room,"error pars cmd: '%s' at '%s' as date"%(cmd,pars[1]))
        return False
      if len(date_tmp)<2 or len(date_tmp)>3:
        log.warning("error pars cmd: '%s' at '%s' as date"%(cmd,pars[1]))
        if cur_data["lang"]=="ru":
          await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как значение даты"%(cmd,pars[1]))
        else:
          await ma.send_text(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[1]))
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
        result= await parse_time(cur_time,pars,text_index,cur_data,cmd,room)
        if result==None:
          log.warning("parse_time(%s)"%cmd)
        else:
          text_index=result["text_index"]
          cur_time=result["result_time"]
        success=True
      except:
        log.warning("error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))
        if cur_data["lang"]=="ru":
          await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как значение времени"%(cmd,pars[i+1]))
        else:
          await ma.send_text(room,"error pars cmd: '%s' at '%s' as time"%(cmd,pars[i+1]))

    else:
      #============== пробуем время без даты: ============
      result=await parse_time(0,pars,1,cur_data,cmd,room)
      if result==None:
        log.warning("parse_time(%s)"%cmd)
      else:
        text_index=result["text_index"]
        cur_time=result["result_time"]
        success=True

    if success==False:
      # не смог распознать время:
      if cur_data["lang"]=="ru":
        await ma.send_text(room,"Не смог распознать в команде '%s' слово '%s' как предлог"%(cmd,pars[1]))
      else:
        await ma.send_text(room,"error pars cmd: '%s' at '%s' as predicate"%(cmd,pars[1]))
      return False
      

  # Время получили, устанавливаем таймер:
    #print("cur_time=",cur_time)
    #timestamp=time.mktime(cur_time)
    # TODO:
    alarm_text=""

    while text_index < len(pars):
      alarm_text+=pars[text_index]
      alarm_text+=" "
      text_index+=1
    alarm_text=alarm_text.strip()
    item={}
    item["time"]=int(cur_time)
    item["text"]=alarm_text
    cur_data["alarms"].append(item)
    # Сохраняем в файл данных:
    save_data(data)
    if cur_data["lang"]=="ru":
      return await ma.send_notice(room,"Установил напоминание на %s, с текстом: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )
    else:
      return await ma.send_notice(room,"set alarm at %s, with text: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

async def process_simple_timer_cmd(user,room,timeout_minutes):
  global client
  global log
  global data
  try:
    cur_data=data["users"][user][room]
    alarm_text="%d минут прошло"%timeout_minutes
    cur_time=time.time()+timeout_minutes*60
    item={}
    item["time"]=int(cur_time)
    item["text"]=alarm_text
    cur_data["alarms"].append(item)
    # Сохраняем в файл данных:
    save_data(data)
    if cur_data["lang"]=="ru":
      return await ma.send_notice(room,"Установил напоминание на %s, с текстом: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )
    else:
      return await ma.send_notice(room,"set alarm at %s, with text: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(cur_time)),alarm_text) )
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

async def proccess_alarms():
  global log
  global data
  try:
    log.debug("=== start ===")
    # FIXME
    html="<p><strong>Напоминаю Вам:</strong></p>\n<ul>\n"
    html+="<li>test</li>\n"
    html+="</ul>\n"
    #log.info("ret = %d"% await ma.send_html(room,html))
    



  # Проверяем уведомления:
    for user in data["users"]:
      for room in data["users"][user]:
        for item in data["users"][user][room]["alarms"]:
          alarm_timestamp=item["time"]
          alarm_text=item["text"]
          time_now=time.time()
          if alarm_timestamp < time_now:
            # Уведомляем:
            log.info("send notify to %s"%user)
            html="<p><strong>Напоминаю Вам:</strong></p>\n<ul>\n"
            html+="<li>%s</li>\n"%alarm_text
            html+="</ul>\n"
            if await ma.send_html(room,html)==True:
              data["users"][user][room]["alarms"].remove(item)
              save_data(data)
              break # выходим из текущего цикла, т.к. изменили количество в маассиве (валится в корку) - следующей проверкой проверим оставшиеся
            else:
              log.error("error send alarm at '%s' with text: '%s'"%(time.strftime("%Y.%m.%d-%T",time.localtime(alarm_timestamp)),alarm_text) )
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

