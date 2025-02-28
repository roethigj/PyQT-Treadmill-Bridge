import time
import threading

from openant.easy.node import Node
from openant.easy.channel import Channel

from PySide6.QtCore import QThread

# Fictive Config of Treadmill


# Definition of Variables
NETWORK_KEY = [0xB9, 0xA5, 0x21, 0xFB, 0xBD, 0x72, 0xC3, 0x45]
Device_Type = 124  # 124 = Stride & Distance Sensor
Device_Number = 12345  # Change if you need.
Channel_Period = 8134
Channel_Frequency = 57


class AntSend(QThread):

    def __init__(self):
        super(AntSend, self).__init__()
        self.ant_message_count = 0
        self.data_page_count = 0

        # Init Variables, needed
        self.last_stride_time = 0
        self.strides_done = 0
        self.distance_accu = 0
        self.distance_last = 0
        self.speed_last = 0
        self.time_rollover = 0
        self.time_rollover_h = 0
        self.time_rollover_l_hex = 0
        self.treadmill_distance_old = 0
        self.treadmill_speed = 0  # m/s
        self.treadmill_cadence = 160
        self.treadmill_distance = 0
        self.calories = 0
        self.calories_delta = 0
        self.calories_last = 0
        self.calories_total = 0

        self.treadmill_distance_delta = 0

        self.last_time_event = time.time()

        self.runner = True



        # Building up the Data Pages
        # This is just for demo purpose and can/will look different for every implementation

    def create_next_datapage(self):
        # Define Variables
        update_latency = 0

        self.ant_message_count += 1

        # Time Calculations
        elapsed_seconds = time.time() - self.last_time_event
        self.last_time_event = time.time()
        update_latency += elapsed_seconds  # 1Second / 32 = 0,03125
        update_latency = int(update_latency / 0.03125)

        # Stride Count, Accumulated strides.
        # This value is incremented once for every two footfalls.
        stride_count_up_value = 60.0 / (self.treadmill_cadence / 2.0)  # In our Example 0,75
        while self.last_stride_time > stride_count_up_value:
            self.strides_done += 1
            self.last_stride_time -= stride_count_up_value
        self.last_stride_time += elapsed_seconds
        if self.strides_done > 255:
            self.strides_done -= 255
            if self.strides_done > 255: # after reconnect
                self.strides_done = 1

        self.calories_delta = self.calories - self.calories_last
        self.calories_last = self.calories
        self.calories_total += self.calories_delta
        if self.calories_total > 255:
            self.calories_total -= 255
            if self.calories_total > 255: # after reconnect
                self.calories_total = 1

        # TIME
        # DISTANCE
        # Accumulated distance, in m-Meters, Rollover = 256
        # self.DistanceBetween = self.ElapsedSeconds * TreadmillSpeed
        self.treadmill_distance_delta = self.treadmill_distance - self.treadmill_distance_old
        self.treadmill_distance_old = self.treadmill_distance
        self.distance_accu += (
            self.treadmill_distance_delta
        )  # Add Distance between 2 ANT+ Ticks to Accumulated Distance
        if self.distance_accu > 255:
            self.distance_accu -= 255
            if self.distance_accu > 255: # after reconnect
                self.distance_accu = 1

        distance_h = int(self.distance_accu)  # just round it to INT
        distance_low_hex = int((self.distance_accu - distance_h) * 16)

        # SPEED - Calculation
        var_speed_ms_h = int(self.treadmill_speed)  # INT-Value
        var_speed_ms_l_hex = int((self.treadmill_speed - var_speed_ms_h) * 256)

        # TIME (changes to Distance or speed will affect if This byte needs to be calculated (<= check Specification)
        if self.speed_last != self.treadmill_speed or self.distance_last != self.distance_accu:
            self.time_rollover += elapsed_seconds
            if self.time_rollover > 255:
                self.time_rollover -= 255
                if self.time_rollover > 255:  # after reconnect
                    self.time_rollover = 1

        self.time_rollover_h = int(self.time_rollover)
        # only integer
        if self.time_rollover_h > 255:
            self.time_rollover_h = 255
            if self.time_rollover_h > 255:  # after reconnect
                self.time_rollover_h = 1
        self.time_rollover_l_hex = int((self.time_rollover - self.time_rollover_h) * 200)
        if self.time_rollover_l_hex > 255:
            self.time_rollover_l_hex -= 255
            if self.time_rollover_l_hex > 255:  # after reconnect
                self.time_rollover_l_hex = 1

        self.speed_last = self.treadmill_speed
        self.distance_last = self.distance_accu
        ant_message_payload = [0, 0, 0, 0, 0, 0, 0, 0]

        if self.ant_message_count < 3:
            ant_message_payload[0] = 80  # DataPage 80
            ant_message_payload[1] = 0xFF
            ant_message_payload[2] = 0xFF  # Reserved
            ant_message_payload[3] = 1  # HW Revision
            ant_message_payload[4] = 1
            ant_message_payload[5] = 1  # Manufacturer ID
            ant_message_payload[6] = 1
            ant_message_payload[7] = 1  # Model Number

        elif 66 < self.ant_message_count < 69:
            ant_message_payload[0] = 81  # DataPage 81
            ant_message_payload[1] = 0xFF
            ant_message_payload[2] = 0xFF  # Reserved
            ant_message_payload[3] = 1  # SW Revision
            ant_message_payload[4] = 0xFF
            ant_message_payload[5] = 0xFF  # Serial Number
            ant_message_payload[6] = 0xFF
            ant_message_payload[7] = 0xFF  # Serial Number

        else:

            ant_message_payload[0] = 0x01  # Data Page 1
            ant_message_payload[1] = self.time_rollover_l_hex
            ant_message_payload[2] = self.time_rollover_h  # Reserved
            ant_message_payload[3] = distance_h  # Distance Accumulated INTEGER
                # BYTE 4 - Speed-Integer & Distance-Fractional
            ant_message_payload[4] = (
                distance_low_hex * 16 + var_speed_ms_h
                )  # Instantaneous Speed, Note: INTEGER
            ant_message_payload[5] = var_speed_ms_l_hex  # Instantaneous Speed, Fractional
            ant_message_payload[6] = self.strides_done  # Stride Count - required
            ant_message_payload[7] = update_latency  # Update Latency
            
            # ANTMessageCount reset
        if self.ant_message_count > 131:
            self.ant_message_count = 0

        return ant_message_payload

    # TX Event
    def on_event_tx(self, data):
        ant_message_payload = self.create_next_datapage()
        # self.ANTMessagePayload = [1, 255, 133, 128, 7, 223, 128, 0]    # just for Debugging purpose
        try:
            self.channel.send_broadcast_data(
                ant_message_payload)
        except OverflowError as e:
            print('overflow-error: Watch disconnected?', e)
            time.sleep(1)
            print('restarting...?')
            self.stop()

    def node_handler(self):
        self.node.start()

    # Open Channel
    def run(self):
        print("ANT+ Channel is open")
        self.node = Node()
        self.node_thread = None

        # self.node = Node()  # initialize the ANT+ device as node, now in init
        # self.x = asyncio.create_task(self.run_ble())

        # CHANNEL CONFIGURATION
        self.node.set_network_key(0x00, NETWORK_KEY)  # set network key
        self.channel = self.node.new_channel(
            Channel.Type.BIDIRECTIONAL_TRANSMIT, 0x00, 0x00
        )  # Set Channel, Master TX
        self.channel.set_id(
            Device_Number, Device_Type, 5
        )  # set channel id as <Device Number, Device Type, Transmission Type>
        self.channel.set_period(Channel_Period)  # set Channel Period
        self.channel.set_rf_freq(Channel_Frequency)  # set Channel Frequency

        # Callback function for each TX event
        self.channel.on_broadcast_tx_data = self.on_event_tx

        self.channel.open()  # Open the ANT-Channel with given configuration
        self.node_thread = threading.Thread(target=self.node_handler)
        self.node_thread.daemon = True
        self.node_thread.start()
        while self.runner:
            QThread.msleep(200)

    def stop(self):
        print("Closing ANT+ Channel...")
        # self.channel.close()  # can cause faults. Necessary?
        self.node.stop()
        self.runner = False
       # self.node_thread.join()
        print("Closed ANT+ Channel...")
########################################################################################################################
