from PySide6.QtBluetooth import (QBluetoothUuid,
                                 QLowEnergyController,
                                 QLowEnergyDescriptor,
                                 QLowEnergyService,
                                 QBluetoothDeviceInfo,
                                 QBluetoothLocalDevice,
                                 QBluetoothDeviceDiscoveryAgent)
from PySide6.QtCore import QByteArray, Signal, QDateTime, Slot, QThread


def find_local_devices():
    test = QBluetoothLocalDevice.allDevices()
    devices = []
    for i in test:
        devices.append(i.address())
    return devices


class FtmsHandler(QThread):
    ftms_td_signal = Signal(bytearray)
    ftms_st_signal = Signal(bytearray)
    ftms_ts_signal = Signal(bytearray)
    ftms_co_signal = Signal(bool)

    def __init__(self, parent=None, local_device=None):
        super(FtmsHandler, self).__init__(parent)
        self.m_control = None
        self.m_service = None
        self.m_notificationDesc = QLowEnergyDescriptor()
        self.m_currentDevice = None
        self.local_device = local_device

        self.m_foundFtmsService = False
        self.m_measuring = False
        self.ftms_data_char = None
        self.ftms_status_char = None
        self.training_status_char = None
        self.control_point_char = None

        self.m_start = QDateTime()
        self.m_stop = QDateTime()

        self.m_measurements = []
        self.m_addressType = QLowEnergyController.RemoteAddressType.RandomAddress

    def controller_connected(self):
        self.m_control.discoverServices()

    def controller_disconnected(self):
        print("LowEnergy controller disconnected")  # reconnect later?
        # self.set_device(self.m_currentDevice)
        self.ftms_co_signal.emit(False)

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
            # Connect
            if self.m_control.state() == QLowEnergyController.UnconnectedState:
                self.m_control.connectToDevice()
            else:
                print("wrong state")

    def service_discovered(self, gatt):
        if gatt == QBluetoothUuid(0x1826):
            self.m_foundFtmsService = True

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
            self.m_service.descriptorWritten.connect(self.confirmed_descriptor_write)
            self.m_service.discoverDetails()
        else:
            print("FTMS Service not found.")

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
            self.ftms_co_signal.emit(True)

    def update_ftms(self, value):
        if self.m_service is not None and self.control_point_char is not None:
            self.m_service.writeCharacteristic(self.control_point_char, QByteArray(value))

    def write_success(self):
        pass  # for later?
        # print("write success")

    def update_ftms_value(self, c, value):
        # ignore any other characteristic change. Shouldn't really happen though

        # if c.uuid() != QBluetoothUuid(QBluetoothUuid.CharacteristicType.HeartRateMeasurement):
        #    return

        # data = value.data()
        # flags = int(data[0])
        if c.uuid() == QBluetoothUuid(0x2ACD):
            # FTMS Data
            ftms_value = value.data()
            self.ftms_td_signal.emit(ftms_value)
        elif c.uuid() == QBluetoothUuid(0x2ADA):
            ftms_status = value.data()
            self.ftms_st_signal.emit(ftms_status)
        elif c.uuid() == QBluetoothUuid(0x2AD3):
            training_status = value.data()
            self.ftms_ts_signal.emit(training_status)
        else:
            return

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


class BleCentral(QThread):
    # QLoggingCategory.setFilterRules("qt.bluetooth* = true")
    ftms_td_signal = Signal(bytearray)
    ftms_st_signal = Signal(bytearray)
    ftms_ts_signal = Signal(bytearray)
    ftms_co_signal = Signal(bool)

    def __init__(self, parent=None, local_device=None, **kwargs):
        super(BleCentral, self).__init__(parent)
        self.blacklist_address = kwargs.get('blacklist_address', None)
        self.remote_devices = []
        self.ftms_device = ""
        self.device_handler = FtmsHandler(parent=None, local_device=local_device)
        self.device_discovery_agent = QBluetoothDeviceDiscoveryAgent(local_device)
        self.device_discovery_agent.setLowEnergyDiscoveryTimeout(5000)
        self.device_discovery_agent.deviceDiscovered.connect(self.add_device)
        self.device_discovery_agent.finished.connect(self.scan_finished)
        self.device_handler.ftms_td_signal.connect(self.forward_ftms_td)
        self.device_handler.ftms_st_signal.connect(self.forward_ftms_st)
        self.device_handler.ftms_ts_signal.connect(self.forward_ftms_ts)
        self.device_handler.ftms_co_signal.connect(self.forward_ftms_co)

    @Slot()
    def forward_ftms_td(self, data):
        self.ftms_td_signal.emit(data)

    @Slot()
    def forward_ftms_st(self, data):
        self.ftms_st_signal.emit(data)

    @Slot()
    def forward_ftms_ts(self, data):
        self.ftms_ts_signal.emit(data)

    @Slot()
    def forward_ftms_co(self, data):
        self.ftms_co_signal.emit(data)

    def run(self):
        self.device_handler.set_device(None)

        self.device_discovery_agent.start(QBluetoothDeviceDiscoveryAgent.LowEnergyMethod)

    @Slot(QBluetoothDeviceInfo)
    def add_device(self, device):
        if device.address == self.blacklist_address:
            return
        self.remote_devices.append(device)

        for services in device.serviceUuids():
            if services == QBluetoothUuid(0x1826):
                self.device_discovery_agent.stop()
                self.scan_finished()

    @Slot()
    def scan_finished(self):
        if self.remote_devices:
            print(f"Found BT devices: {len(self.remote_devices)}")
            for device in self.remote_devices:
                for services in device.serviceUuids():
                    if services == QBluetoothUuid(0x1826):
                        self.connect_to_service(device.address())
        else:
            print("No BT devices found.")

    @Slot(str)
    def connect_to_service(self, address):
        self.device_discovery_agent.stop()

        current_device = None
        for entry in self.remote_devices:
            device = entry

            if device and device.address() == address:
                current_device = device
                break

        if current_device:
            self.device_handler.set_device(current_device)

    def stop(self):
        self.device_handler.disconnect_service()
        # self.device_discovery_agent.stop()
        # self.device_handler.m_control.disconnectFromDevice()
        self.terminate()
