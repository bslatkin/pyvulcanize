#!/usr/bin/env python2.7

from collections import deque
import logging
from lxml import html
import os.path


class ImportedFile(object):

    def __init__(self, relative_url, path):
        self.relative_url = relative_url
        self.path = path
        self.tree = None
        self.head_resources = []
        self.polymer_elements = []

    def parse(self):
        self.tree = html.parse(self.path, base_url=self.relative_url)
        self.head_resources = self.tree.findall('/head/*')
        self.polymer_elements = self.tree.findall('/body/polymer-element')

    @property
    def dependencies(self):
        for el in self.head_resources:
            if (el.tag == 'link' and el.attrib.get('rel') == 'import'):
                yield el.attrib.get('href')


def relative_url_to_path(relative_url, path, other_relative_url):
    # Resolve the other_relative_url in the same directory as
    # the relative_url.
    dep_relative_url = os.path.join(
        os.path.dirname(relative_url), other_relative_url)

    # Determine what's unique about the other_relative_url's path
    # with respect to the relative_url. This should leave the common
    # prefix of the webserving directory.
    if '/' in dep_relative_url and relative_url:
        prefix = os.path.commonprefix([dep_relative_url, relative_url])
    else:
        prefix = ''

    # Strip the common prefix of the URL serving. What's left relative to
    # the path directory is the path to the file on disk.
    dep_relative_path = dep_relative_url[len(prefix):]
    dep_path = os.path.join(os.path.dirname(path), dep_relative_path)
    return dep_path


def traverse(relative_url, path):
    root = ImportedFile(relative_url, path)
    root.parse()
    all_nodes = {root}
    seen_paths = {root}
    to_process = deque([root])
    while to_process:
        node = to_process.popleft()
        for dep in node.dependencies:
            logging.debug('Found dependency %r in %r', dep, node.path)
            dep_path = relative_url_to_path(node.relative_url, node.path, dep)
            logging.debug('Dependency %r has file path %r', dep, dep_path)
            if dep_path in seen_paths:
                logging.debug('%r already seen', dep_path)
                continue
            seen_paths.add(dep_path)
            dep_node = ImportedFile(dep, dep_path)
            all_nodes.add(dep_node)
            to_process.append(dep_node)
    return all_nodes


logging.getLogger().setLevel(logging.DEBUG)

traverse('index.html', './example/index.html')
