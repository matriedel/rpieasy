#!/usr/bin/env python3
#############################################################################
#################### ADS1015/ADS1115 plugin for RPIEasy #####################
#############################################################################
#
# Copyright (C) 2018-2019 by Alexander Nagy - https://bitekmindenhol.blog.hu/
#
import plugin
import webserver
import rpieGlobals
import rpieTime
import misc
import Adafruit_ADS1x15 as ADS
import gpios

class Plugin(plugin.PluginProto):
 PLUGIN_ID = 25
 PLUGIN_NAME = "Analog input - ADS1x15"
 PLUGIN_VALUENAME1 = "Analog"

 def __init__(self,taskindex): # general init
  plugin.PluginProto.__init__(self,taskindex)
  self.dtype = rpieGlobals.DEVICE_TYPE_I2C
  self.vtype = rpieGlobals.SENSOR_TYPE_SINGLE
  self.ports = 0
  self.readinprogress = 0
  self.valuecount = 1
  self.senddataoption = True
  self.timeroption = True
  self.timeroptional = True
  self.formulaoption = True
  self.adc = None

 def plugin_init(self,enableplugin=None):
  plugin.PluginProto.plugin_init(self,enableplugin)
  if self.enabled:
   i2cport = -1
   try:
    for i in range(0,2):
     if gpios.HWPorts.is_i2c_usable(i) and gpios.HWPorts.is_i2c_enabled(i):
      i2cport = i
      break
   except:
    i2cport = -1
   if i2cport>-1:
    if int(self.taskdevicepluginconfig[0]) in [10,11]:
     try:
      if int(self.taskdevicepluginconfig[0])==10:
       self.adc = ADS.ADS1015(address=int(self.taskdevicepluginconfig[1]),busnum=i2cport)
      else:
       self.adc = ADS.ADS1115(address=int(self.taskdevicepluginconfig[1]),busnum=i2cport)
     except Exception as e:
      misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"ADS can not be initialized! "+str(e))
      self.enabled = False
    else:
     self.initialized = False

 def webform_load(self): # create html page for settings
  choice1 = self.taskdevicepluginconfig[0]
  options = ["ADS1015","ADS1115"]
  optionvalues = [10,11]
  webserver.addFormSelector("Type","plugin_025_type",2,options,optionvalues,None,int(choice1))
  choice2 = self.taskdevicepluginconfig[1]
  options = ["0x48","0x49","0x4A","0x4B"]
  optionvalues = [0x48,0x49,0x4a,0x4b]
  webserver.addFormSelector("Address","plugin_025_addr",4,options,optionvalues,None,int(choice2))
  webserver.addFormNote("Enable <a href='pinout'>I2C bus</a> first, than <a href='i2cscanner'>search for the used address</a>!")
  choice3 = self.taskdevicepluginconfig[2]
  options =      ["2/3","1","2","4","8","16"]
  optionvalues = [(2/3),1,2,4,8,16]
  webserver.addFormSelector("Gain","plugin_025_gain",len(optionvalues),options,optionvalues,None,float(choice3))
  choice4 = self.taskdevicepluginconfig[3]
  options = ["A0","A1","A2","A3"]
  optionvalues = [0,1,2,3]
  webserver.addFormSelector("Analog pin","plugin_025_apin",4,options,optionvalues,None,int(choice4))
  return True

 def webform_save(self,params): # process settings post reply
   par = webserver.arg("plugin_025_type",params)
   if par == "":
    par = 0
   self.taskdevicepluginconfig[0] = int(par)

   par = webserver.arg("plugin_025_addr",params)
   if par == "":
    par = 0
   self.taskdevicepluginconfig[1] = int(par)

   par = webserver.arg("plugin_025_gain",params)
   if par == "":
    par = 1
   self.taskdevicepluginconfig[2] = float(par)

   par = webserver.arg("plugin_025_apin",params)
   if par == "":
    par = 0
   self.taskdevicepluginconfig[3] = int(par)
   self.plugin_init()
   return True

 def plugin_read(self): # deal with data processing at specified time interval
  result = False
  if self.initialized and self.readinprogress==0 and self.enabled:
   self.readinprogress = 1
   value = self.p025_get_value()
   if value != -1:
    self.set_value(1,value,False)
    self.plugin_senddata()
   else:
    misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"ADS1x15 read failed!")
   self._lastdataservetime = rpieTime.millis()
   result = True
   self.readinprogress = 0
  return result

 def p025_get_value(self):
  val = -1
  try:
   val = self.adc.read_adc(self.taskdevicepluginconfig[3],gain=self.taskdevicepluginconfig[2])
  except Exception as e:
   val = -1
  return val