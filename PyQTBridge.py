import sys
import antstride
import central
import peripheral
import struct
import time

from contextlib import redirect_stdout, redirect_stderr

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QStyleFactory, QTextEdit
from PySide6.QtBluetooth import (QBluetoothAddress,
                                 QBluetoothLocalDevice)


def get_adapters():
    test = QBluetoothLocalDevice.allDevices()
    devices = []
    for i in test:
        devices.append(i)
    return devices


class TreadmillGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Treadmill Controller")
        self.layout = QtWidgets.QGridLayout()
        self.layout.setRowStretch(1, 3)
        self.layout.setRowStretch(2, 1)

        self.setLayout(self.layout)

        self.thread = {}

        # Variables for treadmill data
        self.speed = 0.0
        self.pace = "00:00"
        self.distance = 0.000
        self.time_elapsed = "00:00:00"
        self.incline = 0.0
        self.calories = 0
        self.values = []
        self.treadmill_dongle = None
        self.peripheral_dongle = None
        self.ftms_connected = False
        self.output_text = ""

        # Bluetooth adapter selection
        self.create_connect_disconnect_buttons()

        # Treadmill data display
        self.create_data_display()

        # Control buttons
        self.create_control_buttons()

        # Additional buttons for pace and incline
        self.create_pace_buttons()
        self.create_incline_buttons()

        self.set_button_states(False)

        self.running = False
        self.create_output()

    def create_output(self):
        output_group = QtWidgets.QGroupBox("Output")
        output_layout = QtWidgets.QGridLayout()
        output_group.setLayout(output_layout)
        output_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.output_text.setLineWrapMode(QTextEdit.NoWrap)
        output_layout.addWidget(self.output_text, 0, 0, 4, 2)
        self.layout.addWidget(output_group, 5, 0, 5, 4)

    def write_output(self, text):
        self.output_text.append(text)

    def create_connect_disconnect_buttons(self):  # connect and disconnect buttons
        connect_disconnect_group = QtWidgets.QGroupBox("Connect/Disconnect")
        connect_disconnect_layout = QtWidgets.QGridLayout()
        connect_disconnect_group.setLayout(connect_disconnect_layout)
        connect_disconnect_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        connect_disconnect_layout.addWidget(QtWidgets.QLabel("Adapter for Treadmill:"), 0, 0, 1, 1, Qt.AlignRight)
        adapter_combobox = QtWidgets.QComboBox()
        adapters = get_adapters()
        if len(adapters) > 1:
            self.treadmill_dongle = adapters[0].address()
            self.peripheral_dongle = adapters[1].address()
        else:
            self.treadmill_dongle = adapters[0].address()
        for adapter in adapters:
            adapter_combobox.addItem(adapter.address().toString() + " - " + adapter.name())
        connect_disconnect_layout.addWidget(adapter_combobox, 0, 1, 1, 1)
        self.connect_btn = QtWidgets.QPushButton("Connect")
        connect_disconnect_layout.addWidget(self.connect_btn, 0, 2, 1, 1)
        self.disconnect_btn = QtWidgets.QPushButton("Close")
        connect_disconnect_layout.addWidget(self.disconnect_btn, 0, 3, 1, 1)

        adapter_combobox.currentIndexChanged.connect(self.set_treadmill_dongle)

        self.connect_btn.clicked.connect(self.connect_button)
        self.disconnect_btn.clicked.connect(self.disconnect_button)

        self.layout.addWidget(connect_disconnect_group, 0, 0, 1, 4)

    def set_treadmill_dongle(self, index):
        if index == 0:
            self.treadmill_dongle = str(self.sender().currentText()).split(" - ")[0]
            self.peripheral_dongle = str(self.sender().itemText(index + 1)).split(" - ")[0]
        else:
            self.treadmill_dongle = str(self.sender().currentText()).split(" - ")[0]
            self.peripheral_dongle = str(self.sender().itemText(index - 1)).split(" - ")[0]

    def connect_button(self):
        self.sender().setDisabled(True)
        self.disconnect_btn.setDisabled(True)
        if self.peripheral_dongle is None:
            self.thread[1] = central.BleCentral(local_device=QBluetoothAddress(self.treadmill_dongle))
        else:
            self.thread[1] = central.BleCentral(local_device=QBluetoothAddress(self.treadmill_dongle),
                                                blacklist_address=QBluetoothAddress(self.peripheral_dongle))

        self.thread[1].run()
        self.thread[1].emitter.ftms_td_signal.connect(self.ftms_td)
        self.thread[1].emitter.ftms_st_signal.connect(self.ftms_st)
        self.thread[1].emitter.ftms_ts_signal.connect(self.ftms_ts)
        self.thread[1].emitter.ftms_co_signal.connect(self.connected)
        self.thread[1].emitter.central_output.connect(self.received_output)

        if 2 not in self.thread:
            self.thread[2] = antstride.AntSend()
            self.thread[2].start()
            self.thread[2].finished.connect(self.ant_died)

    def received_output(self, data):
        self.write_output(data)

    def ant_died(self):
        if self.ftms_connected:
            self.thread[2].stop()
            self.write_output("Ant died... reconnect")
            self.thread[2] = antstride.AntSend()
            self.thread[2].start()

    def control_point(self, data):
        self.thread[1].update_ftms(data)

    def connected(self, data):
        if self.peripheral_dongle and 3 not in self.thread and data:
            self.thread[3] = peripheral.FtmsPeripheral(local_device=QBluetoothAddress(self.peripheral_dongle))

        if data and not self.ftms_connected:
            self.disconnect_btn.setDisabled(False)
            self.set_button_states(True)
            self.ftms_connected = True
            if 3 in self.thread:
                self.thread[3].run()
                self.thread[3].emitter.control_point.connect(self.control_point)
                self.thread[3].emitter.peripheral_output.connect(self.received_output)
                self.thread[3].emitter.peripheral_co_signal.connect(self.peripheral_connected)
        elif self.ftms_connected and not data:
            self.write_output("FTMS disconnected unintended... reconnect.")
            self.thread[1].stop()
            time.sleep(2)
            self.thread[1].run()
        elif not data and not self.ftms_connected:
            self.thread[1].stop()
            # self.disconnect_btn.setDisabled(True)
            self.set_button_states(False)
            self.ftms_connected = False
            self.write_output("No FTMS connected... retry?")

    def peripheral_connected(self, data):
        if not data:
            self.write_output("Peripheral disconnected... rebuild peripheral.")
            self.thread[3].stop()
            time.sleep(1)
            self.thread[3] = peripheral.FtmsPeripheral(local_device=QBluetoothAddress(self.peripheral_dongle))
            self.thread[3].run()
            self.thread[3].emitter.control_point.connect(self.control_point)
            self.thread[3].emitter.peripheral_output.connect(self.received_output)
            self.thread[3].emitter.peripheral_co_signal.connect(self.peripheral_connected)

    def ftms_td(self, data):
        if 3 in self.thread:
            self.thread[3].ftms_value = data
        payload = data[2:]
        fmt = '<HHBHHHHBBH'
        self.values = list(struct.unpack(fmt, bytes(payload[0:struct.calcsize(fmt)])))
        self.thread[2].TreadmillSpeed = self.values[0] / 360  # m/s
        self.thread[2].TreadmillDistance = self.values[9]
        self.update_data(self.values)

    def ftms_st(self, data):
        if 3 in self.thread:
            self.thread[3].ftms_status = data

    def ftms_ts(self, data):
        if 3 in self.thread:
            self.thread[3].training_status = data

    def update_data(self, data):
        self.speed = data[0]/100
        if data[0] != 0:
            self.pace = str(int(6000/data[0])) + ":" + str(int((6000/data[0] - int(6000/data[0]))*60)).zfill(2)
        else:
            self.pace = "00:00"
        self.distance = data[1]/1000
        if data[9] < 60:
            self.time_elapsed = "00:" + str(data[9]).zfill(2)
        elif data[9] < 3600:
            self.time_elapsed = str(data[9]//60).zfill(2) + ":" + str(data[9] % 60).zfill(2)
        else:
            self.time_elapsed = (str(data[9]//3600) + ":"
                                 + str((data[9] % 3600)//60).zfill(2) + ":"
                                 + str(data[9] % 60).zfill(2))
        self.incline = data[3]/10
        self.calories = data[5]

        for field, value in zip(self.data_fields, [str(self.speed), self.pace, str(self.distance), self.time_elapsed,
                                                   str(self.incline), str(self.calories)]):
            field.setText(str(value))

    def disconnect_button(self):
        if self.disconnect_btn.text() == "Disconnect":
            self.ftms_connected = False
            if 1 in self.thread:
                self.thread[1].stop()

            if 3 in self.thread:
                self.thread[3].stop()

            print("set button")
            self.set_button_states(False)
            print("set connect_btn")
            self.connect_btn.setEnabled(True)
        else:
            self.write_output("shutting down ...")
            self.stop()
            self.close()

    def create_data_display(self):
        data_group = QtWidgets.QGroupBox("Treadmill Data")
        data_layout = QtWidgets.QGridLayout()
        data_group.setLayout(data_layout)
        data_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        data_labels = ["Speed (km/h):", "Pace (min/km):", "Distance (km):", "Time Elapsed:", "Incline (%):",
                       "Calories Burned:"]
        data_values = [str(self.speed), self.pace, str(self.distance), self.time_elapsed, str(self.incline),
                       str(self.calories)]

        self.data_fields = []

        for i, (label, value) in enumerate(zip(data_labels, data_values)):
            lbl = QtWidgets.QLabel(label)
            val = QtWidgets.QLabel(value)
            lbl.setFont(QtGui.QFont("Arial", 16))
            val.setFont(QtGui.QFont("Arial", 20, QtGui.QFont.Bold))
            data_layout.addWidget(lbl, i, 0)
            data_layout.addWidget(val, i, 1)
            self.data_fields.append(val)

        self.layout.addWidget(data_group, 1, 1, 1, 2)

    def create_control_buttons(self):
        control_group = QtWidgets.QGroupBox("Controls")
        control_layout = QtWidgets.QGridLayout()
        control_group.setLayout(control_layout)

        self.increase_speed_button = QtWidgets.QPushButton("Increase Speed")
        self.decrease_speed_button = QtWidgets.QPushButton("Decrease Speed")
        self.increase_incline_button = QtWidgets.QPushButton("Increase Incline")
        self.decrease_incline_button = QtWidgets.QPushButton("Decrease Incline")
        self.start_pause_button = QtWidgets.QPushButton("Start/Pause")
        self.stop_button = QtWidgets.QPushButton("Stop")

        for button in [
            self.increase_speed_button, self.decrease_speed_button,
            self.increase_incline_button, self.decrease_incline_button,
            self.start_pause_button, self.stop_button
        ]:
            button.setMinimumSize(40, 40)
            button.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

        control_layout.addWidget(self.increase_speed_button, 0, 2)
        control_layout.addWidget(self.decrease_speed_button, 1, 2)
        control_layout.addWidget(self.increase_incline_button, 0, 0)
        control_layout.addWidget(self.decrease_incline_button, 1, 0)
        control_layout.addWidget(self.start_pause_button, 0, 1)
        control_layout.addWidget(self.stop_button, 1, 1)

        self.increase_speed_button.clicked.connect(lambda: self.increase_speed())
        self.decrease_speed_button.clicked.connect(lambda: self.decrease_speed())
        self.increase_incline_button.clicked.connect(lambda: self.increase_incline())
        self.decrease_incline_button.clicked.connect(lambda: self.decrease_incline())
        self.start_pause_button.clicked.connect(self.start_pause)
        self.stop_button.clicked.connect(self.stop)

        self.layout.addWidget(control_group, 2, 0, 1, 4)

    def create_pace_buttons(self):
        pace_group = QtWidgets.QGroupBox("Pace Selection")
        pace_layout = QtWidgets.QVBoxLayout()
        pace_group.setLayout(pace_layout)

        self.pace_buttons = []
        for pace in ["4:00", "4:30", "5:00", "5:30", "6:00"]:
            btn = QtWidgets.QPushButton(f"Set Pace {pace}")
            btn.setMinimumSize(60, 60)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            btn.clicked.connect(lambda checked, p=pace: self.set_pace(p))
            self.pace_buttons.append(btn)
            pace_layout.addWidget(btn)

        self.layout.addWidget(pace_group, 1, 0, 1, 1)

    def create_incline_buttons(self):
        incline_group = QtWidgets.QGroupBox("Incline Selection")
        incline_layout = QtWidgets.QVBoxLayout()
        incline_group.setLayout(incline_layout)

        self.incline_buttons = []
        for incline in [0, 2, 4, 6, 8]:
            btn = QtWidgets.QPushButton(f"Set Incline {incline}%")
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            btn.clicked.connect(lambda checked, i=incline: self.set_incline(i))
            btn.setMinimumSize(60, 60)
            self.incline_buttons.append(btn)
            incline_layout.addWidget(btn)

        self.layout.addWidget(incline_group, 1, 3, 1, 1)

    def set_button_states(self, enabled):
        buttons = [
            self.increase_speed_button, self.decrease_speed_button,
            self.increase_incline_button, self.decrease_incline_button,
            self.start_pause_button, self.stop_button
        ] + self.pace_buttons + self.incline_buttons

        buttons2 = [self.connect_btn]

        if enabled:
            self.disconnect_btn.setText("Disconnect")
        else:
            self.disconnect_btn.setText("Close")

        for button in buttons:
            button.setEnabled(enabled)

        for button in buttons2:
            button.setDisabled(enabled)

    def adjust_speed(self, delta):
        self.speed = max(0, self.speed + delta)
        self.data_fields[0].setText(str(round(self.speed, 1)))

    def adjust_incline(self, delta):
        self.incline = max(0, self.incline + delta)
        self.data_fields[4].setText(str(round(self.incline, 1)))

    def set_pace(self, pace):
        speed = 3600 / ((int((pace.split(":")[0])) * 60) + int(pace.split(":")[1]))
        speed_bytes = bytearray([0x02]) + int(speed*100).to_bytes(2, byteorder='little')
        self.thread[1].update_ftms(speed_bytes)

    def set_incline(self, incline):
        incline_bytes = bytearray([0x03]) + int(incline*10).to_bytes(2, byteorder='little')
        self.thread[1].update_ftms(incline_bytes)

    def increase_speed(self):
        speed = self.values[0] + 20
        speed_bytes = bytearray([0x02]) + int(speed).to_bytes(2, byteorder='little')
        self.thread[1].update_ftms(speed_bytes)

    def decrease_speed(self):
        speed = self.values[0] - 20
        speed_bytes = bytearray([0x02]) + int(speed).to_bytes(2, byteorder='little')
        self.thread[1].update_ftms(speed_bytes)

    def increase_incline(self):
        incline = self.values[3] + 5
        incline_bytes = bytearray([0x03]) + int(incline).to_bytes(2, byteorder='little')
        self.thread[1].update_ftms(incline_bytes)

    def decrease_incline(self):
        incline = self.values[3] - 5
        incline_bytes = bytearray([0x03]) + int(incline).to_bytes(2, byteorder='little')
        self.thread[1].update_ftms(incline_bytes)

    def start_pause(self):
        if self.running is False:
            self.thread[1].update_ftms(bytearray([0x07]))
            self.running = True
        else:
            self.thread[1].update_ftms(bytearray([0x08, 0x02]))
            self.running = False

    def stop(self):
        if 1 in self.thread:
            self.thread[1].update_ftms(bytearray([0x08, 0x02]))
            time.sleep(0.25)
            self.thread[1].update_ftms(bytearray([0x00]))
            time.sleep(0.25)
            self.thread[1].update_ftms(bytearray([0x01]))
            time.sleep(0.25)
            self.thread[1].update_ftms(bytearray([0x00]))
        self.running = False

    def closeEvent(self, event):
        self.ftms_connected = False
        print("Closing...")
        self.write_output("Shutting down...")
        for i in self.thread:
            self.thread[i].stop()
            print(f"Thread {i} stopped.")
        time.sleep(2)
        app.quit()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    window = TreadmillGUI()
    window.show()
    app.exec()
