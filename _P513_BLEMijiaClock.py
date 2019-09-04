#!/usr/bin/env python3
#############################################################################
################### BLE Mijia Clock plugin for RPIEasy ######################
#############################################################################
#
# Xiaomi Mijia LYWSD02 Bluetooth Clock+Temperature/Humidity Sensor plugin.
# Can be used when BLE compatible Bluetooth dongle, and BluePy is installed.
#
# Based on:
#  https://github.com/h4/lywsd02
#
# Copyright (C) 2019 by Alexander Nagy - https://bitekmindenhol.blog.hu/
#
import plugin
import webserver
import rpieGlobals
import rpieTime
import misc
from bluepy import btle
import threading
import time
import binascii

UUID_UNITS = 'EBE0CCBE-7A0A-4B0C-8A1A-6FF2997DA3A6'     # 0x00 - F, 0x01 - C    READ WRITE
UUID_DATA = 'EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6'      # 3 bytes               READ NOTIFY
UUID_BATTERY = 'EBE0CCC4-7A0A-4B0C-8A1A-6FF2997DA3A6'   # 1 byte                READ
TEMP_HUM_READ_HANDLE = 0x3c

class Plugin(plugin.PluginProto):
 PLUGIN_ID = 513
 PLUGIN_NAME = "Environment - BLE Xiaomi LYWSD02 Clock&Hygrometer (EXPERIMENTAL)"
 PLUGIN_VALUENAME1 = "Temperature"
 PLUGIN_VALUENAME2 = "Humidity"
 PLUGIN_VALUENAME3 = "Battery"

 def __init__(self,taskindex): # general init
  plugin.PluginProto.__init__(self,taskindex)
  self.dtype = rpieGlobals.DEVICE_TYPE_BLE
  self.vtype = rpieGlobals.SENSOR_TYPE_TEMP_HUM
  self.valuecount = 2
  self.senddataoption = True
  self.recdataoption = False
  self.timeroption = True
  self.timeroptional = False
  self.connected = False
  self.formulaoption = True
  self.BLEPeripheral = False
  self.cproc = False
  self.waitnotifications = False
  self.conninprogress = False
  self.readinprogress = False
  self.battery = 0
  self.lastbatteryreq = 0
#  self.lastread = 0
  self.preread = 3000
  self._lastdataservetime = 0
  self._nextdataservetime = 0
  self.TARR = []
  self.HARR = []
  self.failures = 0

 def webform_load(self): # create html page for settings
  webserver.addFormTextBox("Device Address","plugin_513_addr",str(self.taskdevicepluginconfig[0]),20)
  webserver.addFormNote("Enable blueetooth then <a href='blescanner'>scan LYWSD02 address</a> first.")
  webserver.addFormCheckBox("Add Battery value for non-Domoticz system","plugin_513_bat",self.taskdevicepluginconfig[1])
  return True

 def webform_save(self,params): # process settings post reply
  self.taskdevicepluginconfig[0] = str(webserver.arg("plugin_513_addr",params)).strip()
  self.taskdevicepluginconfig[1] = (webserver.arg("plugin_513_bat",params)=="on")
  if self.taskdevicepluginconfig[1]:
   self.valuecount = 3
   self.vtype = rpieGlobals.SENSOR_TYPE_TRIPLE
  else:
   self.valuecount = 2
   self.vtype = rpieGlobals.SENSOR_TYPE_TEMP_HUM
  self.plugin_init()
  return True

 def plugin_init(self,enableplugin=None):
  plugin.PluginProto.plugin_init(self,enableplugin)
  self.readinprogress = False
  self.conninprogress = False
  self.waitnotifications = False
  self.connected = False
  self.TARR = []
  self.HARR = []
  self.uservar[0] = 0
  self.uservar[1] = 0
  if self.enabled:
   self.timer1s = True
   self.battery = -1
   self._nextdataservetime = rpieTime.millis()-self.preread
   self._lastdataservetime = 0
#   self.lastread = 0
   self.failures = 0
  else:
   self.timer1s = False
 
 def timer_once_per_second(self):
  if self.enabled:
   if self._nextdataservetime-rpieTime.millis()<=self.preread:
    if self.conninprogress==False and self.connected==False:
     self.waitnotifications = False
     if len(self.taskdevicepluginconfig[0])>10:
      self.cproc = threading.Thread(target=self.connectproc)
      self.cproc.daemon = True
      self.cproc.start()
   return self.timer1s

 def plugin_read(self):
   result = False
