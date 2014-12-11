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

from collections import deque, namedtuple
from copy import deepcopy
from cStringIO import StringIO
import logging
from lxml import html
import os.path
import re


class Error(Exception):
    pass


class InvalidScriptError(Error):
    pass


class InvalidLinkError(Error):
    pass


# TODO: Handle no-script Polymer elements that don't explicitly call Polymer()
# TODO: Rewrite Polymer() constructor calls.

class ImportedFile(object):

    def __init__(self, relative_url, path, el):
        self.relative_url = relative_url
        self.path = path
        self.el = el

    def __repr__(self):
        return '%s(relative_url=%r, path=%r)' % (
            self.__class__.__name__, self.relative_url, self.path)


class ImportedHtml(ImportedFile):

    def __init__(self, relative_url, path):
        super(ImportedHtml, self).__init__(relative_url, path, None)
        self.dependencies = []
        self.script_tags = []
        self.link_tags = []
        self.polymer_tags = []
        self.head_tags = []
        self.body_tags = []

    def parse(self):
        self.el = html.parse(self.path)

        seen_tags = set()

        self.script_tags = self.el.findall('//script')
        seen_tags.update(self.script_tags)

        found_links = self.el.findall('//link')
        seen_tags.update(found_links)

        for el in found_links:
            if el.attrib.get('rel') == 'import':
                href = el.attrib.get('href')
                if (href.startswith('http://') or
                        href.startswith('https://') or
                        href.startswith('/')):
                    # Let links to absolute URLs pass through to the
                    # final vulcanized document.
                    self.link_tags.append(el)
                else:
                    # It's fine if there are duplicates in this list.
                    # They'll get deduped at merge time.
                    self.dependencies.append(href)
            else:
                self.link_tags.append(el)

        self.polymer_tags = self.el.findall('//polymer-element')
        seen_tags.update(self.polymer_tags)

        # Save everything from head and body that aren't tags we've
        # already seen through the xpath queries above.
        for el in self.el.findall('/head/*'):
            if el in seen_tags:
                continue
            else:
                self.head_tags.append(el)

        for el in self.el.findall('/body/*'):
            if el in seen_tags:
                continue
            else:
                self.body_tags.append(el)


class ImportedScript(ImportedFile):

    def __init__(self, script_el, text=None, relative_url=None, path=None):
        super(ImportedScript, self).__init__(relative_url, path, script_el)
        self.text = text

    def parse(self):
        parent = self.el.xpath('ancestor::polymer-element')
        if not parent:
            return

        assert len(parent) == 1
        parent = parent[0]

        name = parent.attrib['name']
        match = re.search(
            r'Polymer\(\s*([\'\"]([^\'\"]+)[\'\"]\s*)?\s*([^\)])?',
            self.text)
        if not match:
            return

        has_name, found_name, closing = match.groups()
        logging.info('Groups are: %r', match.groups())
        if has_name:
            assert found_name == name
            return

        before = self.text[:match.start()]
        after = self.text[match.end():]

        if closing:
            middle = ', '
        else:
            closing = ''
            middle = ''

        self.text = "%sPolymer('%s'%s%s%s" % (
            before, name, middle, closing, after)

    def __repr__(self):
        if self.path:
            return 'ImportedScript(path=%r)' % self.path
        elif self.text:
            return 'ImportedScript(%r)' % self.text
        else:
            assert False, 'Bad ImportedScript'


class ImportedLink(ImportedFile):

    def __init__(self, relative_url, link_el):
        super(ImportedLink, self).__init__(relative_url, path=None, el=link_el)


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
        imported_file = ImportedHtml(relative_url, path)
        imported_file.parse()
        return imported_file

    def resolve_script(self, parent_relative_url, script_el):
        try:
            script_type = script_el.attrib['type']
        except KeyError:
            pass  # Defaults to JavaScript
        else:
            if script_type.lower() != 'text/javascript':
                raise InvalidScriptError(html.tostring(script_el))

        try:
            script_src = script_el.attrib['src']
        except KeyError:
            # The script is inline.
            tag = ImportedScript(script_el, text=script_el.text)
            tag.parse()
            return tag
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

    def resolve_link(self, parent_relative_url, link_el):
        try:
            rel = link_el.attrib['rel']
            href = link_el.attrib['href']
        except KeyError:
            raise InvalidLinkError(html.tostring(link_el))

        relative_url, _ = self.get_path(
            href, parent_relative_url=parent_relative_url)

        return ImportedLink(relative_url, link_el)


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

    def get_source_line(self, relative_url, line_number):
        path = self.index[relative_url]
        open(path).read()


