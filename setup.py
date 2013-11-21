import os
from setuptools import setup, find_packages

f = open('README.rst', 'r')
long_description = f.read()
f.close()

setup(name="van.static",
      version='1.3',
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
          'pyramid',
          ],
      classifiers=[
          'Programming Language :: Python :: 2.5',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.2',
          'Programming Language :: Python :: 3.3',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Programming Language :: Python',
          'Topic :: Internet :: WWW/HTTP',
          'Development Status :: 5 - Production/Stable',
          'Framework :: Pyramid',
          ],
      include_package_data = True,
      )
