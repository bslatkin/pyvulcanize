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

from cStringIO import StringIO
import os

import html5lib

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

    walker = html5lib.getTreeWalker('lxml')
    stream = walker(root_el)
    serializer = html5lib.serializer.HTMLSerializer(
        quote_attr_values=True,
        sanitize=False,
        inject_meta_charset=False,
        resolve_entities=False,
        strip_whitespace=False,
        omit_optional_tags=False,
        minimize_boolean_attributes=True)

    output = StringIO()
    output.write('<!doctype html>\n')

    for token in serializer.serialize(stream, encoding='utf-8'):
        # This is super gross, but lxml is going to sanitize the input and
        # drop Polymer's conditional attribute names that look like:
        # foo ?= "bar". This code reverses the way html5lib coerces the
        # bad attribute values to something that lxml can handle.
        if token.endswith('U0003F'):
            token = token[:-len('U0003F')] + '?'

        output.write(token)

    return output.getvalue()
