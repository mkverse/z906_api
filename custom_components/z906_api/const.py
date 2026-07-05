from enum import StrEnum

DOMAIN = "z906_api"

class Endpoints(StrEnum):
    POWER_STATE = "/power"
    POWER_ON = "/power/on"
    POWER_OFF = "/power/off"
    TEMPERATURE = "/temperature"
    INPUT_STATE = "/input"
    INPUT_ENABLE = "/input/enable"
    INPUT_SET = "/input"
    VOLUME_MAIN = "/volume/main"
    VOLUME_MAIN_SET = "/volume/main/set"
    VOLUME_CENTER = "/volume/center"
    VOLUME_CENTER_SET = "/volume/center/set"
    VOLUME_REAR = "/volume/rear"
    VOLUME_REAR_SET = "/volume/rear/set"
    VOLUME_SUBWOOFER = "/volume/subwoofer"
    VOLUME_SUBWOOFER_SET = "/volume/subwoofer/set"
    MUTE_ON = "/mute/on"
    MUTE_OFF = "/mute/off"