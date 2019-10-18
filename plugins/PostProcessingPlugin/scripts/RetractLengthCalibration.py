# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     October, 2019

# Licence: AGPLv3 or higher
# Code based on Dryw Filtiarn Junction Deviation Calibration toolkit (https://www.thingiverse.com/thing:3463159)

from ..Script import Script
from UM.Application import Application

class RetractLengthCalibration(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Retract Length Calibration",
            "key": "RetractLengthCalibration",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "start":
                {
                    "label": "Starting value",
                    "description": "The value for Retract Length the print will start at. A value of 3.00 is the Marlin default value (range 0.00 - 10.00, default 0.20)",
                    "type": "float",
                    "default_value": 0.20,
                    "minimum_value": 0.00,
                    "maximum_value": 10.00,
                    "minimum_value_warning": 0.00,
                    "maximum_value_warning": 10.00
                },
                "stepsize":
                {
                    "label": "Stepping size",
                    "description": "The increment with which Retract Length will be increased every 20 layers (range 0.01 - 2.00, default 0.20)",
                    "type": "float",
                    "default_value": 0.20,
                    "minimum_value": 0.01,
                    "maximum_value": 2.00,
                    "minimum_value_warning": 0.01,
                    "maximum_value_warning": 2.00
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
                    "default_value": 5,
                    "minimum_value": 0,
                    "maximum_value": 200,
                    "minimum_value_warning": 0,
                    "maximum_value_warning": 200
                },
                "everylayers":
                {
                    "label": "Change Retract Length every N layers",
                    "description": "",
                    "type": "int",
                    "default_value": 25,
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

        lcd_gcode = "M117 Retract Length - "
        rl_gcode = "M207 S"

        rl = start
        i = 0

        for layer in data:
            lay_idx = data.index(layer)
            
            lcd_out = lcd_gcode + ('%.3f' % rl)
            rl_out = rl_gcode + ('%.3f' % rl)

            lines = layer.split("\n")
            for line in lines:
                if line.startswith(";LAYER:"):
                    lin_idx = lines.index(line)

                    if (i >= lbase):
                        if (i - lbase) % lps == 0:
                            lines.insert(lin_idx + 1, rl_out)
                            if uselcd:
                                lines.insert(lin_idx + 2, lcd_out)
                            rl += incr
                            
                    i += 1
            
            result = "\n".join(lines)
            data[lay_idx] = result

        return data