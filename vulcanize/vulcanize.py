#!/usr/bin/env python2.7

from lxml.html import html5parser


class ImportedFile(object):

    def __init__(self, relative_url, file_path):
        self.relative_url = relative_url
        self.file_path = file_path
        self.tree = None
        self.head_resources = []
        self.polymer_elements = []

    def parse(self):
        self.tree = html5parser.parse(self.file_path)
        self.root = self.tree.getroot()
        import pdb; pdb.set_trace()
        self.root.make_links_absolute(base_url=self.relative_url)




# merge head from dependent files
#


x = ImportedFile('index.html', './example/index.html')
x.parse()
