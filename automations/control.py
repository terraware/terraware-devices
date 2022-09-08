from .base import TerrawareAutomation


class GeneratorControl(TerrawareAutomation):

    def __init__(self, automation_info):
        super().__init__(automation_info)
        self.monitor_device_id = automation_info['deviceId']
        self.monitor_timeseries_name = automation_info['timeseriesName']
        self.lower_threshold = automation_info['lowerThreshold']
        self.upper_threshold = automation_info['upperThreshold']
        settings = automation_info.get('settings')
        self.control_device_id = settings['controlDeviceId']
        self.control_timeseries_name = settings['controlTimeseriesName']
        self.test_output_state = settings.get('testOutputState')

    def run(self, device_manager):

        # get state of charge and relay state
        soc = device_manager.last_value(self.monitor_device_id, self.monitor_timeseries_name)
        relay_state = device_manager.last_value(self.control_device_id, self.control_timeseries_name)
        if self._verbosity:
            print(f'SOC: {soc}, relay: {relay_state}')

        # override output state for testing
        if (not self.test_output_state is None) and (not relay_state is None):
            if self.test_output_state != int(relay_state):
                print('setting output state to %d' % self.test_output_state)
                control_device = device_manager.find_device(self.control_device_id)
                control_device.set_state(self.test_output_state)

        # turn on/off generator if needed
        if (not soc is None) and (not relay_state is None):
            relay_state = int(relay_state)
            if soc < self.lower_threshold and relay_state == 0:
                print('SOC (%.1f) below lower threshold (%.1f); turning on generator' % (soc, self.lower_threshold))
                control_device = device_manager.find_device(self.control_device_id)
                control_device.set_state(1)
            if soc > self.upper_threshold and relay_state == 1:
                print('SOC (%.1f) above upper threshold (%.1f); turning off generator' % (soc, self.upper_threshold))
                control_device = device_manager.find_device(self.control_device_id)
                control_device.set_state(0)
