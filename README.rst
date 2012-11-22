Tools for managing Pyramid static files on a CDN
================================================

Serving static files from a CDN
-------------------------------

A Content Delivery Network (CDN) allows you to serve static files to
users faster. For a web application the primary benefit is that your
pages render faster, giving a better user experience.

Additionally, content such as JavaScript or CSS files should be
"slimmed" before being placed on a CDN. By decreasing the file size you
further improve the user experience with even faster loading.

van.static gives you a tool to optionally deploy files to a CDN without
making the development process more onerous.

Workflow
++++++++

This tool aids in implementing a very specific workflow using static files and
pyramid:

 * During development static files are stored in subversion and are configured
   as normal in Pyramid applications.
 * Before deployment, the static files are extracted from the eggs by the
   system administrator and uploaded to a CDN. The URL on the CDN varies
   depending on the egg version the files where extracted from.
 * During extraction, CSS and JS files can be optionally minified.
 * In production, the system administrator configures the application to use
   static files from the CDN.

This workflow has these advantages:

 * Minimal impact on development. Changes to files are immediately visible,
   also developers work with un-compressed files.
 * CDN served files can have very long cache-control times while still allowing
   them to be updated almost immediately on application upgrade.

Testing an extraction
+++++++++++++++++++++

You can try out the extract tool by running the ``cdn.py`` file directly. The
following commands will extract the ``static`` resource from the ``deform``
package to the ``test_extract`` directory:

    $ mkdir test_extract
    $ python van/static/cdn.py --target "file://$(pwd)/test_extract" --resource deform:static

NOTE: the deform package must be on the python path.

If you use a url like this ``s3://mybucket/path/to/files/`` the extracted
resources will be placed directly in Amazon S3. You need to manually install
``boto`` to be able to use this functionality.

Implementing in your application
++++++++++++++++++++++++++++++++

One way would be to have code like this in your package:

    >>> def my_extract_filesystem_command():
    ...     """Customized extract command for my application"""
    ...     cdn.extract_cmd(['myapp:static', 'deform:static'], yui_compressor=True)

    >>> from pyramid.config import Configurator
    >>> def make_pyramid_app(cdn_url=None):
    ...     config = Configurator()
    ...     config.include('van.static.cdn')
    ...     config.add_cdn_view(cdn_url or 'myapp_static', 'myapp:static')
    ...     config.add_cdn_view(cdn_url or 'deform_static', 'deform:static')
    ...     return config.make_wsgi_app()

You would make ``my_extract_filesystem_command`` a command line script
for the system administrator to run on deployment. Likewise the
``cdn_url`` configuration option is set by the system administrator to
the url where the files were exported to.

GZip Content-Encoding compression
+++++++++++++++++++++++++++++++++

Compressing resources during extraction is supported for the S3 target.
S3 and Cloudfront does not directly support on the fly compression at
this time so a workaround is used where multiple copies of resources are
uploaded. One without any encoding and the others with encodings.

The links to resources should then be generated to compressed or
non-compressed resources depending on the capabilities of the browser.

An example of how to modify the resource generation in a pyramid
application is::

    >>> class ZippingPyramidRequest(Request):
    ...
    ...     def static_url(self, path, **kw):
    ...         if 'gzip' in self.accept_encoding:
    ...             package, path = path.split(':', 1)
    ...             path = '{package}:gzip/{path}'.format(
    ...                     package=package,
    ...                     path=path)
    ...         return Request.static_url(self, path, **kw)

The extractor is configured to upload resources with the gzip encoding
with the --encoding parameter.

WARNING: The `Vary` HTTP will need to contain `Accept-Encoding` to play
well with any caches.

APT integration
+++++++++++++++

For system administrators who use APT to install packages, a useful trick is
put a snippet into ``/etc/apt/apt.conf.d/``::

    DPkg::Post-Invoke::      "/path/to/extraction/script";

So that the extraction script runs whenever packages are installed on the
application servers. Note that if you have ``etckeeper`` installed, this should
be placed afterwards.

JSLint testing support
----------------------

NOTE: To use this functionality you must have a ``jslint`` command on your PATH.

This allows you to run ``jslint`` on all the files in a directory from a
unittest. For example:

    >>> import unittest

    >>> class TestJSLint(unittest.TestCase):
    ...
    ...     def test_static(self):
    ...         from van.static.testing import assert_jslint_dir
    ...         from pkg_resources import resource_filename, cleanup_resources
    ...         assert_jslint_dir(resource_filename('vanguardistas.publicview', 'static/js'))
    ...         cleanup_resources()

YUI3 loader configuration helper
--------------------------------

``van.static.yui`` holds utilities to simplify setting up a YUI3 loader
configuration from a directory of JS modules.

Contributing
------------

If you're interested, the primary development repository over at github
https://github.com/jinty/van.static


..
    Test... Make sure we can actually create the app:

    >>> app = make_pyramid_app()
