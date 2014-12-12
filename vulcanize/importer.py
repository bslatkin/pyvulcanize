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
import logging
import os.path
import re
import warnings

import html5lib
from html5lib import ihatexml
from html5lib.constants import DataLossWarning
from lxml import html

from . import errors

# Ignore coertion warnings from html5lib. This happens because of foo ?= "bar"
# conditional attribute expressions in the HTML documents. We compensate for
# this in pipeline.py when we reserialize the document.
warnings.simplefilter('ignore', DataLossWarning)


def polymer_element_ancestor(el):
    for parent_el in reversed(el.xpath('ancestor::*')):
        if parent_el.tag == 'polymer-element':
            return parent_el
    return None


class ImportedTag(object):

    def __init__(self, relative_url=None, path=None, el=None):
        self.relative_url = relative_url
        self.path = path
        self.el = el
        self.resource_tags = []
        self.polymer_element_ancestor = None

    def parse(self):
        pass

    @property
    def is_included_resource(self):
        return self.relative_url is not None

    def __repr__(self):
        return '%s(relative_url=%r, path=%r, el=%r)' % (
            self.__class__.__name__, self.relative_url, self.path, self.el)


class ImportedHtml(ImportedTag):

    def __init__(self, relative_url, path):
        super(ImportedHtml, self).__init__(
            relative_url=relative_url, path=path)
        self.head_tags = []
        self.body_tags = []

    def parse(self):
        tree_builder = html5lib.getTreeBuilder('lxml')
        parser = html5lib.HTMLParser(
            namespaceHTMLElements=False,
            tree=tree_builder,
            debug=True)
        with open(self.path) as handle:
            self.el = parser.parse(
                handle,
                encoding='utf-8')

        seen_tags = set()

        # Consider scripts and links in the order they appear in the document.
        for el in self.el.findall('//*'):
            if el.tag not in ('script', 'link', 'style'):
                continue
            if polymer_element_ancestor(el) is not None:
                # Ignore scripts and links that appear within a polymer
                # element tag. Those will be handled by ImportedPolymerElement.
                continue
            if el not in seen_tags:
                seen_tags.add(el)
                self.resource_tags.append(el)

        for el in self.el.findall('//polymer-element'):
            seen_tags.add(el)
            self.resource_tags.append(el)

        # Save everything from head and body that aren't tags we've
        # already seen through the xpath queries above.
        for el in self.el.findall('/head/*'):
            if el not in seen_tags:
                seen_tags.add(el)
                self.head_tags.append(el)

        for el in self.el.findall('/body/*'):
            if el not in seen_tags:
                seen_tags.add(el)
                self.body_tags.append(el)


class ImportedScript(ImportedTag):

    def __init__(self, script_el, text=None, relative_url=None, path=None):
        super(ImportedScript, self).__init__(
            relative_url=relative_url, path=path, el=script_el)
        self.text = text

    def parse(self):
        if self.text:
            # Escape any </script> close tags because those will break the
            # parser. Notably, CDATA is ignored with HTML5 parsing rules, so
            # that can't help.
            self.text = self.text.replace('</script>', '<\/script>')

        self.rewrite_name()

        # Rewrite relative URLs to be relative to the index file.
        if self.relative_url:
            self.el.attrib['src'] = self.relative_url

    def rewrite_name(self):
        # Determine if we need to rewrite a Polymer() constructor.
        parent = polymer_element_ancestor(self.el)
        if parent is None:
            return

        name = parent.attrib['name']
        match = re.search(
            r'Polymer\(\s*([\'\"]([^\'\"]+)[\'\"]\s*)?\s*([^\)])?',
            self.text)
        if not match:
            return

        has_name, found_name, closing = match.groups()
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

    @property
    def is_included_resource(self):
        return self.el.attrib.get('src') is not None

    def __repr__(self):
        if self.is_included_resource:
            return 'ImportedScript(relative_url=%r)' % self.relative_url
        elif self.text:
            return 'ImportedScript(%.40r...)' % self.text
        else:
            assert False, 'Bad ImportedScript'


