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

from collections import deque
from copy import deepcopy
import logging
from lxml import html
import os.path


class Error(Exception):
    pass


class InvalidScriptError(Error):
    pass


# TODO: assert we have relative URLs everywhere, not absolute
# TODO: Don't manipulate the original etrees because we want to be able to
# generate sourcemaps that point back to the original script locations.
# TODO: Explicitly import style and link tags from children, ignore everything
# else. Only preserve other head tags from the root file.

def is_import_element(el):
    return el.tag == 'link' and el.attrib.get('rel') == 'import'


def is_polymer_element(el):
    return el.tag == 'polymer-element'


class ImportedHtml(object):

    def __init__(self, relative_url, path):
        self.relative_url = relative_url
        self.path = path
        self.tree = None
        self.head_tags = []
        self.polymer_elements = []
        self.dependencies = []

    def parse(self):
        self.tree = html.parse(self.path, base_url=self.relative_url)

        for el in self.tree.findall('/head/*'):
            if not is_import_element(el) and not is_polymer_element(el):
                self.head_tags.append(el)

        self.polymer_elements = self.tree.findall('//polymer-element')

        import_links = self.tree.findall('//link[@rel="import"]')
        for el in import_links:
            href = el.attrib.get('href')
            if (href.startswith('http://') or
                    href.startswith('https://') or
                    href.startswith('/')):
                continue
            else:
                self.dependencies.append(href)

    def __repr__(self):
        return 'ImportedHtml(relative_url=%r, path=%r)' % (
            self.relative_url, self.path)


class ImportedScript(object):

    def __init__(self, script_el, text=None, relative_url=None, path=None):
        self.el = script_el
        self.relative_url = relative_url
        self.path = path
        self.text = text

    def __repr__(self):
        if self.path:
            return '<Contents of %r>' % self.path
        elif self.text:
            return repr(self.text)
        elif self.el is not None:
            return html.tostring(self.el)
        else:
            assert False, 'Bad ImportedScript'


class PathResolver(object):

    def __init__(self, index_relative_url, index_path):
        self.index_relative_url = index_relative_url
        self.index_path = index_path
        self.root_url = os.path.dirname(index_relative_url)
        self.root_dir = os.path.dirname(index_path)

    def get_path(self, relative_url, parent_relative_url=None):
        if parent_relative_url is None:
            # This means we're dealing with a root dependency with no parent.
            # Assume the relative_url is already resolved.
            resolved_relative_url = relative_url
        else:
            # Resolve the other_relative_url in the same directory as
            # the parent_relative_url.
            resolved_relative_url = os.path.join(
                os.path.dirname(parent_relative_url), relative_url)

        # Normalize and remove '..' and other relative path pieces.
        normalized_relative_url = os.path.normpath(resolved_relative_url)

        # Strip the common prefix of the URL serving. What's left relative to
        # the path directory is the path to the file on disk.
        relative_path = normalized_relative_url[len(self.root_url):]

        return (normalized_relative_url,
                os.path.join(self.root_dir, relative_path))

    def resolve_html(self, relative_url, parent_relative_url=None):
        relative_url, path = self.get_path(
            relative_url, parent_relative_url=parent_relative_url)
        logging.debug('Dependency %r of %r has file path %r',
                      relative_url, parent_relative_url, path)
        return ImportedHtml(relative_url, path)

    def resolve_script(self, parent_relative_url, script_el):
        try:
            script_type = script_el.attrib['type']
        except KeyError:
            pass  # Defaults to JavaScript
        else:
            if script_type.lower() != 'text/javascript':
                raise InvalidScriptError(script_type)

        try:
            script_src = script_el.attrib['src']
        except KeyError:
            # The script is inline.
            return ImportedScript(script_el, text=script_el.text)
        else:
            if (script_src.startswith('http://') or
                script_src.startswith('https://')):
                # The script is an external resource we can't vulcanize.
                return ImportedScript(script_el)
            else:
                # The script is a local resource we should vulcanize.
                logging.debug('Found script %r in %r',
                              script_src, parent_relative_url)
                relative_url, path = self.get_path(
                    script_src, parent_relative_url=parent_relative_url)
                logging.debug('Script %r from %r has file path %r',
                              relative_url, parent_relative_url, path)
                return ImportedScript(
                    script_el, relative_url=relative_url, path=path)


class FileIndex(object):

    def __init__(self):
        self.index = {}

    def add(self, relative_url, path):
        assert relative_url
        assert path
        if relative_url in self.index:
            logging.debug('Already seen %r', path)
            return False
        self.index[relative_url] = path
        logging.debug('New file %r', path)
        return True

    def get_source_line(self, relative_url, line_number):
        path = self.index[relative_url]
        open(path).read()


def traverse(root, resolver):
    """
    Breadth-first search. Order of returned nodes matters because
    that's dependency order.
    """
    all_nodes = [root]
    file_index = FileIndex()
    to_process = deque([root])

    while to_process:
        node = to_process.popleft()
        node.parse()
        if not file_index.add(node.relative_url, node.path):
            continue

        all_nodes.append(node)

        for relative_url in node.dependencies:
            dep = resolver.resolve_html(
                relative_url, parent_relative_url=node.relative_url)
            to_process.append(dep)

    return all_nodes, file_index


def merge_nodes(all_nodes, file_index, resolver):
    """
    Order of returned values matters because that's in dependency order
    based on the supplied nodes.
    """
    head_tags = []
    polymer_elements = []
    scripts = []

    for dep_node in all_nodes:
        script_elements = []

        for el in dep_node.head_tags:
            if el.tag == 'script':
                script_elements.append(el)
            else:
                head_tags.append(el)

        for el in dep_node.polymer_elements:
            polymer_elements.append(el)
            script_elements.extend(el.findall('script'))

        for el in script_elements:
            try:
                script = resolver.resolve_script(dep_node.relative_url, el)
            except InvalidScriptError as e:
                logging.debug('Ignoring invalid script type %s', e)

            if (script.relative_url is not None and
                    not file_index.add(script.relative_url, script.path)):
                continue

            scripts.append(script)

    return head_tags, polymer_elements, scripts


def extract_body(root):
    body_nodes = root.tree.findall('//body')
    assert len(body_nodes) == 1
    return body_nodes[0]


TEMPLATE = """<!doctype html>
<html>
<head></head>
<body></body>
</html>
"""

def assemble(root_file, head_tags, polymer_elements, scripts):
    root_el = html.Element('html')

    head_el = html.Element('head')
    root_el.append(head_el)

    for tag in head_tags:
        copied = deepcopy(tag)
        head_el.append(copied)

    body_el = html.Element('body')
    root_el.append(body_el)

    hidden_el = html.Element('div', attrib={'hidden': 'hidden'})
    body_el.append(hidden_el)

    for tag in polymer_elements:
        copied = deepcopy(tag)
        # Remove all scripts from Polymer elements since these will
        # be in the vulcanized JS file.
        for el in copied.findall('script'):
            copied.remove(el)
        hidden_el.append(copied)

    print html.tostring(root_el)
    return root_el


logging.getLogger().setLevel(logging.DEBUG)

resolver = PathResolver('', './example/')
root_file = resolver.resolve_html('index.html')
all_nodes, file_index = traverse(root_file, resolver)
head_tags, polymer_elements, scripts = merge_nodes(
    all_nodes, file_index, resolver)

assemble(root_file, head_tags, polymer_elements, scripts)

import pdb; pdb.set_trace()
