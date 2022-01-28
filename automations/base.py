from abc import ABC


class TerrawareAutomation(ABC):

    def __init__(self, facility_id, name, config):
        self._facility_id = facility_id
        self._name = name
        self._verbosity = config.get('verbosity', 0)
        print('creating automation; facility: %s, name: %s, type: %s' % (facility_id, name, config['type']))

    def name(self):
        return self._name

    def facility_id(self):
        return self._facility_id
