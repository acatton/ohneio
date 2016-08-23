#!/usr/bin/env python

import os
import sys

from distutils.core import setup


def read(fname):
    with open(os.path.abspath(os.path.join(os.path.dirname(__file__), fname)), 'r') as fp:
        return fp.read()


install_requires = []
if sys.version_info <= (3, 5):
    install_requires.append('typing')


setup(name="ohneio",
      version="0.9.0-dev",
      description="Utility to write network protocol parser without any I/O",
      long_description=read('README'),
      license='ISC',
      author="Antoine Catton",
      author_email="devel@antoine.catton.fr",
      url="https://github.com/acatton/ohneio",
      py_modules=['ohneio'],
      install_requires=install_requires,
      classifiers=[
          "Intended Audience :: Developers",
          "Intended Audience :: Telecommunications Industry",
          "License :: OSI Approved :: ISC License (ISCL)",
          "Operating System :: OS Independent",
          "Programming Language :: Python :: 3.4",
          "Programming Language :: Python :: 3.5",
      ],
      )
