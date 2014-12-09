#!/usr/bin/env python2.7

from collections import deque
import logging
from lxml import html
import os.path


# TODO assert we have relative URLs everywhere, not absolute


def is_import_element(el):
    return el.tag == 'link' and el.attrib.get('rel') == 'import'


def is_polymer_element(el):
    return el.tag == 'polymer-element'


class PathResolver(object):

    def __init__(self, index_path, index_relative_url):
        self.index_path = index_path
        self.index_relative_url = index_relative_url
        self.root_dir = os.path.dirname(index_path)
        self.root_url = os.path.dirname(index_relative_url)

    def __call__(self, parent_relative_url, relative_url):
        # Resolve the other_relative_url in the same directory as
        # the parent_relative_url.
        resolved_relative_url = os.path.join(
            os.path.dirname(parent_relative_url), relative_url)
        # Normalize and remove '..' and other relative path pieces.
        normalized_relative_url = os.path.normpath(resolved_relative_url)

        # Strip the common prefix of the URL serving. What's left relative to
        # the path directory is the path to the file on disk.
        relative_path = normalized_relative_url[len(self.root_url):]
        return os.path.join(self.root_dir, relative_path)


class ImportedHtml(object):

    get_path = None

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

    get_path = None

    def __init__(self, parent_relative_url, script_el):
        self.el = None
        self.path = None
        self.text = ''
        try:
            script_type = script_el.attrib['type']
        except KeyError:
            pass  # Defaults to JavaScript
        else:
            if script_type.lower() != 'text/javascript':
                logging.debug('Ignoring invalid script tag with type %r',
                              script_type)
                return

        try:
            script_src = script_el.attrib['src']
        except KeyError:
            self.text = script_el.text
        else:
            if (script_src.startswith('http://') or
                script_src.startswith('https://')):
                self.el = script_el
            else:
                logging.debug('Found script %r in %r',
                              script_src, parent_relative_url)
                self.path = self.get_path(parent_relative_url, script_src)
                logging.debug('Script %r has file path %r',
                              script_src, self.path)
                self.text = open(self.path).read()

    def __repr__(self):
        if self.el:
            return html.tostring(self.el)
        elif self.path:
            return '<Contents of %r>' % self.path
        else:
            return repr(self.text)


def traverse(relative_url, index_path):
    root = ImportedHtml(relative_url, index_path)
    root.parse()
    all_nodes = [root]
    seen_paths = {root}
    to_process = deque([root])

    while to_process:
        print to_process
        node = to_process.popleft()
        for dep in node.dependencies:
            logging.debug('Found dependency %r in %r', dep, node.path)
            dep_path = node.get_path(node.relative_url, dep)
            logging.debug('Dependency %r has file path %r', dep, dep_path)
            if dep_path in seen_paths:
                logging.debug('%r already seen', dep_path)
                continue

            seen_paths.add(dep_path)
            dep_node = ImportedHtml(dep, dep_path)
            dep_node.parse()
            all_nodes.append(dep_node)
            to_process.append(dep_node)

    return all_nodes


def merge_nodes(all_nodes):
    head_tags = []
    polymer_elements = []
    scripts = []

    for dep_node in all_nodes:
        for el in dep_node.head_tags:
            if el.tag == 'script':
                el.getparent().remove(el)
                scripts.append(ImportedScript(dep_node.relative_url, el))
            else:
                head_tags.append(el)

        for el in dep_node.polymer_elements:
            for script_el in el.findall('script'):
                el.remove(script_el)
                scripts.append(ImportedScript(
                    dep_node.relative_url, script_el))
            polymer_elements.append(el)

    return head_tags, polymer_elements, scripts


logging.getLogger().setLevel(logging.DEBUG)

resolver = PathResolver('./example/index.html', 'index.html')
ImportedHtml.get_path = resolver
ImportedScript.get_path = resolver

all_nodes = traverse('index.html', './example/index.html')
head_tags, polymer_elements, scripts = merge_nodes(all_nodes)

print head_tags
print polymer_elements
print scripts
