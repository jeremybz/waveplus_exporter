# MIT License
#
# Copyright (c) 2018 Airthings AS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# https://airthings.com

# ===============================
# Module import dependencies
# ===============================

import sys
import time
import struct
import logging
import argparse
import tableprint

from threading import Lock
from bluepy.btle import UUID, Peripheral, Scanner, DefaultDelegate
from prometheus_client import start_http_server, Metric, Summary, REGISTRY

# ===================================
# Class Sensor and sensor definitions
# ===================================
NUMBER_OF_SENSORS               = 7
SENSOR_IDX_HUMIDITY             = 0
SENSOR_IDX_RADON_SHORT_TERM_AVG = 1
SENSOR_IDX_RADON_LONG_TERM_AVG  = 2
SENSOR_IDX_TEMPERATURE          = 3
SENSOR_IDX_REL_ATM_PRESSURE     = 4
SENSOR_IDX_CO2_LVL              = 5
SENSOR_IDX_VOC_LVL              = 6

# ===============================
# set up logging
# ===============================
log = logging.getLogger('waveplus-exporter')
log.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
log.addHandler(ch)

# ===============================
# parse args
# ===============================
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('--port', nargs='?', type=int, help='The TCP port to listen on', default=9744)
parser.add_argument('--bind', nargs='?', help='The interface/IP to bind to', default='0.0.0.0')
parser.add_argument('--periodseconds', nargs='?', type=int, help='number of seconds to wait between sampling', default='60')
parser.add_argument('--serialnumber', required=True, type=int, nargs='?')

args = parser.parse_args()
SerialNumber = args.serialnumber
SamplePeriod = args.periodseconds

# ====================================
# Utility functions for WavePlus class
# ====================================

def parseSerialNumber(ManuDataHexStr):
    if (ManuDataHexStr == "None"):
        SN = "Unknown"
    else:
        ManuData = bytearray.fromhex(ManuDataHexStr)

        if (((ManuData[1] << 8) | ManuData[0]) == 0x0334):
            SN  =  ManuData[2]
            SN |= (ManuData[3] << 8)
            SN |= (ManuData[4] << 16)
            SN |= (ManuData[5] << 24)
        else:
            SN = "Unknown"
    return SN

# ===============================
# Class WavePlus
# ===============================

class WavePlus():
    def __init__(self, SerialNumber):
        self._lock         = Lock()
        self.periph        = None
        self.curr_val_char = None
        self.MacAddr       = None
        self.SN            = SerialNumber
        self.uuid          = UUID("b42e2a68-ade7-11e4-89d3-123b93f75cba")

    def connect(self):
        # Auto-discover device on first connection
        if (self.MacAddr is None):
            scanner     = Scanner().withDelegate(DefaultDelegate())
            searchCount = 0
            while self.MacAddr is None and searchCount < 50:
                devices      = scanner.scan(0.1) # 0.1 seconds scan period
                searchCount += 1
                for dev in devices:
                    ManuData = dev.getValueText(255)
                    SN = parseSerialNumber(ManuData)
                    if (SN == self.SN):
                        self.MacAddr = dev.addr # exits the while loop on next conditional check
                        break # exit for loop

            if (self.MacAddr is None):
                log.error( "ERROR: Could not find device.")
                log.error( "Device serial number: %s" %(self.SN) )
                log.error( "GUIDE: (1) Please verify the serial number." )
                log.error( "       (2) Ensure that the device is advertising." )
                log.error( "       (3) Retry connection." )
                sys.exit(1)

        # Connect to device
        if (self.periph is None):
            self.periph = Peripheral(self.MacAddr)
        if (self.curr_val_char is None):
            self.curr_val_char = self.periph.getCharacteristics(uuid=self.uuid)[0]

    def read(self):
        if (self.curr_val_char is None):
            log.error( "ERROR: Devices are not connected." )
            sys.exit(1)
        rawdata = self.curr_val_char.read()
        rawdata = struct.unpack('BBBBHHHHHHHH', rawdata)
        sensors = Sensors()
        sensors.set(rawdata)
        return sensors

    def disconnect(self):
        if self.periph is not None:
            self.periph.disconnect()
            self.periph = None
            self.curr_val_char = None

    def collect(self):
        with self._lock:
          self.connect()
          sensors = self.read()

          humidity     = str(sensors.getValue(SENSOR_IDX_HUMIDITY))
          radon_st_avg = str(sensors.getValue(SENSOR_IDX_RADON_SHORT_TERM_AVG))
          radon_lt_avg = str(sensors.getValue(SENSOR_IDX_RADON_LONG_TERM_AVG))
          temperature  = str(sensors.getValue(SENSOR_IDX_TEMPERATURE))
          pressure     = str(sensors.getValue(SENSOR_IDX_REL_ATM_PRESSURE))
          CO2_lvl      = str(sensors.getValue(SENSOR_IDX_CO2_LVL))
          VOC_lvl      = str(sensors.getValue(SENSOR_IDX_VOC_LVL))

          metric = Metric('waveplus', 'airthings waveplus sensor values', 'gauge')
          metric.add_sample('humidity_percent', value=humidity, labels={})
          metric.add_sample('radon_short_term_avg_becquerels', value=radon_st_avg, labels={})
          metric.add_sample('radon_long_term_avg_becquerels', value=radon_lt_avg, labels={})
          metric.add_sample('temperature_celsius', value=temperature, labels={})
          metric.add_sample('pressure_pascal', value=pressure, labels={})
          metric.add_sample('carbondioxide_ppm', value=CO2_lvl, labels={})
          metric.add_sample('voc_ppb', value=VOC_lvl, labels={})

          self.disconnect()
          yield metric

class Sensors():
    def __init__(self):
        self.sensor_version = None
        self.sensor_data    = [None]*NUMBER_OF_SENSORS
        self.sensor_units   = ["%rH", "Bq/m3", "Bq/m3", "degC", "hPa", "ppm", "ppb"]

    def set(self, rawData):
        self.sensor_version = rawData[0]
        if (self.sensor_version == 1):
            self.sensor_data[SENSOR_IDX_HUMIDITY]             = rawData[1]/2.0
            self.sensor_data[SENSOR_IDX_RADON_SHORT_TERM_AVG] = self.conv2radon(rawData[4])
            self.sensor_data[SENSOR_IDX_RADON_LONG_TERM_AVG]  = self.conv2radon(rawData[5])
            self.sensor_data[SENSOR_IDX_TEMPERATURE]          = rawData[6]/100.0
            self.sensor_data[SENSOR_IDX_REL_ATM_PRESSURE]     = rawData[7]/50.0
            self.sensor_data[SENSOR_IDX_CO2_LVL]              = rawData[8]*1.0
            self.sensor_data[SENSOR_IDX_VOC_LVL]              = rawData[9]*1.0
        else:
            log.error( "ERROR: Unknown sensor version." )
            log.error( "GUIDE: Contact Airthings for support." )
            sys.exit(1)

    def conv2radon(self, radon_raw):
        radon = "N/A" # Either invalid measurement, or not available
        if 0 <= radon_raw <= 16383:
            radon  = radon_raw
        return radon

    def getValue(self, sensor_index):
        return self.sensor_data[sensor_index]

    def getUnit(self, sensor_index):
        return self.sensor_units[sensor_index]

try:
    waveplus = WavePlus(SerialNumber)
    REGISTRY.register(waveplus)

    start_http_server(int(args.port), addr=args.bind)
    log.info('listening on http://%s:%d/metrics', args.bind, int(args.port))

    while True:
        time.sleep(SamplePeriod)

finally:
    waveplus.disconnect()
