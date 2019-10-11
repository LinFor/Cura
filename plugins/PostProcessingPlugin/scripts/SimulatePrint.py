# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     October, 2019

# Licence: CC BY-SA 3.0


from ..Script import Script
from UM.Application import Application

class SimulatePrint(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Print simulation mode (drop all E-movements and Heating commands)",
            "key": "SimulatePrint",
            "metadata": {},
            "version": 2,
            "settings": {}
        }"""

    def execute(self, data):
        for layer in data:
            lay_idx = data.index(layer)
            layerCommandLines = layer.split("\n")
            for commandLine in layerCommandLines:
                command_idx = layerCommandLines.index(commandLine)

                gCommand = self.getValue(commandLine, "G")
                if gCommand in [0, 1, 2, 3] and self.getValue(commandLine, "E"):
                    layerCommandLines[command_idx] = self.putValue(commandLine, E=0)
                if gCommand in [10, 11]:
                    layerCommandLines[command_idx] = ";" + commandLine
                if self.getValue(commandLine, "M") in [104, 109, 140, 190]:
                    layerCommandLines[command_idx] = ";" + commandLine

            data[lay_idx] = "\n".join(layerCommandLines)
        return data