#!/usr/bin/env python

"""
An example of using the LobbyClient class

"""

import time
import logging

from pylobby.client import LobbyClient

def main():
    who = 'testuser'
    room = '#general'

    logging.basicConfig(
        format='[%(asctime)s - %(levelname)s/%(processName)s] %(message)s',
        level=logging.DEBUG
    )

    client = LobbyClient(
        who=who,
        endpoint='tcp://127.0.0.1:8888',
        join=[room]
    )
    client.start()

    time.sleep(1)
    logging.info('Press Ctrl-C to stop the Lobby Client ...')

    while True:
        try:
            msg = raw_input('%s > ' % who)
            client.say(room=room, message=msg)
        except KeyboardInterrupt:
            client.say(message='/QUIT')
            break

    logging.info('You have received %s public messages', client.inbox.qsize())
    logging.info('You have received %s private messages', client.priv_inbox.qsize())
    client.stop()

if __name__ == '__main__':
    main()
