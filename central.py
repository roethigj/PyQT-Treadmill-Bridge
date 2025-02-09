import time

from PySide6.QtBluetooth import (QBluetoothUuid,
                                 QBluetoothAddress,
                                 QLowEnergyController,
                                 QLowEnergyDescriptor,
                                 QLowEnergyService,

                                 QBluetoothDeviceDiscoveryAgent,
                                 QLowEnergyConnectionParameters)
from PySide6.QtCore import QByteArray, Signal, QThread, QLoggingCategory


class WriteEmitter(QThread):
    ftms_td_signal = Signal(bytearray)
    ftms_st_signal = Signal(bytearray)
    ftms_ts_signal = Signal(bytearray)
    ftms_co_signal = Signal(bool)
    central_output = Signal(str)

    def __init__(self, parent=None,
                 runner=False):
        super(WriteEmitter, self).__init__(parent)
        self.runner = runner

    def run(self):
        while self.runner:
            QThread.msleep(200)
            # pass

    def emit_ftms_td_signal(self, data):
        self.ftms_td_signal.emit(data)

    def emit_ftms_st_signal(self, data):
        self.ftms_st_signal.emit(data)

    def emit_ftms_ts_signal(self, data):
        self.ftms_ts_signal.emit(data)

    def emit_ftms_co_signal(self, data):
        self.ftms_co_signal.emit(data)

    def emit_central_output(self, data):
        output = "Central: " + data
        self.central_output.emit(output)

    def stop(self):
        self.runner = False