def traverse(node, resolver, file_index):
    """
    Breadth-first search. Order of returned nodes matters because
    that's dependency order.
    """
    if not file_index.add(node.relative_url, node.path):
        return []

    all_nodes = []

    for relative_url in node.dependencies:
        dep = resolver.resolve_html(
            relative_url, parent_relative_url=node.relative_url)
        all_nodes.extend(traverse(dep, resolver, file_index))

    return all_nodes + [node]


MergedDependencies = namedtuple(
    'MergedDependencies',
    ['head_tags', 'polymer_tags', 'script_tags', 'link_tags'])


def merge_nodes(all_nodes, file_index, resolver):
    """
    Order of returned values matters because that's in dependency order
    based on the supplied nodes.
    """
    head_tags = []
    polymer_tags = []
    script_tags = []
    link_tags = []

    for dep_node in all_nodes:
        head_tags.extend(dep_node.head_tags)
        polymer_tags.extend(dep_node.polymer_tags)

        for el in dep_node.script_tags:
            try:
                script = resolver.resolve_script(dep_node.relative_url, el)
            except InvalidScriptError as e:
                logging.debug('Ignoring invalid script: %r', str(e))
                continue

            if (script.relative_url is not None and
                    not file_index.add(script.relative_url, script.path)):
                continue
            script_tags.append(script)

        for el in dep_node.link_tags:
            try:
                link = resolver.resolve_link(dep_node.relative_url, el)
            except InvalidLinkError as e:
                logging.debug('Ignoring invalid link: %r', str(e))
                continue

            if (link.relative_url is not None and
                    not file_index.add(link.relative_url, link.path)):
                continue
            link_tags.append(link)

    return MergedDependencies(
        head_tags=head_tags,
        polymer_tags=polymer_tags,
        script_tags=script_tags,
        link_tags=link_tags)


def assemble_scripts(merged):
    output = StringIO()
    for tag in merged.script_tags:
        output.write(tag.text)
        output.write(';\n')
    return output.getvalue()


def assemble(root_file, merged):
    root_el = html.Element('html')

    head_el = html.Element('head')
    root_el.append(head_el)

    for tag in root_file.head_tags:
        copied = deepcopy(tag)
        head_el.append(copied)

    for tag in merged.link_tags:
        copied = deepcopy(tag.el)
        # Clear any funky tail text that may be after certain html elements
        # like <link> with no closing </link> tag.
        copied.tail = ''
        head_el.append(copied)

    body_el = html.Element('body')
    root_el.append(body_el)

    hidden_el = html.Element('div', attrib={'hidden': 'hidden'})
    body_el.append(hidden_el)

    for tag in merged.polymer_tags:
        copied = deepcopy(tag)
        # Remove any child script and link tags from Polymer elements because
        # these will already exist in the vulcanized file or head.
        for el in copied.findall('script'):
            copied.remove(el)
        for el in copied.findall('link'):
            copied.remove(el)
        hidden_el.append(copied)

    for tag in root_file.body_tags:
        copied = deepcopy(tag)
        body_el.append(copied)

    # TODO: Split this into a separate file that can have a sourcemap.
    combined_script = StringIO()

    for tag in merged.script_tags:
        if tag.text:
            combined_script.write(tag.text)
            combined_script.write('\n;\n')
        elif tag.path:
            with open(tag.path) as handle:
                combined_script.write(handle.read())
                combined_script.write('\n;\n')
        else:
            # This is an external script that can't be resolved to
            # a local path and thus can't be vulcanized.
            copied = deepcopy(tag.el)
            head_el.append(copied)

    script_source = combined_script.getvalue()
    # Escape any </script> close tags because those will break the parser.
    # Notably, CDATA is ignored with HTML5 parsing rules, so that can't help.
    script_source = script_source.replace('</script>', '<\/script>')

    combined_el = html.Element('script', attrib={'type': 'text/javascript'})
    combined_el.text = script_source.decode('utf-8')
    body_el.append(combined_el)

    return root_el


logging.getLogger().setLevel(logging.DEBUG)

resolver = PathResolver('', './')
root_file = resolver.resolve_html('index.html')
file_index = FileIndex()
all_nodes = traverse(root_file, resolver, file_index)
merged = merge_nodes(all_nodes, file_index, resolver)
root_el = assemble(root_file, merged)

print html.tostring(root_el, doctype='<!doctype html>')

# import pdb; pdb.set_trace()
