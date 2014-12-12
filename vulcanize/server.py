#!/usr/bin/env python2.7
#
# Copyright 2014 Brett Slatkin
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import SimpleHTTPServer
import SocketServer
import logging
import os
import signal
import sys
import threading
import time

from . pipeline import vulcanize


def get_handler(root_dir, index_path):
    """Wraps the parameters for the server in a closure."""

    class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.wfile.write(vulcanize(root_dir, index_path))
            else:
                return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    return Handler


def run_server(host, port, root_dir, index_path):
    handler = get_handler(root_dir, index_path)
    server = SocketServer.TCPServer((host, port), handler)
    host, port = server.server_address
    logging.info('Serving on %s:%d', host, port)

    threading.Thread(target=server.serve_forever).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info('Terminating')
        server.shutdown()
