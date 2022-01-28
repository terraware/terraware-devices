from .base import TerrawareAutomation


class GeneratorControl(TerrawareAutomation):

    def __init__(self, facility_id, name, config):
        super().__init__(facility_id, name, config)
        self.monitor_device_id = config['monitorDeviceId']
        self.monitor_timeseries_name = config['monitorTimeseriesName']
        self.control_device_id = config['controlDeviceId']
        self.control_timeseries_name = config['controlTimeseriesName']
        self.lower_threshold = config['lowerThreshold']
        self.upper_threshold = config['upperThreshold']

    def run(self, device_manager):

        # get state of charge and relay state
        soc = device_manager.last_value(self.monitor_device_id, self.monitor_timeseries_name)
        relay_state = device_manager.last_value(self.control_device_id, self.control_timeseries_name)

        # turn on/off generator if needed
        if (not soc is None) and (not relay_state is None):
            relay_state = int(relay_state)
            if soc < self.lower_threshold and relay_state == 0:
                print('SOC (%.1f) below lower threshold (%.1f); turning on generator', soc, self.lower_threshold)
                control_device = device_manager.find_device(self.control_device_id)
                control_device.set_state(1)
            if soc > self.upper_threshold and relay_state == 1:
                print('SOC (%.1f) above upper threshold (%.1f); turning off generator', soc, self.upper_threshold)
                control_device = device_manager.find_device(self.control_device_id)
                control_device.set_state(0)
