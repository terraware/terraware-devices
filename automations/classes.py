from .monitoring import AlarmMonitor, SensorBoundsAlert
from .control import GeneratorControl


def get_automation_class(automation_type):
    if automation_type == 'AlarmMonitor':
        return AlarmMonitor
    elif automation_type == 'SensorBoundsAlert':
        return SensorBoundsAlert
    elif automation_type == 'GeneratorControl':
        return GeneratorControl
