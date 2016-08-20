#!/usr/bin/env python

import os

from distutils.core import setup


def read(fname):
    with open(os.path.abspath(os.path.join(os.path.dirname(__file__), fname)), 'r') as fp:
        return fp.read()


setup(name="ohneio",
      version="0.8.1",
      description="Utility to write network protocol parser without any I/O",
      long_description=read('README'),
      license='ISC',
      author="Antoine Catton",
      author_email="devel@antoine.catton.fr",
      url="https://github.com/acatton/ohneio",
      py_modules=['ohneio'],
      classifiers=[
          "Intended Audience :: Developers",
          "Intended Audience :: Telecommunications Industry",
          "License :: OSI Approved :: ISC License (ISCL)",
          "Operating System :: OS Independent",
          "Programming Language :: Python :: 3.5",
      ],
      )
