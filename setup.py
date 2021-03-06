#!/usr/bin/env python2.7

from setuptools import setup

setup(
    name = 'vulcanize',
    packages = ['vulcanize'],
    version = '0.2',
    description = 'Vulcanizes HTML files that use Polymer',
    author = 'Brett Slatkin',
    author_email = 'brett@haxor.com',
    url = 'https://github.com/bslatkin/pyvulcanize',
    keywords = ['polymer'],
    install_requires=['lxml', 'html5lib'],
    entry_points={
        'console_scripts': [
            'vulcanize=vulcanize.__main__:main',
        ]
    },
    classifiers = [
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup :: HTML',
    ],
    long_description = """\
Python implementation of the vulcanize tool that is part of the Polymer project.

See the original at: https://github.com/Polymer/vulcanize

See the Polymer project at: https://www.polymer-project.org/
"""
)
