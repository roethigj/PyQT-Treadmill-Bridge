from PySide6.QtBluetooth import QLowEnergyCharacteristic

from PySide6.QtCore import QByteArray
import struct

treadmill_values = struct.pack('<BBHHBHHHHBBH', 140, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ftms_status_value = struct.pack('<B', 0)
ftms_status_value_old = struct.pack('<B', 0)
training_status_value = struct.pack('<B', 0)
training_status_value_old = struct.pack('<B', 0)
ftms_control_value = [False, True, struct.pack('<B', 0)]


services = {0x180A: {0x2A29: [QByteArray.fromStdString("BLE_Bridge"),
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2A24: [QByteArray.fromStdString("2"),
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2A25: [QByteArray.fromStdString("1234"),
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2A27: [QByteArray.fromStdString("1.0"),
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2A26: [QByteArray.fromStdString("1.0"),
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2A28: [QByteArray.fromStdString("1.0"),
                              QLowEnergyCharacteristic.PropertyType.Read]
                     },
            0x1826: {0x2ACC: [QByteArray(b'\x0D\x16\x00\x00'    # 1011000001101000
                                         b'\x03\x00\x00\x00'),  # 1100000000000000
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2ACD: [QByteArray(b'\x8C\x05'               # 1000 110000000101 0011 0001 1010 0000 
                                         b'\x00\x00\x00\x00\x00\x00\x00\x00'
                                         b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'),
                              QLowEnergyCharacteristic.PropertyType.Notify],
                     0x2AD4: [QByteArray(b'\x64\x00\x40\x06\x0A\x00'),      # speed range
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2AD5: [QByteArray(b'\x00\x00\x64\x00\x05\x00'),      # incline range
                              QLowEnergyCharacteristic.PropertyType.Read],
                     0x2ADA: [QByteArray(b'\x00'),                          # ftms status
                              QLowEnergyCharacteristic.PropertyType.Notify],
                     0x2AD3: [QByteArray(b'\x01\x00'),                      # training status
                              QLowEnergyCharacteristic.PropertyType.Read |
                              QLowEnergyCharacteristic.PropertyType.Notify],
                     0x2AD9: [QByteArray(b'\x00'),                          # control point
                              QLowEnergyCharacteristic.PropertyType.Write]
                     }
            }
