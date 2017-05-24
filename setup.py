# -*- coding: utf-8 -

import os
import sys

from setuptools import setup, find_packages

CLASSIFIERS = []

# read long description
with open(os.path.join(os.path.dirname(__file__), 'README.md')) as f:
    long_description = f.read()


setup(
    name='magnet2torrent',
    version="0.1.0",

    description='Magnet URL to Torrent File',
    long_description=long_description,
    author='Dejan Noveski',
    author_email='dr.mote@gmail.com',
    classifiers=CLASSIFIERS,
    zip_safe=False,
    packages=find_packages(),
    entry_points="""
    [console_scripts]
    magnet2torrent=magnet2torrent:run
    """
)
 
