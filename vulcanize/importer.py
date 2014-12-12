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


class ImportedTag(object):

    def __init__(self, relative_url, path, el):
        self.relative_url = relative_url
        self.path = path
        self.el = el
        self.resource_tags = []

    def parse(self):
        pass

    def __repr__(self):
        return '%s(relative_url=%r, path=%r, el=%r)' % (
            self.__class__.__name__, self.relative_url, self.path, self.el)


class ImportedHtml(ImportedTag):

    def __init__(self, relative_url, path):
        super(ImportedHtml, self).__init__(relative_url, path, None)
        self.head_tags = []
        self.body_tags = []

    def parse(self):
        self.el = html.parse(self.path)

        seen_tags = set()

        # Consider scripts and links in the order they appear in the document.
        for el in self.el.findall('//*'):
            if el.tag not in ('script', 'link', 'style'):
                continue
            if el.xpath('ancestor::polymer-element'):
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

    def __init__(self, script_el, text=None, relative_url=None):
        super(ImportedScript, self).__init__(relative_url, None, script_el)
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
        if self.relative_url:
            return 'ImportedScript(relative_url=%r)' % self.relative_url
        elif self.text:
            return 'ImportedScript(%r)' % self.text
        else:
            assert False, 'Bad ImportedScript'


class ImportedLink(ImportedTag):

    def __init__(self, relative_url, link_el, path=None):
        super(ImportedLink, self).__init__(
            relative_url, path=path, el=link_el)
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

        with open(self.path) as handle:
            self.replacement.text = handle.read()

        # TODO: Rewrite url() in the included file in case the path of the
        # link is different than the path of what included it.

        # TODO: transitively include @import references?


class ImportedStyle(ImportedTag):

    def __init__(self, style_el):
        super(ImportedStyle, self).__init__(
            relative_url=None, path=None, el=style_el)


class ImportedPolymerElement(ImportedTag):

    def __init__(self, polymer_el):
        super(ImportedPolymerElement, self).__init__(
            relative_url=None, path=None, el=polymer_el)

    def parse(self):
        # TODO: Handle no-script Polymer elements that don't explicitly
        # call Polymer() in a child script tag.

        for child_el in self.el.findall('.//*'):
            if child_el.tag not in ('script', 'link'):
                continue
            self.resource_tags.append(child_el)


class PathResolver(object):

    def __init__(self, index_relative_url, index_path):
        self.index_relative_url = index_relative_url
        self.index_path = index_path
        self.root_url = os.path.dirname(index_relative_url)
        self.root_dir = os.path.dirname(index_path)

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

        # Strip the common prefix of the URL serving. What's left relative to
        # the path directory is the path to the file on disk.
        relative_path = normalized_relative_url[len(self.root_url):]

        return (normalized_relative_url,
                os.path.join(self.root_dir, relative_path))


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
                raise InvalidScriptError(html.tostring(script_el))

        try:
            script_src = script_el.attrib['src']
        except KeyError:
            # The script is inline.
            return ImportedScript(script_el, text=script_el.text)
        else:
            # The script is an external resource so we shouldn't vulcanize.
            relative_url, _ = self.resolve(
                script_src, parent_relative_url=parent_relative_url)
            return ImportedScript(script_el, relative_url=relative_url)

    def import_link(self, parent_relative_url, link_el):
        try:
            rel = link_el.attrib['rel']
            href = link_el.attrib['href']
        except KeyError:
            raise InvalidLinkError(html.tostring(link_el))

        relative_url, path = self.resolve(
            href, parent_relative_url=parent_relative_url)

        return ImportedLink(relative_url, link_el, path=path)

    def import_polymer_element(self, parent_relative_url, polymer_el):
        return ImportedPolymerElement(polymer_el)

    def import_style(self, parent_relative_url, style_el):
        return ImportedStyle(style_el)
