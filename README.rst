Tools for managing Pyramid static files on a CDN
================================================

Serving static files from a CDN
-------------------------------

Rationale
+++++++++

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

One way would be to have code like this:

    >>> from van.static import cdn

    >>> GLOBAL_LIST_OF_STATIC_RESOURCES = (
    ...     ('my_app_static_view_name': 'myapp:static'),
    ...     ('deform_static_view_name': 'deform:static'))

    >>> def my_extract_filesystem_command():
    ...     """Customized extract command for my application"""
    ...     cdn.extract_cmd([r[1] for r in GLOBAL_LIST_OF_STATIC_RESOURCES], yui_compressor=True)

    >>> def make_pyramid_app(static_cdn=None):
    ...     config = Configurator()
    ...     cdn.config_static(config, GLOBAL_LIST_OF_STATIC_RESOURCES, static_cdn=static_cdn)
    ...     return config.make_wsgi_app()

You would make ``my_extract_filesystem_command`` a command line script for the
system administrator to run on deployment. Likewise ``static_cdn`` is set by
the system administrator to the url where the files were exported to.

TODO:

 * Write tests, this was a spike that turned out to work.
 * Try get enough bits of this into Pyramid so the config_static function is
   unnecessary.

APT integration
+++++++++++++++

For system administrators who use APT to install packages, a useful trick is
put a snippet into ``/etc/apt/apt.conf.d/``::

    DPkg::Post-Invoke::      { "/path/to/extraction/script"; };

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
