# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     October, 2019

# Licence: AGPLv3 or higher

from ..Script import Script
from UM.Application import Application
from UM.Logger import Logger
from math import ceil
import time
import re

class MState:
    FIRST_LAYER_ALREADY_FOUND = "FIRST_LAYER_ALREADY_FOUND"
    TOTAL_LAYERS_COUNT = "TOTAL_LAYERS_COUNT"
    TOTAL_OVERALL_TIME = "TOTAL_OVERALL_TIME"

    LAYER_NUMBER = "LAYER_NUMBER"
    LAYER_OVERALL_TIME = "LAYER_OVERALL_TIME"
    LAYER_ENDING_TIME = "LAYER_ENDING_TIME"
    LAYER_OVERALL_E_MOVEMENT = "LAYER_OVERALL_E_MOVEMENT"
    E_POSITION = "E_POSITION"
    TIME = "TIME"
    ACTUAL_MESSAGE = "ACTUAL_MESSAGE"
    IS_E_ABSOLUTE_MODE = "IS_E_ABSOLUTE_MODE"
    ACTUAL_E_ABS_POSITION = "ACTUAL_E_ABS_POSITION"

    def __init__(self, previous = None):
        self.previous = previous
        self.state = dict(self.previous.state) if self.previous else dict()

    def set(self, k, v):
        self.state[k] = v
    
    def get(self, k, default = None):
        return self.state.get(k, default)

    def collapseInto(self, to):
        to.state = dict(self.state)

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

    def execute(self, data):
        Logger.log("d", "Processing starts...")
        begin_state = MState()

        overallTime = self.getOverallTime(data)
        begin_state.set(MState.TOTAL_OVERALL_TIME, overallTime)
        totalLayersCount = self.getTotalLayersCount(data)
        begin_state.set(MState.TOTAL_LAYERS_COUNT, totalLayersCount)
        
        state = begin_state
        for lay_idx, layer in enumerate(data):
            data[lay_idx] = self.processSingleLayer(layer, state)

        Logger.log("d", "Processing complete.")
        return data

    def processSingleLayer(self, layerData, state: MState) -> str:
        currentLayerEndingTime = 0
        previousLayerEndingTime = state.get(MState.LAYER_ENDING_TIME, 0)
        # ;TIME_ELAPSED:6921.814718
        timeElapsedRe = r';TIME_ELAPSED:(\d+(\.\d+)?)\n'
        layerEndingTimeMatch = re.search(timeElapsedRe, layerData)
        if layerEndingTimeMatch:
            currentLayerEndingTime = float(layerEndingTimeMatch.group(1))


        currentLayerTimeCost = currentLayerEndingTime - previousLayerEndingTime
        state.set(MState.LAYER_OVERALL_TIME, currentLayerTimeCost)
        state.set(MState.LAYER_ENDING_TIME, currentLayerEndingTime)

        layerCommandLines = layerData.split("\n")
        currentLayerOverallEmovement = self.getOverallEmovement(state, layerCommandLines)
        state.set(MState.LAYER_OVERALL_E_MOVEMENT, currentLayerOverallEmovement)

        new_state = state
        for index, command in enumerate(layerCommandLines):
            after_command_state = MState(new_state)
            self.processSingleCommand(command, after_command_state)

            if currentLayerEndingTime and currentLayerOverallEmovement:
                commandDifficultyContribution = (after_command_state.get(MState.E_POSITION, 0) - new_state.get(MState.E_POSITION, 0)) / currentLayerOverallEmovement
                commandTimeCost = commandDifficultyContribution * currentLayerTimeCost
                new_time = new_state.get(MState.TIME, 0) + commandTimeCost
                after_command_state.set(MState.TIME, new_time)

            if index < 10 or index % 10 == 0:
                command_to_inject = self.getInjectionCommands(new_state, after_command_state)
                for ins_index, injection_command in enumerate(command_to_inject, index + 1):
                    layerCommandLines.insert(ins_index, injection_command)
                
            new_state = after_command_state

        new_state.collapseInto(state)
        state.set(MState.TIME, currentLayerEndingTime)

        return "\n".join(layerCommandLines)

    def processSingleCommand(self, commandLine, state: MState):
        mCommand = self.getValue(commandLine, "M")
        gCommand = self.getValue(commandLine, "G")
        if mCommand in [73, 117]:
            return

        if commandLine.startswith(";LAYER:"):
            # Count layer change
            state.set(MState.FIRST_LAYER_ALREADY_FOUND, True)
            state.set(MState.LAYER_NUMBER, int(commandLine[commandLine.find(":") + 1:]))
            return

        isEabsoluteMode = state.get(MState.IS_E_ABSOLUTE_MODE, True)
        if (mCommand == 82 or gCommand == 90) and isEabsoluteMode == False:
            # Switch to absolute
            state.set(MState.IS_E_ABSOLUTE_MODE, True)
            return
        if (mCommand == 83 or gCommand == 91) and isEabsoluteMode == True:
            # Switch to relative
            state.set(MState.IS_E_ABSOLUTE_MODE, False)
            return
        if gCommand == 92:
            # Update stored position
            state.set(MState.ACTUAL_E_ABS_POSITION, self.getValue(commandLine, "E", state.get(MState.ACTUAL_E_ABS_POSITION)))
            return

        if gCommand in [0, 1]:
            # Process movement
            if isEabsoluteMode:
                previous_e_abs_position = state.get(MState.ACTUAL_E_ABS_POSITION, 0)
                previous_e_position = state.get(MState.E_POSITION, 0)
                new_e_abs_position = self.getValue(commandLine, "E", previous_e_abs_position)
                state.set(MState.ACTUAL_E_ABS_POSITION, new_e_abs_position)
                state.set(MState.E_POSITION, previous_e_position + new_e_abs_position - previous_e_abs_position)
            else:
                previous_e_abs_position = state.get(MState.ACTUAL_E_ABS_POSITION, 0)
                previous_e_position = state.get(MState.E_POSITION, 0)
                movement = self.getValue(commandLine, "E", 0)
                state.set(MState.ACTUAL_E_ABS_POSITION, previous_e_abs_position + movement)
                state.set(MState.E_POSITION, previous_e_position + movement)
            return
        return

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

    def getOverallEmovement(self, begin_state: MState, commandLines) -> float:
        state = MState(begin_state)
        for commandLine in commandLines:
            self.processSingleCommand(commandLine, state)
        
        return state.get(MState.E_POSITION, 0) - begin_state.get(MState.E_POSITION, 0)

    def getInjectionCommands(self, previous: MState, current: MState) -> list:
        if not current.get(MState.FIRST_LAYER_ALREADY_FOUND):
            return []
        
        res = []
        current_time = current.get(MState.TIME)
        overall_time = current.get(MState.TOTAL_OVERALL_TIME)
        percent_change_time = previous.get("NEXT_PERCENT_CHANGE_TIME", 0)
        is_percent_changed = (overall_time > 0) and (current_time > percent_change_time)
        if is_percent_changed:
            current.set("NEXT_PERCENT_CHANGE_TIME", ceil(current_time + 0.0001 * overall_time))

        if self.getSettingValueByKey("useM73"):
            if is_percent_changed:
                previous_m73 = current.get("M73_MESSAGE")
                current_m73 = "M73 P{0:.2f}".format(current_time * 100 / overall_time)
                if previous_m73 != current_m73:
                    res.append(current_m73)
                    current.set("M73_MESSAGE", current_m73)
        
        if self.getSettingValueByKey("useM117"):
            previous_layer = previous.get(MState.LAYER_NUMBER)
            current_layer = current.get(MState.LAYER_NUMBER)
            if is_percent_changed or (previous_layer != current_layer):
                previous_m117 = current.get("M117_MESSAGE")
                current_m117 = "M117"
                if self.getSettingValueByKey("showProgress"):
                    current_m117 += " {0:.1f}%".format(current_time * 100 / overall_time)
                if self.getSettingValueByKey("showCurrentLayer"):
                    total_layers_count = current.get(MState.TOTAL_LAYERS_COUNT)
                    if total_layers_count > 0:
                        current_m117 += " L{0:d}/{1:d}".format(current_layer, total_layers_count)
                    else:
                        current_m117 += " L{0:d}/?".format(current_layer)
                if self.getSettingValueByKey("showElapsedTime"):
                    current_m117 += time.strftime(" P%H-%M", time.gmtime(current_time))
                if (self.getSettingValueByKey("showLeftTime")) and (overall_time > 0):
                    current_m117 += time.strftime(" E%H-%M", time.gmtime(overall_time - current_time))

                if previous_m117 != current_m117:
                    res.append(current_m117)
                    current.set("M117_MESSAGE", current_m117)

        return res
