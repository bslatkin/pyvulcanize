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

from lxml import etree
from lxml import html

from . import errors
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
            logging.debug('Traversing %.60r...', html.tostring(el))

            try:
                dep = self.import_tag(node.relative_url, el)
            except errors.InvalidScriptError as e:
                logging.debug('Removing invalid script: %r', str(e))
                remove_node(el)
                continue
            except errors.InvalidLinkError as e:
                logging.debug('Removing invalid link: %r', str(e))
                remove_node(el)
                continue

            if (dep.is_included_resource and
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
    if parent is None:
        return

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

    combined_head_script = StringIO()
    combined_body_script = StringIO()

    for tag in traverse(root_file):
        logging.debug('Assembling %r', tag)

        if isinstance(tag, importer.ImportedLink):
            if tag.replacement is not None:
                # CSS that can be inlined.
                if tag.polymer_element_ancestor is not None:
                    # Inlined directly into the polymer-element so it's
                    # part of that template's shadow dom.
                    tag.el.addprevious(tag.replacement)
                    remove_node(tag.el)
                else:
                    # Can be inlined, but must be put into head because
                    # it didn't appear within a polymer-element.
                    remove_node(tag.el)
                    head_el.append(tag.replacement)
            else:
                # External link that can't be vulcanized.
                copied = copy_clean(tag.el)
                remove_node(tag.el)
                head_el.append(copied)
        elif isinstance(tag, importer.ImportedStyle):
            # Move the style tag to the root if it's not part of a
            # polymer element.
            if tag.polymer_element_ancestor is None:
                copied = copy_clean(tag.el)
                remove_node(tag.el)
                head_el.append(copied)
        elif isinstance(tag, importer.ImportedScript):
            if not tag.is_included_resource:
                remove_node(tag.el)
                if tag.polymer_element_ancestor is not None:
                    combined_body_script.write(tag.text)
                    combined_body_script.write('\n;\n')
                else:
                    combined_head_script.write(tag.text)
                    combined_head_script.write('\n;\n')
            else:
                # External script that can't be vulcanized.
                copied = copy_clean(tag.el)
                remove_node(tag.el)
                head_el.append(copied)
        elif isinstance(tag, importer.ImportedPolymerElement):
            copied = copy_clean(tag.el)
            remove_node(tag.el)
            hidden_el.append(copied)
        elif isinstance(tag, importer.ImportedHtml):
            for child_tag in tag.body_tags:
                copied = copy_clean(child_tag)
                remove_node(child_tag)
                body_el.append(copied)

    # Add the head tags in last, after all of the calls to remove_node above
    # have been able to copy tail text around in the original documents as
    # necessary. The head tags will go in before all of the other content that's
    # already in there.
    for tag in reversed(root_file.head_tags):
        head_el.insert(0, tag)

    # TODO: Split these into separate files that can have sourcemaps.

    head_script_el = html.Element('script', attrib={'type': 'text/javascript'})
    head_script_el.text = combined_head_script.getvalue().decode('utf-8')
    # The head script must come before *everything* else because polymer is
    # sensitive about other resources that are loading from remote URLs, such
    # as link tags.
    head_el.insert(0, head_script_el)

    body_script_el = html.Element('script', attrib={'type': 'text/javascript'})
    body_script_el.text = combined_body_script.getvalue().decode('utf-8')
    body_el.append(body_script_el)

    return root_el
