#!/usr/bin/env python

"""
An example showing how to start the Lobby Server

"""

import time
import logging

from pylobby.server import LobbyServer

def main():
    logging.basicConfig(
        format='[%(asctime)s - %(levelname)s/%(processName)s] %(message)s',
        level=logging.DEBUG
    )
    server = LobbyServer(endpoint='tcp://*:8888')

    logging.info('Press Ctrl-C to stop the Lobby Server ...')
    time.sleep(1)

    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

if __name__ == '__main__':
    main()
