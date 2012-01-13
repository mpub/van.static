##############################################################################
#
# Copyright (c) 2008 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

import os
from setuptools import setup, find_packages

f = open('README.rst', 'r')
long_description = f.read()
f.close()

setup(name="van.static",
      version='0.6',
      license='BSD-derived',
      long_description=long_description,
      url='http://pypi.python.org/pypi/van.static',
      author_email='brian@vanguardistas.net',
      packages=find_packages(),
      author="Vanguardistas LLC",
      description="Tools for managing Pyramid static files on a CDN",
      test_suite="van.static.tests",
      namespace_packages=["van"],
      tests_require = ['mock'],
      install_requires = [
          'setuptools',
          ],
      classifiers=[
          'Programming Language :: Python :: 2.5',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.2',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Programming Language :: Python',
          'Topic :: Internet :: WWW/HTTP',
          'Development Status :: 4 - Beta',
          'Framework :: Pylons', # actually pyramid, but that's part of pylons
          ],
      include_package_data = True,
      )
