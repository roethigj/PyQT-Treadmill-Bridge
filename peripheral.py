from __future__ import annotations

from PySide6.QtBluetooth import (QBluetoothUuid, QLowEnergyAdvertisingData,
                                 QLowEnergyAdvertisingParameters,
                                 QLowEnergyCharacteristic,
                                 QLowEnergyCharacteristicData,
                                 QLowEnergyController,
                                 QLowEnergyServiceData,
                                 QLowEnergyConnectionParameters)
from PySide6.QtCore import QByteArray, QTimer, Signal, QThread

from qt_ftms import services as ftms_services


class WriteEmitter(QThread):
    control_point = Signal(bytearray)
    peripheral_output = Signal(str)
    peripheral_co_signal = Signal(bool)

    def __init__(self, parent=None,
                 runner=False):
        super(WriteEmitter, self).__init__(parent)
        self.runner = runner

    def run(self):
        while self.runner:
            QThread.msleep(200)

    def emit_data(self, data):
        self.control_point.emit(data)

    def emit_peripheral_co_signal(self, data):
        self.peripheral_co_signal.emit(data)

    def emit_peripheral_output(self, data):
        output = "Peripheral: " + data
        self.peripheral_output.emit(output)

    def stop(self):
        self.runner = False


class FtmsPeripheral:
    control_point = Signal(bytearray)

    def __init__(self, local_device=None):
        super().__init__()
        self.advertising_data = QLowEnergyAdvertisingData()
        self.advertising_data.setDiscoverability(
            QLowEnergyAdvertisingData.Discoverability.DiscoverabilityGeneral)  # noqa: E501
        self.advertising_data.setIncludePowerLevel(True)
        self.advertising_data.setLocalName("BLE_Bridge")
        self.advertising_data.setServices((QBluetoothUuid(0x180A), QBluetoothUuid(0x1826)))
        self.local_device = local_device
        self.le_controller = QLowEnergyController.createPeripheral(self.local_device)
        self.le_controller.disconnected.connect(self.reconnect)
        self.le_controller.connected.connect(self.connected)
        self.le_controller.stateChanged.connect(self.connected)

        self.connection_parameters = QLowEnergyConnectionParameters()
        self.connection_parameters.setIntervalRange(7.5, 200)
        self.connection_parameters.setLatency(10)
        self.connection_parameters.setSupervisionTimeout(4500)

        self.ftms_value = QByteArray(b'\x8C\x05'  # 1000 110000000101 0011 0001 1010 0000 
                                     b'\x00\x00\x00\x00\x00\x00\x00\x00'
                                     b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        self.ftms_status = QByteArray(b'\x00')
        self.training_status = QByteArray(b'\x02\x01')
        self.emitter = WriteEmitter(parent=None, runner=True)

        self.peripheral_connected = False

        self.notification_timer = QTimer()

        self.services = []
        for s_uuid, characters in ftms_services.items():
            self.service_data = QLowEnergyServiceData()
            self.service_data.setType(QLowEnergyServiceData.ServiceType.ServiceTypePrimary)
            self.service_data.setUuid(QBluetoothUuid(s_uuid))
            for c_uuid, prop in characters.items():
                self.char_data = QLowEnergyCharacteristicData()
                self.char_data.setUuid(QBluetoothUuid(c_uuid))
                self.char_data.setValue(prop[0])
                self.char_data.setProperties(prop[1])
                self.service_data.addCharacteristic(self.char_data)
            self.service_cb = self.le_controller.addService(self.service_data)
            self.service_cb.characteristicChanged.connect(self.write_cb)
            self.services.append(self.service_cb)

        self.notification_timer.timeout.connect(self.notification_provider)
        self.notification_timer.start(500)

    def run(self):
        self.le_controller.startAdvertising(QLowEnergyAdvertisingParameters(),
                                            self.advertising_data, self.advertising_data)
        self.emitter.start()

    def connected(self, data):
        print("State changed", data)
        if data == QLowEnergyController.ControllerState.ConnectedState:
            self.peripheral_connected = True
            self.emitter.emit_peripheral_output("Connected.")
        elif data == QLowEnergyController.ControllerState.UnconnectedState:
            self.peripheral_connected = False
            self.emitter.emit_peripheral_co_signal(False)

    def reconnect(self):
        # service = le_controller.addService(service_data)
        self.emitter.emit_peripheral_output("Connection lost.")
        self.peripheral_connected = False
        self.emitter.emit_peripheral_co_signal(False)

    def notification_provider(self):
        for service in self.services:
            for characteristic in service.characteristics():
                if QLowEnergyCharacteristic.PropertyType.Notify in characteristic.properties():
                    if characteristic.uuid() == QBluetoothUuid(0x2ACD):     # treadmill data
                        service.writeCharacteristic(characteristic, self.ftms_value)
                    elif characteristic.uuid() == QBluetoothUuid(0x2ADA):   # ftms status
                        service.writeCharacteristic(characteristic, self.ftms_status)
                    elif characteristic.uuid() == QBluetoothUuid(0x2AD3):   # training status
                        service.writeCharacteristic(characteristic, self.training_status)
                    else:
                        pass

    def write_cb(self, char, value):
        self.emitter.emit_data(value)

    def stop(self):
        self.emitter.stop()
        self.le_controller.stopAdvertising()
        self.le_controller.disconnectFromDevice()
