"""
Core pylobby module

"""

__all__ = ['LobbyMember', 'LobbyRoom']


class LobbyMember(object):
    def __init__(self, name, identity):
        self.name = name
        self.identity = identity
        self.last_active = None
        self.rooms = []

class LobbyRoom(object):
    def __init__(self, name):
        self.name = name
        self.topic = None
        self.members = []

