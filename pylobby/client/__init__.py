"""
Lobby client module

"""

import time
import logging
import threading
import Queue

import zmq

from zmq.utils import jsonapi
from zmq.eventloop import ioloop, zmqstream

from pylobby.exceptions import LobbyException

__all__ = ['LobbyClient']


class LobbyClient(threading.Thread):
    """
    docstring

    """
    def __init__(self, who, endpoint, join=['#general']):
        """
        docstring

        """
        super(LobbyClient, self).__init__()
        self.daemon = True

        self.who = who
        self.discovery_endpoint = endpoint
        self.to_join = join

        self.ctx = zmq.Context()
        self.loop = ioloop.IOLoop.instance()

        self.discovery_socket = self.ctx.socket(zmq.DEALER)
        self.frontend_socket = self.ctx.socket(zmq.DEALER)
        self.backend_socket = self.ctx.socket(zmq.SUB)

        self.inbox = Queue.Queue()
        self.priv_inbox = Queue.Queue()

        self.connected = False

        self.rooms = []
        self.commands = {
            '/JOIN': self.command_join,
            '/PART': self.command_part,
            '/QUIT': self.command_quit,
        }

    def run(self):
        """
        docstring

        """
        logging.info('Starting Lobby client')

        self.discover_endpoints()
        self.connect_endpoints()
        self.connected = True
        self.say(message='/CONNECT')

        for room in self.to_join:
            self.say(message='/JOIN %s' % room)

        logging.info('Starting event loop')
        self.loop.start()

    def stop(self):
        """
        docstring

        """
        logging.info('Stopping Lobby client')

#        self.say(message='/QUIT')
#        self.inbox.join()
#        self.priv_inbox.join()
        self.loop.stop()
        self.frontend_stream.close()
        self.backend_stream.close()
        self.frontend_socket.close()
        self.backend_socket.close()
        self.ctx.destroy()

    def discover_endpoints(self):
        """
        docstring

        """
        logging.info(
            'Discovering server endpoints via %s ...',
            self.discovery_endpoint
        )
        self.discovery_socket.connect(self.discovery_endpoint)
        self.discovery_socket.send("")
        self.endpoints = self.discovery_socket.recv_json()
        self.discovery_socket.close()
        logging.info('Discovered server endpoints: %s', self.endpoints)

    def connect_endpoints(self):
        """
        docstring

        """
        proto, host, port = self.discovery_endpoint.split(':')
        self.frontend_endpoint = ':'.join(
            [proto, host, str(self.endpoints['frontend'])]
        )
        self.backend_endpoint = ':'.join(
            [proto, host, str(self.endpoints['backend'])]
        )

        logging.info('Connecting to frontend at %s', self.frontend_endpoint)
        logging.info('Connecting to backend at %s', self.backend_endpoint)

        self.frontend_socket.connect(self.frontend_endpoint)
        self.backend_socket.connect(self.backend_endpoint)

        self.frontend_stream = zmqstream.ZMQStream(self.frontend_socket, self.loop)
        self.backend_stream = zmqstream.ZMQStream(self.backend_socket, self.loop)

        self.frontend_stream.on_recv(self.recv_priv_message)
        self.backend_stream.on_recv(self.recv_message)

    def recv_message(self, data):
        """
        docstring

        """
        logging.debug('New public message received: %s', data)

        try:
            self.inbox.put((time.localtime(), jsonapi.loads(data[1])))
        except (TypeError, ValueError) as e:
            logging.warning('Invalid message received: %s', data)

    def recv_priv_message(self, data):
        """
        docstring

        """
        logging.debug('New private message received: %s', data)

        try:
            self.priv_inbox.put((time.localtime(), jsonapi.loads(data[0])))
        except (TypeError, ValueError) as e:
            logging.warning('Invalid message received: %s', data)

    def say(self, **kwargs):
        """
        docstring

        """
        if not self.connected:
            logging.warning('Not connected yet, cannot send a message...')
            return

        if not kwargs.get('message'):
            logging.warning('Need to provide a message to be sent')
            return

        kwargs['who'] = self.who

        logging.debug('Sending message: %s', kwargs)

        # TODO: We should probably not send messages for which
        # commands have failed, e.g. sending an empty '/JOIN' command
        # should not be sent to the server in order to
        # avoid unnecessary messages passing back and forth
        if kwargs['message'].startswith('/'):
            self.process_command(msg=kwargs)
        self.frontend_socket.send_json(kwargs)

    def process_command(self, msg):
        """
        docstring

        """
        if len(msg['message']) == 1:
            logging.warning('Empty command provided, ignoring it')
            return

        # Extract command name from the message
        command = msg['message'].split()

        if command[0].upper() not in self.commands:
            # Silently ignore the command, as it could be a command
            # which is processed only by the server
            return

        self.commands[command[0].upper()](msg)

    def command_join(self, msg):
        """
        docstring

        """
        # Join only to the first room provided
        room = msg['message'].split()[1]

        if not room:
            logging.warning('No room provided for /JOIN command')
            return

        if not room.startswith('#'):
            room = '#' + room
            
        if room in self.rooms:
            logging.warning('You are already subscribed to %s', room)
            return

        logging.info('Subscribing to %s', room)
        self.backend_socket.setsockopt(zmq.SUBSCRIBE, room)

    def command_part(self, msg):
        """
        docstring

        """
        # Leave only from the first room provided
        room = msg['message'].split()[1]

        if not room:
            logging.warning('No room provided for /PART command')
        
        if not room.startswith('#'):
            room = '#' + room

        if room not in self.rooms:
            logging.warning('You are not subscribed to %s', room)
            return

        logging.info('Unsubscribing from %s', room)
        self.backend_socket.setsockopt(zmq.UNSUBSCRIBE, room)
        
    def command_quit(self, msg):
        """
        docstring

        """
        pass
