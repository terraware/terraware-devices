from .base import TerrawareAutomation


class EventMonitor(TerrawareAutomation):

    def __init__(self, automation_info):
        super().__init__(automation_info)
        self.monitor_device_id = automation_info['deviceId']
        self.monitor_timeseries_name = automation_info['timeseriesName']
        self.prev_state = 0  # want to send alert if start up in alarm state

    def run(self, device_manager):

        # get alarm state
        state = device_manager.last_value(self.monitor_device_id, self.monitor_timeseries_name)
        if not state is None:

            # if state changes, send notification
            if state != self.prev_state:
                message = self._name
                device_manager.send_alert(self._facility_id, message, message, message, avoid_resend=False)
            self.prev_state = state


class AlarmMonitor(TerrawareAutomation):

    def __init__(self, automation_info):
        super().__init__(automation_info)
        self.monitor_device_id = automation_info['deviceId']
        self.monitor_timeseries_name = automation_info['timeseriesName']
        self.prev_state = 0  # want to send alert if start up in alarm state

    def run(self, device_manager):

        # get alarm state
        state = device_manager.last_value(self.monitor_device_id, self.monitor_timeseries_name)
        if not state is None:

            # if transition to alarm state, send notification
            if state and (not self.prev_state):
                message = self._name
                device_manager.send_alert(self._facility_id, message, message, message, avoid_resend=False)
            self.prev_state = state


class SensorBoundsAlert(TerrawareAutomation):

    def __init__(self, automation_info):
        super().__init__(automation_info)
        self.monitor_device_id = automation_info['deviceId']
        self.monitor_timeseries_name = automation_info['timeseriesName']
        self.lower_threshold = automation_info.get('lowerThreshold')
        self.upper_threshold = automation_info.get('upperThreshold')
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
