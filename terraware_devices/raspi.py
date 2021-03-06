import random
import gevent
import logging
import psutil
import time
from .base import TerrawareDevice


# performs monitoring a raspberry pi
class RasPiDevice(TerrawareDevice):

    def __init__(self, local_sim):
        self._last_disk_counters = {}
        self._last_poll_time = None
        self._local_sim = local_sim
        self._polled = False
        self._start_time = time.time()
        print('created RasPiDevice')

    def reconnect(self):
        pass

    def poll(self):
        if self._local_sim:
            gigabyte = 1024*1024*1024

            # CPU percentages should add up to 100 even with fake data since there
            # might be dashboards that do math on these values.
            cpu_user = random.uniform(1,30)
            cpu_system = random.uniform(1,30)
            cpu_iowait = random.uniform(1,30)
            cpu_idle = 100 - cpu_user - cpu_system - cpu_iowait

            values = {
                'cpu_idle': cpu_idle,
                'cpu_iowait': cpu_iowait,
                'cpu_system': cpu_system,
                'cpu_user': cpu_user,
                'memory_available': random.uniform(1 * gigabyte, 4 * gigabyte),
                'memory_total': 8 * gigabyte,
                'temperature': random.uniform(40, 60),
                'uptime': time.time() - self._start_time,
            }
        else:
            memory_stats = psutil.virtual_memory()

            values = {
                'memory_available': memory_stats.available,
                'memory_total': memory_stats.total,
                'uptime': time.time() - psutil.boot_time(),
            }

            # sensors_temperatures doesn't exist on all platforms
            if hasattr(psutil, 'sensors_temperatures'):
                values['temperature'] = psutil.sensors_temperatures()['cpu_thermal'][0].current

            # CPU percentages are computed using elapsed time since the previous
            # call, so you're supposed to throw the first sample away.
            cpu_times = psutil.cpu_times_percent()
            if self._polled:
                values.update({
                    'cpu_user': cpu_times.user,
                    'cpu_system': cpu_times.system,
                    'cpu_idle': cpu_times.idle,
                })

                # iowait doesn't exist on all platforms
                if hasattr(cpu_times, 'iowait'):
                    values['cpu_iowait'] = cpu_times.iowait

        values.update(self._disk_io_metrics('md0', 'array'))
        values.update(self._disk_io_metrics('mmcblk0', 'sdcard'))

        self._last_poll_time = time.time()
        self._polled = True

        return values

    def _disk_io_metrics(self, device, name):
        """Return a dict of I/O metrics about a specific disk device.

        Attempt to normalize the metrics to per-second values based on the values from
        the previous invocation. The first invocation returns an empty dict since there
        is no baseline to compare against.

        device: Filename of block device (no /dev prefix)
        name: Device name to include in the metric labels
        """
        if self._local_sim:
            counters = None
        else:
            counters = psutil.disk_io_counters(perdisk=True).get(device)
            if counters is None:
                if not self._polled:
                    logging.warning('No metrics found for disk %s (%s)', device, name)
                return {}

        values = {}
        values.update(self._metric_per_second(device, name, 'read_bytes', counters))
        values.update(self._metric_per_second(device, name, 'read_time', counters))
        values.update(self._metric_per_second(device, name, 'write_bytes', counters))
        values.update(self._metric_per_second(device, name, 'write_time', counters))
        values.update(self._metric_per_second(device, name, 'busy_time', counters))

        self._last_disk_counters[device] = counters

        return values


    def _metric_per_second(self, device, name, counter_name, counters):
        """Return a dict with a per-second I/O metric for a device.

        device: Filename of block device (no /dev prefix)
        name: Device name to include in the metric label
        counter_name: psutil.disk_io_counters() attribute name containing metric
        counters: Value of psutil.disk_io_counters()
        """
        metric_name = f'disk_{name}_{counter_name}'

        if self._local_sim:
            return { metric_name: random.uniform(1, 1000) }

        last_counters = self._last_disk_counters.get(device)
        if not last_counters:
            return {}

        try:
            last_value = getattr(last_counters, counter_name)
        except AttributeError:
            return {}
        try:
            new_value = getattr(counters, counter_name)
        except AttributeError:
            logging.warning('No metric %s in counters for %s', counter_name, device)
            return {}

        seconds_since_last = time.time() - self._last_poll_time
        if seconds_since_last == 0:
            logging.warning('0 seconds since last poll time')
            return {}

        value_per_second = (new_value - last_value) / seconds_since_last

        return { metric_name: value_per_second }
