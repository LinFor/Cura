# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     October, 2019

# Licence: AGPLv3 or higher
# Code based on Dryw Filtiarn Junction Deviation Calibration toolkit (https://www.thingiverse.com/thing:3463159)

from ..Script import Script
from UM.Application import Application

class RetractSpeedCalibration(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Retract Speed Calibration",
            "key": "RetractSpeedCalibration",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "start":
                {
                    "label": "Starting value",
                    "description": "The value for Retract Speed the print will start at. A value of 0.02 is the Marlin default value (range 5 - 200, default 5)",
                    "type": "int",
                    "default_value": 5,
                    "minimum_value": 5,
                    "maximum_value": 200,
                    "minimum_value_warning": 5,
                    "maximum_value_warning": 200
                },
                "stepsize":
                {
                    "label": "Stepping size",
                    "description": "The increment with which Retract Speed will be increased every 20 layers (range 1 - 50, default 5)",
                    "type": "int",
                    "default_value": 5,
                    "minimum_value": 1,
                    "maximum_value": 50,
                    "minimum_value_warning": 1,
                    "maximum_value_warning": 50
                },
                "lcdfeedback":
                {
                    "label": "Display details on LCD?",
                    "description": "This setting will insert M117 gcode instructions, to display current Retract Speed value is being used.",
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

        lcd_gcode = "M117 Retract Speed - {:d} mm/s"
        rs1_gcode = "M207 F{:d}"
        rs2_gcode = "M208 F{:d}"

        rs = start
        i = 0

        for layer in data:
            lay_idx = data.index(layer)
            
            lcd_out = lcd_gcode.format(rs)
            rs1_out = rs1_gcode.format(rs * 60)
            rs2_out = rs2_gcode.format(rs * 60)

            lines = layer.split("\n")
            for line in lines:
                if line.startswith(";LAYER:"):
                    lin_idx = lines.index(line)

                    if (i >= lbase):
                        if (i - lbase) % lps == 0:
                            lines.insert(lin_idx + 1, rs1_out)
                            lines.insert(lin_idx + 2, rs2_out)
                            if uselcd:
                                lines.insert(lin_idx + 3, lcd_out)
                            rs += incr
                            
                    i += 1
            
            result = "\n".join(lines)
            data[lay_idx] = result

        return data