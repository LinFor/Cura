# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     October, 2019

# Licence: AGPLv3 or higher
# Code based on Dryw Filtiarn Junction Deviation Calibration toolkit (https://www.thingiverse.com/thing:3463159)

from ..Script import Script
from UM.Application import Application

class TemperatureCalibration(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Temperature Calibration",
            "key": "TemperatureCalibration",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "start":
                {
                    "label": "Starting value",
                    "description": "The value for Temperature the print will start at. A value of 0.02 is the Marlin default value (range 0.50 - 10.00, default 4.00)",
                    "type": "int",
                    "default_value": 200,
                    "minimum_value": 150,
                    "maximum_value": 300,
                    "minimum_value_warning": 150,
                    "maximum_value_warning": 300
                },
                "stepsize":
                {
                    "label": "Stepping size",
                    "description": "The decrement with which Temperature will be increased every 20 layers (range 0.05 - 2.00, default 1.00)",
                    "type": "int",
                    "default_value": 5,
                    "minimum_value": 1,
                    "maximum_value": 20,
                    "minimum_value_warning": 1,
                    "maximum_value_warning": 20
                },
                "lcdfeedback":
                {
                    "label": "Display details on LCD?",
                    "description": "This setting will insert M117 gcode instructions, to display current Retract Length value is being used.",
                    "type": "bool",
                    "default_value": true
                },
                "skiplayers":
                {
                    "label": "Skip N layers on start",
                    "description": "",
                    "type": "int",
                    "default_value": 0,
                    "minimum_value": 0,
                    "maximum_value": 200,
                    "minimum_value_warning": 0,
                    "maximum_value_warning": 200
                },
                "everylayers":
                {
                    "label": "Change Temperature every N layers",
                    "description": "",
                    "type": "int",
                    "default_value": 100,
                    "minimum_value": 0,
                    "maximum_value": 200,
                    "minimum_value_warning": 0,
                    "maximum_value_warning": 200
                }
            }
        }"""
    
    def execute(self, data):
        uselcd = self.getSettingValueByKey("lcdfeedback")
        start = self.getSettingValueByKey("start")
        incr = self.getSettingValueByKey("stepsize")
        lbase = self.getSettingValueByKey("skiplayers")
        lps = self.getSettingValueByKey("everylayers")

        lcd_gcode = "M117 Temperature - {:d}"
        tmp_gcode = "M104 S{:d}"

        tmp = start
        i = 0

        for layer in data:
            lay_idx = data.index(layer)
            
            lcd_out = lcd_gcode.format(tmp)
            tmp_out = tmp_gcode.format(tmp)

            lines = layer.split("\n")
            for line in lines:
                if line.startswith(";LAYER:"):
                    lin_idx = lines.index(line)

                    if (i >= lbase):
                        if (i - lbase) % lps == 0:
                            lines.insert(lin_idx + 1, tmp_out)
                            if uselcd:
                                lines.insert(lin_idx + 2, lcd_out)
                            tmp -= incr
                            
                    i += 1
            
            result = "\n".join(lines)
            data[lay_idx] = result

        return data
        