class BleCentral:
    QLoggingCategory.setFilterRules("qt.bluetooth* = true")

    def __init__(self, local_device=None, **kwargs):
        super(BleCentral, self).__init__()
        self.blacklist_address = kwargs.get('blacklist_address', None)
        self.remote_devices = []
        self.ftms_device = ""
        self.local_device = local_device

        self.m_control = None
        self.m_service = None
        self.m_notificationDesc = QLowEnergyDescriptor()
        self.m_currentDevice = None
        self.m_foundFtmsService = False

        self.ftms_data_char = None
        self.ftms_status_char = None
        self.training_status_char = None
        self.control_point_char = None

        self.m_addressType = QLowEnergyController.RemoteAddressType.RandomAddress

        self.device_discovery_agent = QBluetoothDeviceDiscoveryAgent(self.local_device)

        self.connection_parameters = QLowEnergyConnectionParameters()
        self.connection_parameters.setIntervalRange(7.5, 200)
        self.connection_parameters.setLatency(10)
        self.connection_parameters.setSupervisionTimeout(4500)

        self.emitter = WriteEmitter(parent=None, runner=True)

    def run(self, local_device=None, **kwargs):
        # self.device_handler.set_device(None)
        self.emitter.start()
        self.device_discovery_agent = QBluetoothDeviceDiscoveryAgent(self.local_device)
        self.device_discovery_agent.setLowEnergyDiscoveryTimeout(4000)
        self.device_discovery_agent.deviceDiscovered.connect(self.add_device)
        self.device_discovery_agent.finished.connect(self.scan_finished)
        self.device_discovery_agent.errorOccurred.connect(self.error_occurred)

        self.device_discovery_agent.start(QBluetoothDeviceDiscoveryAgent.LowEnergyMethod)

    def error_occurred(self, error):
        self.emitter.emit_central_output(f"Discovery Error occurred: {error} - {self.device_discovery_agent.errorString()}")

    def add_device(self, device):
        if QBluetoothAddress(device.address()) == QBluetoothAddress(self.blacklist_address):
            return
        self.remote_devices.append(device)

        for services in device.serviceUuids():
            if services == QBluetoothUuid(0x1826):
                self.device_discovery_agent.stop()
                self.scan_finished()

    def scan_finished(self):
        self.device_discovery_agent.stop()
        print("Scan finished")
        ftms_found = False
        if self.remote_devices:
            print(f"Found BT devices: {len(self.remote_devices)}")
            for device in self.remote_devices:
                print(f"d {device.address()} b {self.blacklist_address}")
                for services in device.serviceUuids():
                    if services == QBluetoothUuid(0x1826):
                        self.connect_to_service(device.address())
                        ftms_found = True
            if not ftms_found:
                self.emitter.emit_central_output("FTMS device not found.")
                self.emitter.emit_ftms_co_signal(False)
        else:
            self.emitter.emit_central_output("No BT devices found.")

    def connect_to_service(self, address):
        # self.device_discovery_agent.stop()

        current_device = None
        for entry in self.remote_devices:
            device = entry

            if device and device.address() == address:
                current_device = device
                break

        if current_device:
            self.set_device(current_device)

    def set_device(self, device):
        print("Setting device...")
        self.m_currentDevice = device

        # Disconnect and delete old connection
        if self.m_control:
            self.m_control.disconnectFromDevice()
            self.m_control = None

        # Create new controller and connect it if device available
        if self.m_currentDevice:

            # Make connections
            # [Connect-Signals-1]
            print(self.m_currentDevice.address())
            self.m_control = QLowEnergyController.createCentral(self.m_currentDevice, self.local_device)
            # [Connect-Signals-1]
            self.m_control.setRemoteAddressType(self.m_addressType)

            self.m_control.serviceDiscovered.connect(self.service_discovered)
            self.m_control.discoveryFinished.connect(self.service_scan_done)

            self.m_control.connected.connect(self.controller_connected)
            self.m_control.disconnected.connect(self.controller_disconnected)
            self.m_control.errorOccurred.connect(self.error_occurred)
            # Connect
            if self.m_control.state() == QLowEnergyController.UnconnectedState:
                self.m_control.connectToDevice()
                self.emitter.emit_central_output("Connecting to " + self.m_currentDevice.address().toString())
            else:
                self.emitter.emit_central_output("LE Controller wrong state")

    def service_scan_done(self):

        # Delete old service if available
        if self.m_service:
            self.m_service = None

        # [Filter FTMS service 2]
        # If FtmsService found, create new service
        if self.m_foundFtmsService:
            self.m_service = self.m_control.createServiceObject(
                QBluetoothUuid(QBluetoothUuid(0x1826)))

        if self.m_service:
            self.m_service.stateChanged.connect(self.service_state_changed)
            self.m_service.characteristicChanged.connect(self.update_ftms_value)
            # self.m_service.descriptorWritten.connect(self.confirmed_descriptor_write)
            self.m_service.discoverDetails()
        else:
            self.emitter.emit_central_output("FTMS Service not found.")

    def update_ftms(self, value):
        if self.m_service is not None and self.control_point_char is not None:
            self.m_service.writeCharacteristic(self.control_point_char, QByteArray(value),
                                               QLowEnergyService.WriteMode.WriteWithoutResponse)
            time.sleep(0.1)

    def service_state_changed(self, switch):
        if switch == QLowEnergyService.RemoteServiceDiscovering:
            print("Discovering services...")
        elif switch == QLowEnergyService.RemoteServiceDiscovered:
            for chars in self.m_service.characteristics():
                if chars.uuid() == QBluetoothUuid(0x2ACD):
                    self.ftms_data_char = self.m_service.characteristic(
                        QBluetoothUuid(0x2ACD))
                    self.m_notificationDesc = self.ftms_data_char.descriptor(
                        QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration)
                    if self.m_notificationDesc.isValid():
                        self.m_service.writeDescriptor(self.m_notificationDesc,
                                                       QByteArray.fromHex(b"0100"))
                elif chars.uuid() == QBluetoothUuid(0x2ADA):
                    self.ftms_status_char = self.m_service.characteristic(
                        QBluetoothUuid(0x2ADA))
                    self.m_notificationDesc = self.ftms_status_char.descriptor(
                        QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration)
                    if self.m_notificationDesc.isValid():
                        self.m_service.writeDescriptor(self.m_notificationDesc,
                                                       QByteArray.fromHex(b"0100"))
                elif chars.uuid() == QBluetoothUuid(0x2AD3):
                    self.training_status_char = self.m_service.characteristic(
                        QBluetoothUuid(0x2AD3))
                    self.m_notificationDesc = self.training_status_char.descriptor(
                        QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration)
                    if self.m_notificationDesc.isValid():
                        self.m_service.writeDescriptor(self.m_notificationDesc,
                                                       QByteArray.fromHex(b"0100"))
                elif chars.uuid() == QBluetoothUuid(0x2AD9):
                    self.control_point_char = self.m_service.characteristic(
                        QBluetoothUuid(0x2AD9))
                    self.m_service.characteristicWritten.connect(self.write_success)
            self.emitter.emit_ftms_co_signal(True)
            self.emitter.emit_central_output("Connected")

    def update_ftms_value(self, c, value):
        # ignore any other characteristic change. Shouldn't really happen though

        # if c.uuid() != QBluetoothUuid(QBluetoothUuid.CharacteristicType.HeartRateMeasurement):
        #    return

        # data = value.data()
        # flags = int(data[0])
        if c.uuid() == QBluetoothUuid(0x2ACD):
            # FTMS Data
            ftms_value = value.data()
            self.emitter.emit_ftms_td_signal(ftms_value)
        elif c.uuid() == QBluetoothUuid(0x2ADA):
            ftms_status = value.data()
            self.emitter.emit_ftms_st_signal(ftms_status)
        elif c.uuid() == QBluetoothUuid(0x2AD3):
            training_status = value.data()
            self.emitter.emit_ftms_ts_signal(training_status)
        time.sleep(0.05)

    def confirmed_descriptor_write(self, d, value):
        if (d.isValid() and d == self.m_notificationDesc
                and value == QByteArray.fromHex(b"0000")):
            # disabled notifications . assume disconnect intent
            self.m_control.disconnectFromDevice()
            self.m_service = None

    def disconnect_service(self):
        self.m_foundFtmsService = False

        if self.m_control:
            self.m_control.disconnectFromDevice()
        self.m_service = None

    def controller_connected(self):
        self.m_control.discoverServices()

    def controller_disconnected(self):
        self.emitter.emit_ftms_co_signal(False)

    def service_discovered(self, gatt):
        if gatt == QBluetoothUuid(0x1826):
            self.m_foundFtmsService = True

    def write_success(self):
        pass  # for later?
        # print("write success")

    def stop(self):
        self.disconnect_service()
        self.emitter.stop()

