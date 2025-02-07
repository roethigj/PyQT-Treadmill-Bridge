# BLE Bridge - Python Script to connect BLE FTM to several Devices

The intention was to connect my treadmill, which is a FTMS device with my Garmin Forerunner, which only can connect via ANT+. 
The reason, I wanted to have the "Running Dynamics" from my HRM pro, which is connected to my Forerunner too.

In addition, I didn't wanted to lose the ability to control my treadmill with the app on my mobile, which gives me structured trainings.


## Requirements

1. `python` version 3.11 or higher
2. `PySide6`
3. `openant`
4. Bluetooth adapter to connect to FTMS (treadmill)
5. ANT+ Adapter to connect to Forerunner (as stride sensor: pace and distance)
6. Bluetooth adapter to connect to mobile for control

Make sure python have access to bluetooth. e.g. $ sudo setcap 'cap_net_raw,cap_net_admin+eip' PATH_TO_PYTHON_EXECUTABLE


## Usage
clone/ download git
run python PyQTBridge.py

## Hints
Some Bluetooth Adapters don't connect well to FTMS's. 
It's always a good idea to restart Bluetooth, when problems occur. 