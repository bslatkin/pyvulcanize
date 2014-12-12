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
        """Traverse all dependencies in the given node.

        Breadth-first search. Order of returned nodes matches document order.
        """
        # After going depth-first on the resources, figure out which of
        # the script tags and link tags we need to track for this node.
        # We'll ignore anything here that was already included in a dependency
        # deeper in the graph.
        for el in node.resource_tags:
            try:
                dep = self.import_tag(node.relative_url, el)
            except importer.InvalidScriptError as e:
                logging.debug('Removing invalid script: %r', str(e))
                remove_node(el)
                continue
            except importer.InvalidLinkError as e:
                logging.debug('Removing invalid link: %r', str(e))
                remove_node(el)
                continue

            if (dep.relative_url is not None and
                    not self.file_index.add(dep.relative_url, dep.path)):
                # Resource already included.
                continue

            for child_dep in self(dep):
              yield child_dep

        yield node


def remove_node(el):
    """Clear any funky tail text.

    This may come after certain html elements like <link>.
    """
    parent = el.getparent()
    if not el.tail:
        parent.remove(el)
        return

    siblings = list(el.itersiblings(preceding=True))
    if len(siblings) > 0:
        before = siblings[0]
        if not before.tail:
            before.tail = ''
        before.tail += el.tail
    else:
        if not parent.text:
            parent.text = ''
        parent.text += el.tail

    el.tail = ''
    parent.remove(el)


def copy_clean(el):
    copied = deepcopy(el)
    # Remove any tail text from the copied element since we only
    # want to move the tag around the document.
    copied.tail = ''
    return copied


def assemble(root_file, traverse):
    root_el = html.Element('html', attrib=root_file.el.getroot().attrib)

    head_el = html.Element('head')
    root_el.append(head_el)

    body_el = html.Element('body')
    root_el.append(body_el)

    hidden_el = html.Element('div', attrib={'hidden': 'hidden'})
    body_el.append(hidden_el)

    combined_script = StringIO()

    for tag in traverse(root_file):
        logging.debug('Traversing %r', tag)

        if isinstance(tag, importer.ImportedLink):
            if tag.replacement is not None:
                # CSS that can be inlined.
                tag.el.addprevious(tag.replacement)
                remove_node(tag.el)
            else:
                # External link that can't be vulcanized.
                copied = copy_clean(tag.el)
                remove_node(tag.el)
                head_el.append(copied)
        elif isinstance(tag, importer.ImportedStyle):
            # Move the style tag to the root.
            copied = copy_clean(tag.el)
            remove_node(tag.el)
            head_el.append(copied)
        elif isinstance(tag, importer.ImportedScript):
            if tag.text:
                remove_node(tag.el)
                if tag.relative_url:
                    combined_script.write('\n// %s\n' % tag.relative_url)
                combined_script.write(tag.text)
                combined_script.write('\n;\n')
            else:
                # External script that can't be vulcanized.
                copied = copy_clean(tag.el)
                remove_node(tag.el)
                head_el.append(copied)
        elif isinstance(tag, importer.ImportedPolymerElement):
            copied = copy_clean(tag.el)
            remove_node(tag.el)
            hidden_el.append(copied)

    # Add the head and body tags in last, after all of the calls to
    # remove_node above have been able to copy tail text around in the
    # original documents as necessary. The head tags will go in before
    # all of the other content that's already in there. The body tags will
    # go in natural document order.
    for tag in reversed(root_file.head_tags):
        head_el.insert(0, tag)

    for tag in root_file.body_tags:
        body_el.append(tag)

    # TODO: Split this into a separate file that can have a sourcemap.
    combined_el = html.Element('script', attrib={'type': 'text/javascript'})
    combined_el.text = combined_script.getvalue().decode('utf-8')
    body_el.append(combined_el)

    return root_el
