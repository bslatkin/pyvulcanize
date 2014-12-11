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

from copy import deepcopy
from cStringIO import StringIO
import logging
from lxml import html

from . import importer


class FileIndex(object):

    def __init__(self):
        self.index = {}

    def add(self, relative_url, path):
        assert relative_url
        if relative_url in self.index:
            logging.debug('Already seen %r', relative_url)
            return False
        self.index[relative_url] = path
        logging.debug('New dependency %r', relative_url)
        return True


class Traverser(object):

    def __init__(self, import_tag):
        self.import_tag = import_tag
        self.file_index = FileIndex()

    def __call__(self, node):
        """
        Breadth-first search. Order of returned nodes matters because
        that's dependency order.
        """
        # After going depth-first on the resources, figure out which of
        # the script tags and link tags we need to track for this node.
        # We'll ignore anything here that was already included in a dependency
        # deeper in the graph.
        for el in node.resource_tags:
            try:
                dep = self.import_tag(node.relative_url, el)
            except importer.InvalidScriptError as e:
                logging.debug('Ignoring invalid script: %r', str(e))
                continue
            except importer.InvalidLinkError as e:
                logging.debug('Ignoring invalid link: %r', str(e))
                continue

            if (dep.relative_url is not None and
                    not self.file_index.add(dep.relative_url, dep.path)):
                # Resource already included.
                continue

            for child_dep in self(dep):
              yield child_dep

        yield node


def remove_node(el):
    """
    Clear any funky tail text that may be after certain html elements
    like <link> with no closing </link> tag.
    """
    parent = el.getparent()
    if not el.tail:
        parent.remove(el)
        return

    siblings = list(el.itersiblings(preceding=True))
    if len(siblings) > 0:
        siblings[0].tail += el.tail
        el.tail = ''
    else:
        parent.text += el.tail

    el.tail = ''
    parent.remove(el)


def assemble(root_file, traverse):
    root_el = html.Element('html')

    head_el = html.Element('head')
    root_el.append(head_el)

    for tag in root_file.head_tags:
        copied = deepcopy(tag)
        head_el.append(copied)

    body_el = html.Element('body')
    root_el.append(body_el)

    hidden_el = html.Element('div', attrib={'hidden': 'hidden'})
    body_el.append(hidden_el)

    for tag in root_file.body_tags:
        copied = deepcopy(tag)
        body_el.append(copied)

    combined_script = StringIO()

    for tag in traverse(root_file):
        logging.debug('Traversing %r', tag)

        if isinstance(tag, importer.ImportedLink):
            # External link that can't be vulcanized.
            copied = deepcopy(tag.el)
            copied.tail = ''
            head_el.append(copied)
        elif isinstance(tag, importer.ImportedScript):
            if tag.text:
                if tag.relative_url:
                    combined_script.write('\n// %s\n' % tag.relative_url)
                combined_script.write(tag.text)
                combined_script.write('\n;\n')
            else:
                # External link that can't be vulcanized.
                copied = deepcopy(tag.el)
                # Override the script tag's include URL to be relative to
                # the index file.
                logging.debug('Adding script src %r', html.tostring(tag.el))
                copied.attrib['src'] = tag.relative_url
                copied.tail = ''
                head_el.append(copied)
        elif isinstance(tag, importer.ImportedHtml):
            for child_tag in tag.polymer_tags:
                copied = deepcopy(child_tag)

                # Remove any child script and link tags from Polymer elements
                # because these will already exist in the vulcanized file or
                # head.
                for el in copied.findall('.//script'):
                    remove_node(el)
                for el in copied.findall('.//link'):
                    remove_node(el)

                hidden_el.append(copied)

    # TODO: Split this into a separate file that can have a sourcemap.
    combined_el = html.Element('script', attrib={'type': 'text/javascript'})
    combined_el.text = combined_script.getvalue().decode('utf-8')
    body_el.append(combined_el)

    return root_el
