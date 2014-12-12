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

"""Tool for vulcanizing resources in Polymer applications.

The current working directory will be used as the vulcanizing root.
"""

import argparse
import logging
import os
import sys

from . pipeline import vulcanize
from . server import run_server


class Flags(object):

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=__doc__,
            prog='vulcanize')
        self.parser.add_argument(
            '-v', '--verbose',
            help='Do verbose logging.',
            action='store_true',
            default=False)
        self.parser.add_argument(
            '-o', '--output',
            help='Write output to the given path instead of stdout.',
            action='store',
            default=None)
        self.parser.add_argument(
            '-a', '--host',
            help='Run a vulcanizing server on the given hostname.',
            action='store',
            type=str,
            default='')
        self.parser.add_argument(
            '-p', '--port',
            help='Run a vulcanizing server on the given port.',
            action='store',
            type=int,
            default=0)
        self.parser.add_argument(
            'index_path',
            help='Path to the index file to vulcanize.',
            type=str,
            action='store',
            default=None)

    def parse(self):
        self.parser.parse_args(namespace=self)
        if not self.index_path:
            self.parser.error('index_path required')
        if not os.path.isfile(self.index_path):
            self.parser.error('index_path %r does not exist' % self.index_path)


FLAGS = Flags()


def main():
    FLAGS.parse()

    if FLAGS.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if FLAGS.port:
        run_server(FLAGS.host, FLAGS.port, os.getcwd(), FLAGS.index_path)
        return 0

    result = vulcanize(os.getcwd(), FLAGS.index_path)

    if FLAGS.output:
        with open(FLAGS.output, 'wb') as handle:
            handle.write(result)
    else:
        print result

    return 0


if __name__ == '__main__':
    sys.exit(main())
