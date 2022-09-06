import gevent
import pexpect
from .base import TerrawareDevice, TerrawareHub


sample_status_lines = """
Active SIM          : SIM 1
SIM Status          : SIM Ready
IMEI Code           : 0
IMSI Code           : 0
ICCID Code          : 0
Phone Number        : +1
Signal Level        : 21 asu (-71 dbm)
Register Status     : Registered
Operator            : Verizon
Network Type        : 4G
LAC                 : 0703
Cell ID             : 1BD902
"""


def poll_router(device_id, host, username, password):
    proc = pexpect.spawn('ssh %s -l %s' % (host, username))
    try:
        proc.expect('(yes/no)', timeout=2)  # for "The authenticity of host ... can't be established ... Are you sure you want to continue connecting (yes/no)?"
        proc.sendline('yes')
    except pexpect.TIMEOUT:
        pass
    proc.expect('password:')
    proc.sendline(password)
    proc.expect('Router# ')
    proc.sendline('show cellular')
    proc.expect('Router# ')
    status_lines = proc.before.decode().split('\n')
    signal_strength = 0
    for line in status_lines:
        if 'Signal Level' in line:
            signal_strength = int(line.split(':')[1].split('a')[0])
    proc.sendline('exit')
    proc.sendline('Y')
    return {
        (device_id, 'signal_stength'): signal_strength
    }


# performs monitoring of the InHand Networks IR915L 4G router
class InHandRouterDevice(TerrawareDevice):

    def __init__(self, dev_info):
        super().__init__(dev_info)
        self._address = dev_info["address"]
        self._polling_interval = 60
        self._username = "adm"

        self._password = ""
        settings_items = dev_info.get("settings")
        if settings_items and "password" in settings_items:
            self._password = dev_info["settings"]["password"]
        else:
            print('Error: InHandRouterDevice received no "settings" dict with "password": "xxxxx" as a field in its device configuration settings!')

        print('created InHandRouterDevice with address %s' % self._address)

    def get_timeseries_definitions(self):
        return [[self.id, 'signal_strength', 'Numeric', 2]]

    def reconnect(self):
        pass

    def poll(self):
        if self._local_sim:
            values = {
                (self.id, 'signal_strength'): 18
            }
        else:
            values = poll_router(self.id, self._address, self._username, self._password)
        return values
