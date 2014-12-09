#!/usr/bin/env python2.7

from collections import deque
import logging
from lxml import html
import os.path


# TODO assert we have relative URLs everywhere, not absolute


def is_import_element(el):
    return el.tag == 'link' and el.attrib.get('rel') == 'import'


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


class ImportedHtml(object):

    def __init__(self, relative_url, path):
        self.relative_url = relative_url
        self.path = path
        self.tree = None
        self.head_tags = []
        self.polymer_elements = []

    def parse(self):
        self.tree = html.parse(self.path, base_url=self.relative_url)
        self.head_tags = self.tree.findall('/head/*')
        self.polymer_elements = self.tree.findall('/body/polymer-element')

    @property
    def dependencies(self):
        for el in self.head_tags:
            if is_import_element(el):
                yield el.attrib.get('href')


class ImportedScript(object):

    def __init__(self, parent_relative_url, parent_path, script_el):
        try:
            script_src = script_el.attrib['src']
        except KeyError:
            self.text = script_el.text
        else:
            script_path = relative_url_to_path(
                parent_relative_url, parent_path, script_src)
            self.text = open(script_path).read()


def traverse(relative_url, path):
    root = ImportedHtml(relative_url, path)
    root.parse()
    all_nodes = [root]
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
            dep_node = ImportedHtml(dep, dep_path)
            all_nodes.append(dep_node)
            to_process.append(dep_node)

    return all_nodes


def merge_nodes(all_nodes):
    head_tags = []
    polymer_elements = []
    scripts = []

    for dep_node in all_nodes:
        for el in dep_node.head_tags:
            if is_import_element(el):
                pass
            elif el.tag == 'script':
                el.getparent().remove(el)
                scripts.append(ImportedScript(
                    dep_node.relative_url, dep_node.path, el))
            else:
                head_tags.append(el)

        for el in dep_node.polymer_elements:
            for script_el in el.findall('script'):
                el.remove(script_el)
                scripts.append(ImportedScript(
                    dep_node.relative_url, dep_node.path, script_el))
            polymer_elements.append(el)

    return head_tags, polymer_elements, scripts


# def combined_scripts(scripts):
#     result_script = []
#     for el in scripts:
#         if el.attrib.get('src'):

#         else:
#             result_script.append(el.text)


logging.getLogger().setLevel(logging.DEBUG)

all_nodes = traverse('index.html', './example/index.html')
head_tags, polymer_elements, scripts = merge_nodes(all_nodes)

print scripts
