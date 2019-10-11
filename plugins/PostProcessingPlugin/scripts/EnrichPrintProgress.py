# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     October, 2019

# Licence: CC BY-SA 3.0


from ..Script import Script
from UM.Application import Application
from UM.Logger import Logger
import time
import re

class EnrichPrintProgress(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Enrich G-code with Print Progress info",
            "key": "EnrichPrintProgress",
            "metadata": {},
            "version": 2,
            "settings": {
                "useM73":
                {
                    "label": "Use M73 command to update print progress",
                    "description": "http://marlinfw.org/docs/gcode/M073.html",
                    "type": "bool",
                    "default_value": true
                },
                "useM117":
                {
                    "label": "Use M117 command to display print progress info on LCD",
                    "description": "http://marlinfw.org/docs/gcode/M117.html",
                    "type": "bool",
                    "default_value": true
                },
                "showProgress":
                {
                    "label": "Show progress in percents in M117",
                    "description": "",
                    "type": "bool",
                    "default_value": false
                },
                "showCurrentLayer":
                {
                    "label": "Show current layer",
                    "description": "Show current layer in M117 in the format 'L2/30'",
                    "type": "bool",
                    "default_value": true
                },
                "showElapsedTime":
                {
                    "label": "Show elapsed time",
                    "description": "Show estimated elapsed time in M117 in the format 'P01-45'",
                    "type": "bool",
                    "default_value": false
                },
                "showLeftTime":
                {
                    "label": "Show time left",
                    "description": "Show estimated time left in M117 in the format 'E00-16'",
                    "type": "bool",
                    "default_value": true
                }
            }
        }"""

    currentLayer = 0
    previousLayerEndingTime = 0
    previousLayerLastEposition = 0
    lastMessage = ""
    isEabsoluteMode = True
    lastEabsPosition = 0
    firstLayerAlreadyFound = False

    def execute(self, data):
        Logger.log("d", "Processing starts...")

        self.currentLayer = 0
        self.previousLayerEndingTime = 0
        self.previousLayerLastEposition = 0
        self.lastMessage = ""
        self.isEabsoluteMode = True
        self.lastEabsPosition = 0
        self.firstLayerAlreadyFound = False

        # ;TIME_ELAPSED:6921.814718
        timeElapsedRe = r';TIME_ELAPSED:(\d+(\.\d+)?)\n'

        overallTime = self.getOverallTime(data)
        totalLayersCount = self.getTotalLayersCount(data)
        
        for layer in data:
            result = layer
            lay_idx = data.index(layer)

            layerEndingTime = 0
            layerEndingTimeMatch = re.search(timeElapsedRe, result)
            if layerEndingTimeMatch:
                layerEndingTime = float(layerEndingTimeMatch.group(1))

            layerCommandLines = layer.split("\n")

            currentEposition = self.previousLayerLastEposition
            currentLayerOverallEmovement = self.getOverallEmovement(layerCommandLines)
            currentLayerTime = layerEndingTime - self.previousLayerEndingTime

            for commandLine in layerCommandLines:
                mCommand = self.getValue(commandLine, "M")
                gCommand = self.getValue(commandLine, "G")
                if mCommand in [73, 117]:
                    continue
                if commandLine.startswith(";LAYER:"):
                    # Count layer change
                    self.firstLayerAlreadyFound = True
                    self.currentLayer = int(commandLine[commandLine.find(":") + 1:])
                    continue
                if (mCommand == 82 or gCommand == 90) and self.isEabsoluteMode == False:
                    # Switch to absolute
                    self.isEabsoluteMode = True
                    continue
                if (mCommand == 83 or gCommand == 91) and self.isEabsoluteMode == True:
                    # Switch to relative
                    self.isEabsoluteMode = False
                    continue
                if gCommand == 92:
                    # Update stored position
                    self.lastEabsPosition = self.getValue(commandLine, "E", self.lastEabsPosition)
                    continue


                if gCommand in [0, 1]:
                    # Process movement
                    if self.isEabsoluteMode:
                        movement = self.getValue(commandLine, "E", self.lastEabsPosition) - self.lastEabsPosition
                        self.lastEabsPosition += movement
                        currentEposition += movement
                    else:
                        movement = self.getValue(commandLine, "E", 0)
                        self.lastEabsPosition += movement
                        currentEposition += movement

                if self.firstLayerAlreadyFound:
                    currentEstimatedElapsedTime = self.previousLayerEndingTime + (currentLayerTime * (currentEposition - self.previousLayerLastEposition) / currentLayerOverallEmovement) if currentLayerOverallEmovement > 0 else self.previousLayerEndingTime

                    currentMessage = self.formatStatusCommand(self.currentLayer, currentEstimatedElapsedTime, totalLayersCount, overallTime)
                    if currentMessage != self.lastMessage:
                        self.lastMessage = currentMessage
                        commandIndex = layerCommandLines.index(commandLine)
                        layerCommandLines.insert(commandIndex + 1, currentMessage)
                
            data[lay_idx] = "\n".join(layerCommandLines)

            self.previousLayerLastEposition = currentEposition
            self.previousLayerEndingTime = layerEndingTime

        Logger.log("d", "Processing complete.")
        
        return data

    def getOverallTime(self, data) -> int:
        # ;TIME_ELAPSED:6921.814718
        timeElapsedRe = r';TIME_ELAPSED:(\d+(\.\d+)?)\n'

        # Get last TIME_ELAPSED
        i = len(data) - 1
        while i >= 0:
            overallTimeMatch = re.search(timeElapsedRe, data[i])
            if not overallTimeMatch:
                i -= 1
                continue
            return float(overallTimeMatch.group(1))

        return -1
    
    def getTotalLayersCount(self, data) -> int:
        # ;LAYER:195
        layerRe = r';LAYER:(\d+)\n'

        # Get last LAYER
        i = len(data) - 1
        while i >= 0:
            currentLayerMatch = re.search(layerRe, data[i])
            if not currentLayerMatch:
                i -= 1
                continue
            return int(currentLayerMatch.group(1)) + 1

        return -1

    def getOverallEmovement(self, commandLines) -> float:
        result = 0
        isCurrentEabsoluteMode = self.isEabsoluteMode
        lastEabsPosition = self.lastEabsPosition
        for commandLine in commandLines:
            mCommand = self.getValue(commandLine, "M")
            gCommand = self.getValue(commandLine, "G")
            if mCommand in [73, 117]:
                continue
            if (mCommand == 82 or gCommand == 90) and isCurrentEabsoluteMode == False:
                # Switch to absolute
                isCurrentEabsoluteMode = True
                continue
            if (mCommand == 83 or gCommand == 91) and isCurrentEabsoluteMode == True:
                # Switch to relative
                isCurrentEabsoluteMode = False
                continue
            if gCommand == 92:
                # Update stored position
                lastEabsPosition = self.getValue(commandLine, "E", lastEabsPosition)
                continue

            if gCommand in [0, 1]:
                # Process movement
                if isCurrentEabsoluteMode:
                    movement = self.getValue(commandLine, "E", lastEabsPosition) - lastEabsPosition
                    lastEabsPosition += movement
                    result += movement
                else:
                    movement = self.getValue(commandLine, "E", 0)
                    lastEabsPosition += movement
                    result += movement
        return result

    def formatStatusCommand(self, currentLayer, elapsedTime, totalLayersCount, overallTime) -> str:
        result = ""
        if (self.getSettingValueByKey("useM73")):
            result += "M73 P{0:.0f}\n".format(elapsedTime * 100 / overallTime)
        if (self.getSettingValueByKey("useM117")):
            result += "M117"
            if self.getSettingValueByKey("showProgress"):
                result += " {0:.1f}%".format(elapsedTime * 100 / overallTime)
            if self.getSettingValueByKey("showCurrentLayer"):
                if totalLayersCount > 0:
                    result += " L{0:d}/{1:d}".format(currentLayer, totalLayersCount)
                else:
                    result += " L{0:d}/?".format(currentLayer)
            if self.getSettingValueByKey("showElapsedTime"):
                result += time.strftime(" P%H-%M", time.gmtime(elapsedTime))
            if (self.getSettingValueByKey("showLeftTime")) and overallTime > 0:
                result += time.strftime(" E%H-%M", time.gmtime(overallTime - elapsedTime))
        
        return result
