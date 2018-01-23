# coding: utf-8
import binascii
import ctypes
import datetime
import os
import shlex
import subprocess
import sys
import time
from struct import pack

import bluetooth
import serial
from model.model import *

# Linux location of serial ports (rfcomm0, rfcomm1, rfcomm2, etc)
DEFAULT_DEVICE = "/dev/rfcomm"


# Class to discover near bluetooth devices
class Discoverer(bluetooth.DeviceDiscoverer):
    def pre_inquiry(self):
        self.done = False
        self.devices = {}

    def device_discovered(self, address, device_class, rssi, name):
        if name.startswith('TSND121') and name not in self.devices:
            self.devices[name] = address

    def inquiry_complete(self):
        self.done = True


# Class to manage the connections
class RFCOMMConection():
    def __init__(self, bdaddr=None):
        self.settings = connectionSettings.select().order_by(connectionSettings.id.desc()).get()
        self.bdaddr = bdaddr
        self.channel = 1
        self.cmd_connect = "rfcomm connect"
        self.cmd_release = "rfcomm release"
        self.ser = None
        self.device = ""
        self.header = 0x9A
        self.connected = False
        self.paused = False

    # Release the given port(port=0 releases /dev/rfcomm0)
    def release(self, port):
        cmd = self.cmd_release + " " + DEFAULT_DEVICE + str(port) + "&"
        print cmd
        os.system(cmd)

    # Makes a new connection
    def connect(self):
        n = 0
        ls = "ls /dev/ | grep rfcomm"
        p = subprocess.Popen(ls, stdout=subprocess.PIPE, shell=True)
        d, err = p.communicate()

        if d != "":
            ports = d.split("\n")
            n = len(ports) - 1
        self.device = self.settings.device + str(n)

        cmd = self.cmd_connect + " " + str(self.device) + " " + str(self.bdaddr) + " " + str(self.channel) + "&"
        print cmd
        os.system(cmd)

        # wait and verify if the file was created
        cs = connectionSettings.select().order_by(connectionSettings.id.desc()).get()
        sleep = cs.conectionTime

        d1 = ""
        while sleep > 0:
            d1 = self.checkSerial(n)
            if d1 != "": break
            time.sleep(1)
            sleep = sleep - 1

        if d1 == "":
            n = -1
        return n

    def checkSerial(self, n):
        ls1 = "ls /dev/ | grep rfcomm" + str(n)
        p1 = subprocess.Popen(ls1, stdout=subprocess.PIPE, shell=True)
        d1, err1 = p1.communicate()
        return d1

    # Initializes the serial port with the action selected in the GUI
    def initDevice(self):
        try:
            self.ser = serial.Serial(port=self.device, timeout=self.settings.timeout, baudrate=self.settings.baudrate)
            print self.ser
        except Exception as detail:
            print detail
        return self.ser

    def comandSwitcher(self, action):
        # 計測開始
        mtsettings = MeasurementReservation.select().order_by(MeasurementReservation.id.desc()).get()
        cmd = mtsettings.cmd  # 0x13
        smode = mtsettings.smode  # 0x00  # start mode: 0 relative time, 1 absolute time
        syear = mtsettings.syear  # 0x00  # start year: Amount of years since 2000
        smonth = mtsettings.smonth  # 0x01  # start month
        sday = mtsettings.sday  # 0x01  # start day
        shour = mtsettings.shour  # 0x00  # start hour
        smin = mtsettings.smin  # 0x00  # start minute
        ssec = mtsettings.ssec  # 0x00  # start second
        emode = mtsettings.emode  # 0x00  # end mode: 0 relative time, 1 absolute time
        eyear = mtsettings.eyear  # 0x00  # end year: Amount of years since 2000
        emonth = mtsettings.emonth  # 0x01  # end month
        eday = mtsettings.eday  # 0x01  # end day
        ehour = mtsettings.ehour  # 0x00  # end hour
        emin = mtsettings.emin  # 0x00  # end minute
        esec = mtsettings.esec  # 0x00  # end second

        check = self.checkSum(
            [cmd, smode, syear, smonth, sday, shour, smin, ssec, emode, eyear, emonth, eday, ehour, emin, esec])

        list = [chr(self.header), chr(cmd), chr(smode), chr(syear), chr(smonth), chr(sday), chr(shour), chr(smin),
                chr(ssec), chr(emode), chr(eyear), chr(emonth), chr(eday), chr(ehour), chr(emin), chr(esec),
                chr(check)]

        # バッファクリア
        self.clearBuffer()
        self.ser.write(bytearray(list))
        str = self.ser.readline()
        if action == 1:
            self.angularVelocity()
        elif action == 2:
            self.geomagnetic()
        else:
            self.atmospheric()

    def angularVelocity(self):
        xasettings = XASettings.select().order_by(XASettings.id.desc()).get()
        # 加速度・角速度パラメータ設定
        cmd = xasettings.cmd  # 0x16
        data = xasettings.mode  # 0x01
        data1 = xasettings.dataTransmission  # 0x0A
        data2 = xasettings.dataRecording  # 0x00

        check = self.checkSum([cmd, data, data1, data2])
        list = bytearray([chr(self.header), chr(cmd), chr(data), chr(data1), chr(data2), chr(check)])
        # self.clearBuffer()
        self.ser.write(repr(list))

    def geomagnetic(self):
        gmsettings = GMSettings.select().order_by(GMSettings.id.desc()).get()
        # 加速度・角速度パラメータ設定
        cmd = gmsettings.cmd  # 0x16
        data = gmsettings.mode  # 0x01
        data1 = gmsettings.dataTransmission  # 0x0A
        data2 = gmsettings.dataRecording  # 0x00

        check = self.checkSum([cmd, data, data1, data2])
        list = bytearray([chr(self.header), chr(cmd), chr(data), chr(data1), chr(data2), chr(check)])
        # self.clearBuffer()
        self.ser.write(repr(list))

    def atmospheric(self):
        apsettings = APSettings.select().order_by(APSettings.id.desc()).get()
        # 加速度・角速度パラメータ設定
        cmd = apsettings.cmd  # 0x16
        data = apsettings.mode  # 0x01
        data1 = apsettings.dataTransmission  # 0x0A
        data2 = apsettings.dataRecording  # 0x00

        check = self.checkSum([cmd, data, data1, data2])
        list = bytearray([chr(self.header), chr(cmd), chr(data), chr(data1), chr(data2), chr(check)])
        # self.clearBuffer()
        self.ser.write(repr(list))

    def clearBuffer(self):
        # バッファクリア
        if self.ser:
            self.ser.read(1000)

    # Read the response
    def readResponse(self):

        while self.connected:
            try:
                str = self.ser.readline()
                # print repr(str)
                # 計測開始通知
                # Measurement start notification
                str = self.ser.read(1)
                # print "2"
                # print repr(str)
                # ヘッダ検索
                # Retrieve header
                while ord(str) != 0x9A:
                    str = self.ser.read(1)

                # コマンド取得
                # Retrieve command
                str = self.ser.read(1)
                # print repr(str)

                # 加速度角速度計測データ通知のみ処理する
                # Acceleration angular velocity measurement data notification
                if ord(str) == 0x80:
                    yield self.angularVelocityResponse()

            except Exception as e:
                print e
                self.connected = False
                yield None
                return

    def angularVelocityResponse(self):
        data = []
        # タイムスタンプ
        # timestamp
        ts = ord(self.ser.read(1))
        ts += ord(self.ser.read(1)) << 8
        ts += ord(self.ser.read(1)) << 16
        ts += ord(self.ser.read(1)) << 24
        # print datetime.date.fromtimestamp(ts)

        # 加速度X
        # Acceleration X
        data1 = self.ser.read(1)
        data2 = self.ser.read(1)
        data3 = self.ser.read(1)

        # 3byteの値を4byteのint型としてマイナスのハンドリング
        if ord(data3) & 0x80:
            data4 = "\xFF"
        else:
            data4 = "\x00"

        data.append(binascii.b2a_hex(data1))
        data.append(binascii.b2a_hex(data2))
        data.append(binascii.b2a_hex(data3))
        data.append(binascii.b2a_hex(data4))

        # エンディアン変換
        # Endian conversion
        accx = ord(data1)
        accx += ord(data2) << 8
        accx += ord(data3) << 16
        accx += ord(data4) << 24

        data.append(ctypes.c_int(accx).value)
        data.append(time.time())
        if self.checkSerial(self.device[-1:]) == "":
            self.connected = False
            return None

        return ctypes.c_int(accx).value

    def setTime(self, year, month, day, hour, min, sec, ms1, ms2):
        # '\x9a\x8f\x01\x14' ERROR
        cmd = 0x11
        year = year - 2000
        ms1 = (ms1 // 1000) & 0xFF
        ms2 = ((ms2 // 1000) >> 8) & 0xFF

        check = self.checkSum([cmd, year, month, day, hour, min, sec, ms1, ms2])

        list = bytearray(
            [chr(self.header), chr(cmd), chr(year), chr(month), chr(day), chr(hour), chr(min), chr(sec), chr(ms1),
             chr(ms2), chr(check)])

        self.clearBuffer()

        self.ser.write(list)
        print repr(self.ser.readline())

    def stopMeassuring(self):
        cmd = 0x15
        data = 0x00
        check = self.checkSum([cmd, data])
        list = bytearray([chr(self.header), chr(cmd), chr(data), chr(check)])

        self.clearBuffer()
        self.ser.write(list)
        print repr(self.ser.readline())

    def batteryStatus(self):
        cmd = 0x3B
        data = 0x00
        info = {}
        check = self.checkSum([cmd, data])
        list = bytearray([chr(self.header), chr(cmd), chr(data), chr(check)])

        self.clearBuffer()
        self.ser.write(list)
        # '\x9a\xbb\x99\x01d\xdd'
        # retrieve header
        str = self.ser.read(1)
        while ord(str) != 0x9A:
            str = self.ser.read(1)
        # response command
        str = self.ser.read(1)
        if ord(str) == 0xbb:
            info["voltage"] = binascii.b2a_hex(self.ser.read(2))
            info["percent"] = binascii.b2a_hex(self.ser.read(1))
        return info

    def timeAcq(self):
        cmd = 0x12
        data = 0x00
        check = self.checkSum([cmd, data])
        list = bytearray([chr(self.header), chr(cmd), chr(data), chr(check)])

        self.clearBuffer()
        self.ser.write(list)

        # retrieve header
        str = self.ser.read(1)
        while ord(str) != 0x9A:
            str = self.ser.read(1)
        # response command
        str = self.ser.read(1)
        if ord(str) == 0x92:
            year = binascii.b2a_hex(self.ser.read(1))
            month = binascii.b2a_hex(self.ser.read(1))
            day = binascii.b2a_hex(self.ser.read(1))
            min = binascii.b2a_hex(self.ser.read(1))
            sec = int(binascii.b2a_hex(self.ser.read(1)), 16)

            print year
            print month
            print day
            print min
            print sec

    def getInfo(self):
        # "\x9a\x90AP06120208\x00\x07\x80K|'\x12\x11\x06\x17TSND121\x00\x00\x00\xae"
        cmd = 0x10
        data = 0x00

        info = {}
        check = self.checkSum([cmd, data])
        list = bytearray([chr(self.header), chr(cmd), chr(data), chr(check)])

        self.clearBuffer()
        self.ser.write(list)
        # retrieve header
        str = self.ser.read(1)
        while ord(str) != 0x9A:
            str = self.ser.read(1)
        # response command
        str = self.ser.read(1)
        if ord(str) == 0x90:
            info["sn"] = self.ser.read(10)
            info["mac"] = binascii.b2a_hex(self.ser.read(6))
            info["swv"] = binascii.b2a_hex(self.ser.read(4))
            info["name"] = ""
            str = self.ser.read(1)
            while ord(str) != 0x00:
                info["name"] += str
                str = self.ser.read(1)
        return info

    def checkSum(self, params):
        check = self.header ^ params[0]
        for idx, i in enumerate(params):
            if idx != 0:
                check = check ^ i
        return check
