"""
Lobby server module

"""

import logging
import threading

import zmq

from zmq.utils import jsonapi
from zmq.eventloop import ioloop, zmqstream

from pylobby.core import LobbyMember, LobbyRoom
from pylobby.exceptions import LobbyException

__all__ = ['LobbyServer']


class LobbyServer(object):
    """
    docstring

    """
    def __init__(self, endpoint):
        """
        docstring
        
        """
        self.discovery_endpoint = endpoint
        self.frontend_endpoint = None
        self.backend_endpoint = None

        self.ctx = zmq.Context()
        self.loop = ioloop.IOLoop.instance()

        self.discovery_socket = self.ctx.socket(zmq.ROUTER)
        self.frontend_socket = self.ctx.socket(zmq.ROUTER)
        self.backend_socket = self.ctx.socket(zmq.PUB)
        
        self.rooms = {}
        self.members = {}

        self.commands = {
            '/CONNECT': self.command_connect,
            '/JOIN': self.command_join,
            '/PART': self.command_part,
            '/QUIT': self.command_quit,
        }

    def start(self):
        """
        docstring

        """
        logging.info('Starting Lobby server')
        self.bind_endpoints()
        
        logging.info('Starting event loop')
        self.loop.start()
        
    def stop(self):
        """
        docstring

        """
        logging.info('Stopping Lobby server')

        self.loop.stop()
        self.discovery_stream.close()
        self.frontend_stream.close()
        self.discovery_socket.close()        
        self.frontend_socket.close()
        self.backend_socket.close()
        self.ctx.destroy()

    def send_to_identity(self, identity, **kwargs):
        """
        docstring

        """
        logging.debug(
            'Sending message to %s: %s',
            repr(identity),
            kwargs
        )
        self.frontend_stream.send_multipart(
            [identity, jsonapi.dumps(kwargs)]
        )

    def broadcast(self, **kwargs):
        if not kwargs.get('room'):
            logging.warning(
                'No room name provided, ignoring message %s',
                kwargs
            )
            return

        logging.debug(
            'Broadcasting message to %s: %s',
            kwargs['room'],
            kwargs
        )
        self.backend_socket.send_unicode(kwargs['room'], zmq.SNDMORE)
        self.backend_socket.send_json(kwargs)

    def bind_endpoints(self):
        """
        docstring

        """
        self.discovery_socket.bind(self.discovery_endpoint)

        self.frontend_port = self.frontend_socket.bind_to_random_port('tcp://*')
        self.backend_port = self.backend_socket.bind_to_random_port('tcp://*')
        self.endpoints = {
            'frontend': self.frontend_port,
            'backend': self.backend_port,
        }

        self.discovery_stream = zmqstream.ZMQStream(
            self.discovery_socket,
            self.loop
        )
        self.discovery_stream.on_recv(self.handle_discovery_messages)

        self.frontend_stream = zmqstream.ZMQStream(
            self.frontend_socket,
            self.loop
        )
        self.frontend_stream.on_recv(self.handle_frontend_messages)

        logging.info(
            'Discovery endpoint bound to %s',
            self.discovery_socket.getsockopt(zmq.LAST_ENDPOINT)
        )
        logging.info(
            'Frontend bound to %s',
            self.frontend_socket.getsockopt(zmq.LAST_ENDPOINT)
        )
        logging.info(
            'Backend bound to %s',
            self.backend_socket.getsockopt(zmq.LAST_ENDPOINT)
        )

    def handle_discovery_messages(self, data):
        """"
        docstring
        
        """
        logging.debug(
            'Received message on discovery stream: %s',
            data
        )

        identity = data[0]
        msg = [identity, jsonapi.dumps(self.endpoints)]

        logging.debug(
            'Sending discovery information to client: %s',
            msg
        )
        self.discovery_stream.send_multipart(msg)

    def handle_frontend_messages(self, data):
        """
        docstring

        Frame 0: [ N ][...]  <- Identity of connection
        Frame 1: [ N ][...]  <- Data frame

        """
        logging.debug(
            'Received message on frontend stream: %s',
            data
        )

        if not self.is_valid_message(data):
            logging.warning('Message validation failed')
            return

        identity, msg = data[0], jsonapi.loads(data[1])
        is_command = msg['message'].startswith('/')

        # Everything except for /CONNECT should have a valid identity
        if msg['message'].split()[0] != '/CONNECT':
            if not self.is_valid_identity(who=msg['who'], identity=identity):
                logging.warning('Invalid identity, ignoring message')
                return

        if is_command:
            self.process_cmd(msg=msg, identity=identity)
        else:
            self.broadcast(**msg)

    def is_valid_message(self, data):
        """
        docstring

        """
        logging.debug('Validating message: %s', data)

        if len(data) != 2:
            logging.warning('Too many frames received: %s', len(data))
            return False

        identity, msg = data
        try:
            msg = jsonapi.loads(msg)
        except (TypeError, ValueError) as e:
            logging.warning('Cannot decode message: %s', e)
            return False

        # Check for required message attributes
        required = ('who', 'message')
        if not all(k in msg for k in required):
            logging.warning('Required attributes missing in message')
            return False

        if not all(msg.get(k) for k in required):
            logging.warning('Empty data in message found')
            return False

        return True
        
    def is_valid_identity(self, who, identity):
        """
        docstring

        """
        logging.debug(
            'Validating identity of %s with id %s',
            who,
            repr(identity)
        )

        if who not in self.members:
            logging.debug('Member %s is unknown to me', who)
            return False

        if identity != self.members[who].identity:
            logging.warning('Identity mismatch for %s', who)
            return False

        return True

    def process_cmd(self, msg, identity):
        """
        docstring

        """
        if len(msg['message']) == 1:
            logging.warning('Empty command received, ignoring it')
            return

        # Extract command name from the message
        command = msg['message'].split()

        if command[0].upper() not in self.commands:
            self.send_to_identity(
                identity=identity,
                message='Unknown command: %s' % command[0].upper()
            )
            return

        self.commands[command[0].upper()](
            msg=msg,
            identity=identity
        )

    def command_connect(self, msg, identity):
        """
        docstring

        """
        who = msg['who']

        logging.info('Member registration request for %s', who)

        if who in self.members:
            logging.warning('Member %s is already registered', who)
            self.send_to_identity(
                identity=identity,
                message='Member %s is already registered' % who,
            )
            return

        self.members[who] = LobbyMember(
            name=who,    
            identity=identity,
        )

        logging.info('Member %s registered successfully', who)

    def command_join(self, msg, identity):
        """
        docstring

        """
        who = msg['who']
        room = msg['message'].split()[1] # Take only the first room

        if not room:
            logging.warning('No room provided for /JOIN command')
            self.send_to_identity(
                identity=identity,
                message='No room provided for /JOIN command'
            )
            return

        if room not in self.rooms:
            self.rooms[room] = LobbyRoom(name=room)
            self.rooms[room].members.append(who)
            logging.debug('New room created: %s', room)
        else:
            if who in self.rooms[room].members:
                logging.warning('Member is already subscribed to room %s', room)
                return
            else:
                self.rooms[room].members.append(who)

        self.broadcast(
            room=room,
            message='%s has joined %s' % (who, room)
        )
        logging.debug('%s has joined %s', who, room)

    def command_part(self, msg, identity):
        """
        docstring

        """
        who = msg['who']
        room = msg['message'].split()[1] # Take only the first room

        if not room:
            logging.debug('No room provided for /PART command')
            self.send_to_identity(
                identity=identity,
                message='No room provided for /PART command'
            )
            return

        if room not in self.rooms:
            logging.debug('Unknown room %s provided for /PART command', room)
            return

        if who not in self.rooms[room].members:
            logging.debug('Member %s is not subscribed to room %s', who, room)
            return

        self.rooms[room].members.pop(who)
        self.broadcast(
            room=room,
            message='%s has left %s', % (who, room)
        )
        self.debug('%s has left %s', who, room)

    def command_quit(self, msg, identity):
        """
        docstring

        """
        who = msg['who']

        if who not in self.members:
            logging.debug('Member %s is unknown to me', who)
            return

        # TODO: Upon /QUIT the client should /PART from all
        # subscribed rooms, but if that's not the case we might
        # want to /PART the user from here instead

        logging.info('%s has quit', who)
        self.members.pop(who)
