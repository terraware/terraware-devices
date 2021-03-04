import gevent
import pexpect
from .base import TerrawareDevice


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


def poll_router(host, username, password):
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
            signal_stength = int(line.split(':')[1].split('a')[0])
    proc.sendline('exit')
    proc.sendline('Y')
    return {
        'signal_stength': signal_stength
    }


# performs monitoring of the InHand Networks IR915L 4G router
class InHandRouterDevice(TerrawareDevice):

    def __init__(self, controller, server_path, address, local_sim):
        self._server_path = server_path
        self._address = address
        self._username = "adm"
        self._password = controller.config.router_password
        self._controller = controller
        self._local_sim = local_sim

    def server_path(self):
        return self._server_path

    def reconnect(self):
        pass

    def poll(self):
        if self._local_sim:
            values = {
                'signal_stength': 18
            }
        else:
            values = poll_router(self._address, self._username, self._password)
        return values

    def run(self):
        controller_path = self._controller.path_on_server()
        while True:
            status = self.poll()
            seq_values = {}
            for name, value in status.items():
                full_path = controller_path + '/' + self._server_path + '/' + name
                seq_values[full_path] = value
                print('    %s/%s: %.2f' % (self._server_path, name, value))
            self._controller.sequences.update_multiple(seq_values)
            gevent.sleep(60)
