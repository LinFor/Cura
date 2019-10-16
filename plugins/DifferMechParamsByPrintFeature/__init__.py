# Copyright (c) 2019 Kirill Shashlov
# The DifferMechParamsByPrintFeature is released under the terms of the AGPLv3 or higher.

# Based on LinearAdvanceSettingPlugin by fieldOfView Copyright (c) 2018

from . import DifferMechParamsByPrintFeature


def getMetaData():
    return {}

def register(app):
    return {"extension": DifferMechParamsByPrintFeature.DifferMechParamsByPrintFeature()}
