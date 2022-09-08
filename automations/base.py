from abc import ABC


class TerrawareAutomation(ABC):

    def __init__(self, automation_info):
        self._facility_id = automation_info['facilityId']
        self._name = automation_info['name']
        self._verbosity = automation_info.get('verbosity', 0)
        print('creating automation; facility: %s, name: %s, type: %s' % (self._facility_id, self._name, automation_info['type']))

    def name(self):
        return self._name

    def facility_id(self):
        return self._facility_id
