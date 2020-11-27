# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     November, 2020

# Licence: AGPLv3 or higher
# Code based on Dryw Filtiarn Junction Deviation Calibration toolkit (https://www.thingiverse.com/thing:3463159)

import math
from ..Script import Script
from UM.Application import Application

class AccelerationCalibration(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Acceleration calibration",
            "key": "AccelerationCalibration",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "start":
                {
                    "label": "Starting value",
                    "description": "The value for Acceleration the print will start at (range 0.00 - 10.00, default 0.002).",
                    "type": "int",
                    "default_value": 50,
                    "minimum_value": 20,
                    "maximum_value": 5000,
                    "minimum_value_warning": 50,
                    "maximum_value_warning": 5000
                },
                "stepsize":
                {
                    "label": "Stepping size",
                    "description": "The increment with which Acceleration will be increased every N layers (range 0.001 - 2.000, default 0.002).",
                    "type": "int",
                    "default_value": 12,
                    "minimum_value": 1,
                    "maximum_value": 1000,
                    "minimum_value_warning": 10,
                    "maximum_value_warning": 500
                },
                "lcdfeedback":
                {
                    "label": "Display details on LCD?",
                    "description": "This setting will insert M117 gcode instructions, to display current Acceleration value is being used.",
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
                    "maximum_value": 1000,
                    "minimum_value_warning": 0,
                    "maximum_value_warning": 1000
                },
                "everylayers":
                {
                    "label": "Change Acceleration every N layers",
                    "description": "",
                    "type": "int",
                    "default_value": 1,
                    "minimum_value": 1,
                    "maximum_value": 1000,
                    "minimum_value_warning": 1,
                    "maximum_value_warning": 1000
                }
            }
        }"""
    
    def execute(self, data):
        uselcd = self.getSettingValueByKey("lcdfeedback")
        start = self.getSettingValueByKey("start")
        incr = self.getSettingValueByKey("stepsize")
        lbase = self.getSettingValueByKey("skiplayers")
        lps = self.getSettingValueByKey("everylayers")

        val = start
        i = 0

        previous_position = 0, 0
        current_speed = 0
        for layer in data:
            lay_idx = data.index(layer)
            
            lcd_out = "M117 Acceleration - {val}".format(val=val)
            val_out = "M204 T{val} P{val} ;override".format(val=val)

            lines = layer.split("\n")

            for line in lines:
                if self.getValue(line, "M") in [201, 204, 205, 900] and "override" not in line:
                    lin_idx = lines.index(line)
                    lines[lin_idx] = ";" + line

                if line.startswith(";LAYER_COUNT:"):
                    lin_idx = lines.index(line)
                    lines.insert(lin_idx + 1, "M201 X5000 Y5000 ;override")
                    lines.insert(lin_idx + 2, "M205 J0.04 ;override")
                    lines.insert(lin_idx + 3, "M900 K0 ;override")


                # Insert M900 with K-factor on layer start
                if line.startswith(";LAYER:"):
                    lin_idx = lines.index(line)

                    if (i >= lbase):
                        if (i - lbase) % lps == 0:
                            lines.insert(lin_idx + 1, val_out)
                            if uselcd:
                                lines.insert(lin_idx + 2, lcd_out)
                            val += incr
                            
                    i += 1
           
            result = "\n".join(lines)
            data[lay_idx] = result

        return data

    def getDistance(self, p1, p2):
        return math.sqrt(sum([(a - b) ** 2 for a, b in zip(p1, p2)]))
