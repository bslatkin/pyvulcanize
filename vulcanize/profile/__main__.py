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

"""Tool for profiling the vulcanize tool."""

import argparse
from cProfile import Profile
import logging
import os
import pstats
import sys

from .. pipeline import vulcanize


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
            '-i', '--iterations',
            help='Number of iterations to run for the performance test.',
            action='store',
            type=int,
            default=10)
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


def run():
    for i in xrange(FLAGS.iterations):
        vulcanize(os.getcwd(), FLAGS.index_path)


def main():
    FLAGS.parse()

    if FLAGS.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    profiler = Profile()
    profiler.runcall(run)

    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    stats.print_stats(.1)
    stats.print_callers(.1)

    return 0


if __name__ == '__main__':
    sys.exit(main())
