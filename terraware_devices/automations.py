from .base import TerrawareAutomation


class AlarmMonitor(TerrawareAutomation):

    def __init__(self, facility_id, name, config):
        super().__init__(facility_id, name, config)
        self.monitor_device_id = config['monitorDeviceId']
        self.monitor_timeseries_name = config['monitorTimeseriesName']
        self.prev_state = None


class SensorBoundsAlert(TerrawareAutomation):

    def __init__(self, facility_id, name, config):
        super().__init__(facility_id, name, config)
        self.monitor_device_id = config['monitorDeviceId']
        self.monitor_timeseries_name = config['monitorTimeseriesName']
        self.lowerThreshold = config['lowerThreshold']
        self.upperThreshold = config['upperThreshold']


class GeneratorControl(TerrawareAutomation):

    def __init__(self, facility_id, name, config):
        super().__init__(facility_id, name, config)
        self.monitor_device_id = config['monitorDeviceId']
        self.control_device_id = config['controlDeviceId']
        self.monitor_timeseries_name = config['monitorTimeseriesName']
        self.control_timeseries_name = config['monitorTimeseriesName']


def automation_class(automation_type):
    if automation_type == 'AlarmMonitor':
        return AlarmMonitor
    elif automation_type == 'SensorBoundsAlert':
        return SensorBoundsAlert
    elif automation_type == 'GeneratorControl':
        return GeneratorControl