#   print("read",self.connected)
   if self.enabled:
#    print(self.TARR)
#    if (rpieTime.millis()-self.lastread)<=(self.preread*2):
#     print(self.lastread,self.preread)
     if len(self.TARR)>0 and len(self.HARR)>0:
      self.get_battery_value()
      if self.battery==-1:
       self.get_battery_value()
      self.set_value(1,self.TARR[-1],False)
      if self.taskdevicepluginconfig[1]:
       self.set_value(2,self.HARR[-1],False)
       self.set_value(3,self.battery,False,susebattery=self.battery)
      else:
       self.set_value(2,self.HARR[-1],False,susebattery=self.battery)
      self.plugin_senddata()
      if self.interval>10:
       self.disconnect()
#      print("b:",self.battery)
      self.TARR = []
      self.HARR = []
      self._lastdataservetime = rpieTime.millis()
      self._nextdataservetime = self._lastdataservetime + (self.interval*1000) - self.preread
      self.failures = 0
     else:
      self.isconnected()

 def connectproc(self):
   self.conninprogress = True
   prevstate = self.connected
   try:
    misc.addLog(rpieGlobals.LOG_LEVEL_DEBUG,"BLE connection initiated to "+str(self.taskdevicepluginconfig[0]))
    self.BLEPeripheral = btle.Peripheral(str(self.taskdevicepluginconfig[0]))
    self.connected = True
    self.failures = 0
    self.BLEPeripheral.setDelegate( Lywsd02Delegate(self.callbackfunc) )
   except:
    self.connected = False
   self.conninprogress = False
   self.isconnected()
   if self.connected==False:
    misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"BLE connection failed "+str(self.taskdevicepluginconfig[0]))
    self.failures =  self.failures +1
    if self.failures>5:
     self._nextdataservetime = rpieTime.millis()+(self.interval*5000)
     self._lastdataservetime = self._nextdataservetime
    return False
   else:
    misc.addLog(rpieGlobals.LOG_LEVEL_DEBUG,"BLE connected to "+str(self.taskdevicepluginconfig[0]))
    self.waitnotifications = True
    self.get_battery_value()
    rpieTime.addsystemtimer(3,self.isconnected,[-1])

 def request_temp_hum_value(self,d=None):
  res = False
  try:
   ch = self.BLEPeripheral.getCharacteristics(uuid=UUID_DATA)[0]
   desc = ch.getDescriptors(forUUID=0x2902)[0]
   desc.write(0x01.to_bytes(2, byteorder="little"), withResponse=True)
   res = True
  except Exception as e:
   res = False
   self.failures+=1
  return res

 def isconnected(self,d=None):
  if self.connected:
   self.connected = self.request_temp_hum_value()
  return self.connected

 def get_battery_value(self):
  if ((time.time()-self.lastbatteryreq)>600) or (self.battery<=0):
   battery = 0
   try:
    ch = self.BLEPeripheral.getCharacteristics(uuid=UUID_BATTERY)[0]
    battery = ch.read()
    self.lastbatteryreq = time.time()
   except Exception as e:
    pass
   try:
    if battery:
     self.battery = ord(battery)
   except Exception as e:
    pass
  return self.battery

 def callbackfunc(self,temp=None,hum=None):
#  print("cb",temp,hum)
  if self.enabled:
   self.TARR.append(temp)
   self.HARR.append(hum)
#   self.lastread = rpieTime.millis()

 def disconnect(self):
#  print("disconn")
  self.connected = False
  self.waitnotifications = False
  if self.enabled:
   try:
    self.BLEPeripheral.disconnect()
    self.cproc._stop()
   except:
    pass

 def __del__(self):
  self.disconnect()

 def plugin_exit(self):
  self.disconnect()

# def __exit__(self,type,value,traceback):
#  self.__del__()

class Lywsd02Delegate(btle.DefaultDelegate):
 def __init__(self,callback):
   self.callback = callback
   btle.DefaultDelegate.__init__(self)

 def handleNotification(self, cHandle, data):
   if (cHandle == TEMP_HUM_READ_HANDLE) and data is not None:
    temp = None
    hum = None
    try:
     ttemp = data[:2]
     hum  = data[2]
     temp = float(struct.unpack('H', ttemp)[0] / 100)
    except Exception as e:
     print("Notification error: ",e)
#    print(temp,hum) # DEBUG
    self.callback(temp,hum)