class ImportedLink(ImportedTag):

    def __init__(self, relative_url, link_el, path=None):
        super(ImportedLink, self).__init__(
            relative_url=relative_url, path=path, el=link_el)
        self.replacement = None

    def parse(self):
        if not self.path:
            return

        if self.el.attrib.get('rel') != 'stylesheet':
            return

        attrib = {}
        for key, value in self.el.attrib.iteritems():
            if key in ('rel', 'href', 'type'):
                continue
            attrib[key] = value

        self.replacement = html.Element('style', attrib=attrib)

        output = StringIO()
        output.write('\n/* From %s */\n' % self.relative_url)

        with open(self.path) as handle:
            output.write(handle.read())

        self.replacement.text = output.getvalue()

        # TODO: Rewrite url() in the included file in case the path of the
        # link is different than the path of what included it.

        # TODO: transitively include @import references?


class ImportedStyle(ImportedTag):

    def __init__(self, style_el):
        super(ImportedStyle, self).__init__(
            relative_url=None, path=None, el=style_el)

    @property
    def is_included_resource(self):
        return False


class ImportedPolymerElement(ImportedTag):

    def __init__(self, parent_relative_url, polymer_el):
        super(ImportedPolymerElement, self).__init__(
            relative_url=parent_relative_url, path=None, el=polymer_el)

    def parse(self):
        # TODO: Handle no-script Polymer elements that don't explicitly
        # call Polymer() in a child script tag.

        for child_el in self.el.findall('.//*'):
            if child_el.tag not in ('script', 'link'):
                continue
            self.resource_tags.append(child_el)

    @property
    def is_included_resource(self):
        return False


class PathResolver(object):

    def __init__(self, root_dir, index_path):
        self.index_path = index_path
        self.root_dir = root_dir

        abs_dir = os.path.abspath(self.root_dir)
        abs_index = os.path.abspath(self.index_path)
        index_relative_url = abs_index[len(abs_dir) + 1:]

        self.index_relative_url = index_relative_url
        self.root_url = os.path.dirname(index_relative_url)

    def __call__(self, relative_url, parent_relative_url=None):
        if (relative_url.startswith('http://') or
                relative_url.startswith('https://') or
                relative_url.startswith('/')):
            return relative_url, None

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

        return (normalized_relative_url,
                os.path.join(self.root_dir, normalized_relative_url))


class Importer(object):

    def __init__(self, resolve):
        self.resolve = resolve

    def __call__(self, parent_relative_url, el):
        if el.tag == 'script':
            result = self.import_script(parent_relative_url, el)
        elif el.tag == 'link':
            rel = el.attrib.get('rel')
            href = el.attrib.get('href')
            if (rel == 'import' and not
                    (href.startswith('http://') or
                     href.startswith('https://') or
                     href.startswith('/'))):
                # Locally resolve any imports that aren't absolute paths.
                result = self.import_html(
                    href, parent_relative_url=parent_relative_url)
            else:
                result = self.import_link(parent_relative_url, el)
        elif el.tag == 'polymer-element':
            result = self.import_polymer_element(parent_relative_url, el)
        elif el.tag == 'style':
            result = self.import_style(parent_relative_url, el)
        else:
            assert False

        result.polymer_element_ancestor = polymer_element_ancestor(el)
        result.parse()
        return result

    def import_html(self, relative_url, parent_relative_url=None):
        relative_url, path = self.resolve(
            relative_url, parent_relative_url=parent_relative_url)
        logging.debug('Dependency %r of %r has file path %r',
                      relative_url, parent_relative_url, path)
        return ImportedHtml(relative_url, path)

    def import_script(self, parent_relative_url, script_el):
        try:
            script_type = script_el.attrib['type']
        except KeyError:
            pass  # Defaults to JavaScript
        else:
            if script_type.lower() != 'text/javascript':
                raise errors.InvalidScriptError(html.tostring(script_el))

        try:
            script_src = script_el.attrib['src']
        except KeyError:
            # The script is inline.
            return ImportedScript(script_el, text=script_el.text)
        else:
            # The script is an external resource so we shouldn't vulcanize.
            relative_url, path = self.resolve(
                script_src, parent_relative_url=parent_relative_url)
            return ImportedScript(
                script_el, relative_url=relative_url, path=path)

    def import_link(self, parent_relative_url, link_el):
        try:
            rel = link_el.attrib['rel']
            href = link_el.attrib['href']
        except KeyError:
            raise errors.InvalidLinkError(html.tostring(link_el))

        relative_url, path = self.resolve(
            href, parent_relative_url=parent_relative_url)

        return ImportedLink(relative_url, link_el, path=path)

    def import_polymer_element(self, parent_relative_url, polymer_el):
        return ImportedPolymerElement(
            parent_relative_url, polymer_el)

    def import_style(self, parent_relative_url, style_el):
        return ImportedStyle(style_el)
