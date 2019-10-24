# Cura PostProcessingPlugin
# Author:   Kirill Shashlov
# Date:     October, 2019

# Licence: AGPLv3 or higher

from ..Script import Script
from UM.Application import Application
from UM.Logger import Logger
from math import ceil
import time

class EnrichPrintProgress(Script):
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

    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name": "Enrich G-code with Print Progress info",
            "key": "EnrichPrintProgress",
            "metadata": {},
            "version": 2,
            "settings": {
                "interpolateByE":
                {
                    "label": "Interpolate by E",
                    "description": "Interpolate progress by E movements (icrease accuracy, but slow)",
                    "type": "bool",
                    "default_value": true
                },
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

        self.interpolateByE = self.getSettingValueByKey("interpolateByE")
        self.useM73 = self.getSettingValueByKey("useM73")
        self.useM117 = self.getSettingValueByKey("useM117")
        self.showProgress = self.getSettingValueByKey("showProgress")
        self.showCurrentLayer = self.getSettingValueByKey("showCurrentLayer")
        self.showElapsedTime = self.getSettingValueByKey("showElapsedTime")
        self.showLeftTime = self.getSettingValueByKey("showLeftTime")

        begin_state = dict()

        begin_state[self.TOTAL_OVERALL_TIME] = self.getOverallTime(data)
        begin_state[self.TOTAL_LAYERS_COUNT] = self.getTotalLayersCount(data)
        
        state = begin_state
        for lay_idx, layer in enumerate(data):
            data[lay_idx] = self.processSingleLayer(layer, state)

        Logger.log("d", "Processing complete.")
        return data

    def processSingleLayer(self, layerData, state: dict) -> str:
        previousLayerEndingTime = state.get(self.LAYER_ENDING_TIME, 0)
        # ;TIME_ELAPSED:6921.814718
        currentLayerEndingTime_str = self.getFirstSubstringBetween(layerData, ";TIME_ELAPSED:", "\n")
        currentLayerEndingTime = float(currentLayerEndingTime_str) if currentLayerEndingTime_str else previousLayerEndingTime

        if self.interpolateByE:
            currentLayerTimeCost = currentLayerEndingTime - previousLayerEndingTime
            state[self.LAYER_OVERALL_TIME] = currentLayerTimeCost
            state[self.LAYER_ENDING_TIME] = currentLayerEndingTime

            layerCommandLines = layerData.split("\n")
            currentLayerOverallEmovement = self.getOverallEmovement(state, layerCommandLines)
            state[self.LAYER_OVERALL_E_MOVEMENT] = currentLayerOverallEmovement

            new_state = state
            for index, command in enumerate(layerCommandLines):
                after_command_state = dict(new_state)
                self.processSingleCommand(command, after_command_state)

                if currentLayerEndingTime and currentLayerOverallEmovement:
                    commandDifficultyContribution = (after_command_state.get(self.E_POSITION, 0) - new_state.get(self.E_POSITION, 0)) / currentLayerOverallEmovement
                    commandTimeCost = commandDifficultyContribution * currentLayerTimeCost
                    new_time = new_state.get(self.TIME, 0) + commandTimeCost
                    after_command_state[self.TIME] = new_time

                if index < 5 or index % 5 == 0:
                    command_to_inject = self.getInjectionCommands(new_state, after_command_state)
                    for ins_index, injection_command in enumerate(command_to_inject, index + 1):
                        layerCommandLines.insert(ins_index, injection_command)
                    
                new_state = after_command_state

            state.update(new_state)
            state[self.TIME] = currentLayerEndingTime

            return "\n".join(layerCommandLines)
        else:
            new_state = dict(state)
            layer_num = self.getLayerNum(layerData)
            if layer_num is not None:
                new_state[self.LAYER_NUMBER] = layer_num
                new_state[self.FIRST_LAYER_ALREADY_FOUND] = True
            new_state[self.LAYER_ENDING_TIME] = currentLayerEndingTime

            injection_commands = self.getInjectionCommands(state, new_state)

            new_state[self.TIME] = currentLayerEndingTime
            state.update(new_state)

            return "\n".join(injection_commands + [layerData])

    def processSingleCommand(self, commandLine, state: dict):
        mCommand = self.getValue(commandLine, "M")
        gCommand = self.getValue(commandLine, "G")
        if mCommand in [73, 117]:
            return

        if commandLine.startswith(";LAYER:"):
            # Count layer change
            state[self.FIRST_LAYER_ALREADY_FOUND] = True
            state[self.LAYER_NUMBER] = int(self.getFirstSubstringBetween(commandLine, ":"))
            return

        isEabsoluteMode = state.get(self.IS_E_ABSOLUTE_MODE, True)
        if (mCommand == 82 or gCommand == 90) and isEabsoluteMode == False:
            # Switch to absolute
            state[self.IS_E_ABSOLUTE_MODE] = True
            return
        if (mCommand == 83 or gCommand == 91) and isEabsoluteMode == True:
            # Switch to relative
            state[self.IS_E_ABSOLUTE_MODE] = False
            return
        if gCommand == 92:
            # Update stored position
            state[self.ACTUAL_E_ABS_POSITION] = self.getValue(commandLine, "E", state.get(self.ACTUAL_E_ABS_POSITION, 0))
            return

        if gCommand in [0, 1]:
            # Process movement
            if isEabsoluteMode:
                previous_e_abs_position = state.get(self.ACTUAL_E_ABS_POSITION, 0)
                previous_e_position = state.get(self.E_POSITION, 0)
                new_e_abs_position = self.getValue(commandLine, "E", previous_e_abs_position)
                state[self.ACTUAL_E_ABS_POSITION] = new_e_abs_position
                state[self.E_POSITION] = previous_e_position + new_e_abs_position - previous_e_abs_position
            else:
                previous_e_abs_position = state.get(self.ACTUAL_E_ABS_POSITION, 0)
                previous_e_position = state.get(self.E_POSITION, 0)
                movement = self.getValue(commandLine, "E", 0)
                state[self.ACTUAL_E_ABS_POSITION] = previous_e_abs_position + movement
                state[self.E_POSITION] = previous_e_position + movement
            return
        return

    def getFirstSubstringBetween(self, input_data: str, start: str, end: str = None) -> str:
        start_index = input_data.find(start)
        if start_index == -1:
            return None
        start_index += len(start)
        if not end:
            return input_data[start_index:]
        end_index = input_data.find(end, start_index)
        if end_index == -1:
            return input_data[start_index:]
        return input_data[start_index:end_index]

    def getOverallTime(self, data) -> float:
        # ;TIME_ELAPSED:6921.814718

        # Get last TIME_ELAPSED
        i = len(data) - 1
        while i >= 0:
            elapsed_str = self.getFirstSubstringBetween(data[i], ";TIME_ELAPSED:", "\n")
            if elapsed_str:
                return float(elapsed_str)
            i -= 1
        return None
    
    def getTotalLayersCount(self, data) -> int:
        # ;LAYER:195

        # Get last LAYER
        i = len(data) - 1
        while i >= 0:
            index_str = self.getFirstSubstringBetween(data[i], ";LAYER:", "\n")
            if index_str:
                return int(index_str) + 1
            i -= 1
        return None

    def getLayerNum(self, data) -> int:
        # ;LAYER:195
        index_str = self.getFirstSubstringBetween(data, ";LAYER:", "\n")
        if index_str:
            return int(index_str)
        return None

    def getOverallEmovement(self, begin_state: dict, commandLines) -> float:
        state = dict(begin_state)
        for commandLine in commandLines:
            self.processSingleCommand(commandLine, state)
        
        return state.get(self.E_POSITION, 0) - begin_state.get(self.E_POSITION, 0)

    def getInjectionCommands(self, previous: dict, current: dict) -> list:
        if not current.get(self.FIRST_LAYER_ALREADY_FOUND, False):
            return []
        
        res = []
        current_time = current.get(self.TIME, 0)
        overall_time = current.get(self.TOTAL_OVERALL_TIME, None)
        percent_change_time = previous.get("NEXT_PERCENT_CHANGE_TIME", 0)
        is_percent_changed = overall_time and (current_time >= percent_change_time)
        if is_percent_changed:
            current["NEXT_PERCENT_CHANGE_TIME"] = ceil(current_time + 0.0001 * overall_time)

        if self.useM73:
            if is_percent_changed:
                previous_m73 = current.get("M73_MESSAGE", "")
                current_m73 = "M73 P{0:.2f}".format(current_time * 100 / overall_time)
                if previous_m73 != current_m73:
                    res.append(current_m73)
                    current["M73_MESSAGE"] = current_m73
        
        if self.useM117:
            previous_layer = previous.get(self.LAYER_NUMBER, 0)
            current_layer = current.get(self.LAYER_NUMBER, 0) + 1
            if is_percent_changed or (previous_layer != current_layer):
                previous_m117 = current.get("M117_MESSAGE", "")
                current_m117 = "M117"
                if self.showProgress:
                    current_m117 += " {0:.1f}%".format(current_time * 100 / overall_time)
                if self.showCurrentLayer:
                    total_layers_count = current.get(self.TOTAL_LAYERS_COUNT, None)
                    if total_layers_count:
                        current_m117 += " L{0:d}/{1:d}".format(current_layer, total_layers_count)
                    else:
                        current_m117 += " L{0:d}/?".format(current_layer)
                if self.showElapsedTime:
                    current_m117 += time.strftime(" P%H-%M", time.gmtime(current_time))
                if self.showLeftTime and overall_time:
                    current_m117 += time.strftime(" E%H-%M", time.gmtime(overall_time - current_time))

                if previous_m117 != current_m117:
                    res.append(current_m117)
                    current["M117_MESSAGE"] = current_m117

        return res
