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

from lxml import html
import os

from . import assembler
from . import importer


__all__ = ['vulcanize']


def vulcanize(root_dir, index_path):
    """Vulcanize the HTML file at the given path.

    Args:
        root_dir: Path to the directory root for vulcanizing.
        index_path: Path to the HTML file to vulcanize.

    Returns:
        String of the vulcanized file.

    Raises:
        IOError if the target index_path or any of its dependencies
        don't exist on disk.
    """
    resolver = importer.PathResolver(root_dir, index_path)
    import_tag = importer.Importer(resolver)
    root_file = import_tag.import_html(resolver.index_relative_url)
    root_file.parse()
    traverser = assembler.Traverser(import_tag)
    root_el = assembler.assemble(root_file, traverser)
    return html.tostring(root_el, doctype='<!doctype html>')
