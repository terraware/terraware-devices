from .base import TerrawareAutomation


class AlarmMonitor(TerrawareAutomation):

    def __init__(self, facility_id, name, config):
        super().__init__(facility_id, name, config)
        self.monitor_device_id = config['monitorDeviceId']
        self.monitor_timeseries_name = config['monitorTimeseriesName']
        self.prev_state = 0  # want to send alert if start up in alarm state

    def run(self, device_manager):

        # get alarm state
        state = device_manager.last_value(self.monitor_device_id, self.monitor_timeseries_name)
        if not state is None:

            # if transition to alarm state, send notification
            if state and not self.prev_state:
                message = self._name
                device_manager.send_alert(self._facility_id, message, message, message)
            self.prev_state = state


class SensorBoundsAlert(TerrawareAutomation):

    def __init__(self, facility_id, name, config):
        super().__init__(facility_id, name, config)
        self.monitor_device_id = config['monitorDeviceId']
        self.monitor_timeseries_name = config['monitorTimeseriesName']
        self.lower_threshold = config['lowerThreshold']
        self.upper_threshold = config['upperThreshold']
        self.prev_value = None

    def run(self, device_manager):

        # get sensor value
        value = device_manager.last_value(self.monitor_device_id, self.monitor_timeseries_name)
        if self._verbosity >= 2:
            print('SensorBoundsAlert value: %s' % value)
        if not value is None:

            # check thresholds
            if not self.lower_threshold is None:
                if value < self.lower_threshold and (self.prev_value is None or self.prev_value >= self.lower_threshold):
                    message = '%s (%.2f) below lower threshold (%.2f)' % (self._name, value, self.lower_threshold)
                    label = '%d too low' % self.monitor_device_id
                    device_manager.send_alert(self._facility_id, label, message, message)
            if not self.upper_threshold is None:
                if value > self.upper_threshold and (self.prev_value is None or self.prev_value <= self.upper_threshold):
                    message = '%s (%.2f) above upper threshold (%.2f)' % (self._name, value, self.upper_threshold)
                    label = '%d too high' % self.monitor_device_id
                    device_manager.send_alert(self._facility_id, label, message, message)
            self.prev_value = value


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


def automation_class(automation_type):
    if automation_type == 'AlarmMonitor':
        return AlarmMonitor
    elif automation_type == 'SensorBoundsAlert':
        return SensorBoundsAlert
    elif automation_type == 'GeneratorControl':
        return GeneratorControl
