# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     November, 2020

# Licence: AGPLv3 or higher
# Code based on Dryw Filtiarn Junction Deviation Calibration toolkit (https://www.thingiverse.com/thing:3463159)

import math
from ..Script import Script
from UM.Application import Application

class LinearAdvanceCalibration(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "LinearAdvance K-factor calibration",
            "key": "LinearAdvanceCalibration",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "start":
                {
                    "label": "Starting value",
                    "description": "The value for K-factor the print will start at (range 0.00 - 10.00, default 0.002).",
                    "type": "float",
                    "default_value": 0.002,
                    "minimum_value": 0.000,
                    "maximum_value": 10.000,
                    "minimum_value_warning": 0.000,
                    "maximum_value_warning": 10.000
                },
                "stepsize":
                {
                    "label": "Stepping size",
                    "description": "The increment with which K-factor will be increased every N layers (range 0.001 - 2.000, default 0.002).",
                    "type": "float",
                    "default_value": 0.002,
                    "minimum_value": 0.001,
                    "maximum_value": 2.000,
                    "minimum_value_warning": 0.001,
                    "maximum_value_warning": 2.000
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
                    "default_value": 1,
                    "minimum_value": 0,
                    "maximum_value": 1000,
                    "minimum_value_warning": 0,
                    "maximum_value_warning": 1000
                },
                "everylayers":
                {
                    "label": "Change K-factor every N layers",
                    "description": "",
                    "type": "int",
                    "default_value": 1,
                    "minimum_value": 0,
                    "maximum_value": 1000,
                    "minimum_value_warning": 1,
                    "maximum_value_warning": 1000
                },
                "highspeed":
                {
                    "label": "Speed override for longest move",
                    "description": "",
                    "type": "int",
                    "default_value": 160,
                    "minimum_value": 50,
                    "maximum_value": 300,
                    "minimum_value_warning": 100,
                    "maximum_value_warning": 200
                },
                "slowspeed1":
                {
                    "label": "Speed override for 1 part of second long move",
                    "description": "",
                    "type": "int",
                    "default_value": 30,
                    "minimum_value": 5,
                    "maximum_value": 100,
                    "minimum_value_warning": 15,
                    "maximum_value_warning": 50
                },
                "slowspeed2":
                {
                    "label": "Speed override for 2 part of second long move",
                    "description": "",
                    "type": "int",
                    "default_value": 60,
                    "minimum_value": 5,
                    "maximum_value": 100,
                    "minimum_value_warning": 50,
                    "maximum_value_warning": 100
                }
            }
        }"""
    
    def execute(self, data):
        uselcd = self.getSettingValueByKey("lcdfeedback")
        start = self.getSettingValueByKey("start")
        incr = self.getSettingValueByKey("stepsize")
        lbase = self.getSettingValueByKey("skiplayers")
        lps = self.getSettingValueByKey("everylayers")
        highspeed = self.getSettingValueByKey("highspeed")
        slowspeed1 = self.getSettingValueByKey("slowspeed1")
        slowspeed2 = self.getSettingValueByKey("slowspeed2")

        kf = start
        i = 0

        previous_position = 0, 0
        current_speed = 0
        for layer in data:
            lay_idx = data.index(layer)
            
            lcd_out = "M117 K-factor - {kf:.3f}".format(kf=kf)
            rl_out = "M900 K{kf:.3f}".format(kf=kf)

            lines = layer.split("\n")

            longest_move = 0, ";---"
            second_long_move = 0, ";---"
            for line in lines:
                # Insert M900 with K-factor on layer start
                if line.startswith(";LAYER:"):
                    lin_idx = lines.index(line)

                    if (i >= lbase):
                        if (i - lbase) % lps == 0:
                            lines.insert(lin_idx + 1, rl_out)
                            if uselcd:
                                lines.insert(lin_idx + 2, lcd_out)
                            kf += incr
                            
                    i += 1
                
                # Find longest moves
                if self.getValue(line, "G") in [0, 1]:
                    new_position = self.getValue(line, "X", previous_position[0]), self.getValue(line, "Y", previous_position[1])
                    if (i > lbase) and self.getValue(line, "E", 0) > 0:
                        commandDistance = self.getDistance(previous_position, new_position)
                        if longest_move[0] < commandDistance:
                            second_long_move = longest_move
                            longest_move = commandDistance, line
                        elif second_long_move[0] < commandDistance:
                            second_long_move = commandDistance, line
                    previous_position = new_position

                        
            # Replace longest moves with different speed
            current_position = 0, 0, 0, 0
            replacement_template = "G1 F{speed} X{dest[0]:.3f} Y{dest[1]:.3f} Z{dest[2]:.3f} E{dest[3]:.3f}"
            for line in lines:
                if self.getValue(line, "G") in [0, 1]:
                    target_position = self.getValue(line, "X", current_position[0]), self.getValue(line, "Y", current_position[1]), self.getValue(line, "Z", current_position[2]), self.getValue(line, "E", current_position[3])
                    current_speed = self.getValue(line, "F", current_speed)

                    if line == longest_move[1]:
                        lin_idx = lines.index(line)
                        distances = tuple((b - a) for a, b in zip(current_position, target_position))
                        split_point1 = tuple((a + (b * 0.2)) for a, b in zip(current_position, distances))
                        split_point2 = tuple((a + (b * 0.6)) for a, b in zip(split_point1, distances))
                        lines[lin_idx] = replacement_template.format(speed=current_speed, dest=split_point1)
                        lines.insert(lin_idx + 1, replacement_template.format(speed=highspeed*60, dest=split_point2))
                        lines.insert(lin_idx + 2, replacement_template.format(speed=current_speed, dest=target_position))

                    if line == second_long_move[1]:
                        lin_idx = lines.index(line)
                        distances = tuple((b - a) for a, b in zip(current_position, target_position))
                        split_point1 = tuple((a + (b * 0.2)) for a, b in zip(current_position, distances))
                        split_point2 = tuple((a + (b * 0.2)) for a, b in zip(split_point1, distances))
                        split_point3 = tuple((a + (b * 0.2)) for a, b in zip(split_point2, distances))
                        split_point4 = tuple((a + (b * 0.2)) for a, b in zip(split_point3, distances))
                        lines[lin_idx] = replacement_template.format(speed=current_speed, dest=split_point1)
                        lines.insert(lin_idx + 1, replacement_template.format(speed=slowspeed1*60, dest=split_point2))
                        lines.insert(lin_idx + 2, replacement_template.format(speed=current_speed, dest=split_point3))
                        lines.insert(lin_idx + 3, replacement_template.format(speed=slowspeed2*60, dest=split_point4))
                        lines.insert(lin_idx + 4, replacement_template.format(speed=current_speed, dest=target_position))

                    current_position = target_position
                        

            
            lines.append("")
            lines.append(";Longest move: " + ('%.3f' % longest_move[0]) + " " + longest_move[1])
            lines.append(";Second long move: " + ('%.3f' % second_long_move[0]) + " " + second_long_move[1])
            lines.append("")
            
            result = "\n".join(lines)
            data[lay_idx] = result

        return data

    def getDistance(self, p1, p2):
        return math.sqrt(sum([(a - b) ** 2 for a, b in zip(p1, p2)]))
