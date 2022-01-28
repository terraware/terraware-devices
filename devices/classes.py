from .mock import MockSensorDevice
from .control_by_web import CBWRelayDevice, CBWWeatherStationDevice, CBWSensorHub, CBWTemperatureHumidityDevice
from .omnisense import OmniSenseHub, OmniSenseTemperatureHumidityDevice
from .chirpstack import ChirpStackHub, SenseCapSoilSensor, DraginoSoilSensor, BoveFlowSensor, DraginoLeakSensor
from .modbus import ModbusDevice
from .raspi import RasPiDevice
from .inhand_router import InHandRouterDevice
from .nut_ups import NutUpsDevice
from .weatherflow import TempestWeatherStation


def get_device_class(dev_info):
    dev_type = dev_info.get('type')
    make = dev_info.get('make')
    model = dev_info.get('model')
    protocol = dev_info.get('protocol')

    if dev_type == 'sensor' and make == 'Mock':
        return MockSensorDevice

    elif dev_type == 'server' and make == 'Raspberry Pi':
        return RasPiDevice

#    elif dev_type == 'ups':
#        return NutUpsDevice

#    elif dev_type == 'router' and make == 'InHand Networks' and model == 'IR915L':
#        return InHandRouterDevice

    elif dev_type == 'relay' and make == 'ControlByWeb' and model == 'WebRelay':
        return CBWRelayDevice

    elif dev_type == 'weather' and make == 'ControlByWeb' and model == 'X-422':
        return CBWWeatherStationDevice

    elif dev_type == 'sensor' and make == 'OmniSense' and model == 'S-11':
        return OmniSenseTemperatureHumidityDevice

    elif dev_type == "hub" and make == "OmniSense":
        return OmniSenseHub

    elif protocol == 'modbus':
        return ModbusDevice

    # SenseCap doesn't really have a model number / name for this sensor:
    # https://www.seeedstudio.com/LoRaWAN-Soil-Moisture-and-Temperature-Sensor-EU868-p-4316.html
    elif dev_type == 'sensor' and make == 'SenseCAP':
        return SenseCapSoilSensor

    # https://www.dragino.com/products/lora-lorawan-end-node/item/159-lse01.html
    elif dev_type == 'sensor' and make == 'Dragino' and model == 'LSE01':
        return DraginoSoilSensor

    elif dev_type == 'sensor' and make == 'Dragino' and model == 'LWL02':
        return DraginoLeakSensor

    elif dev_type == 'sensor' and make == 'Bove' and (model == 'BECO X' or model == 'B95 VPW'):
        return BoveFlowSensor

    elif dev_type == 'hub' and make == 'SenseCAP':
        return ChirpStackHub

    elif dev_type == 'sensor' and make == 'WeatherFlow' and model == 'Tempest':
        return TempestWeatherStation

    return None
