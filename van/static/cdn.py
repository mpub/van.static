import os
import sys
import gzip
import shutil
import base64
import logging
import optparse
import mimetypes
import subprocess
from tempfile import mkdtemp, mkstemp

try:
    from urllib.parse import urlparse
except ImportError:
    #python 2
    from urlparse import urlparse

from pyramid.static import resolve_asset_spec
from pkg_resources import (get_distribution, resource_listdir, resource_isdir,
                           resource_filename)

_PY3 = sys.version_info[0] == 3

def includeme(config):
    config.add_directive('add_cdn_view', add_cdn_view)


def add_cdn_view(config, name, path, encodings=()):
    """Add a view used to render static assets.

    This calls ``config.add_static_view`` underneath the hood.

    If name is not an absolute URL, ``add_static_view`` is called directly with
    ``name`` and ``path`` unchanged.

    If ``name`` is an absolute URL, the project name and version from ``path``
    are added to it before calling ``add_static_view``. This url scheme matches
    the paths to which the resources are extracted to by ``extract_cmd``.

    For example, if ``name`` is ``http://cdn.example.com/path``, ``path`` is
    ``mypackage`` and the current version of ``mypackage`` is ``1.2.3`` then
    ``add_static_view is called with this url:

        http://cdn.example.com/path/mypackage/1.2.3

    Note that `path` is the path to the resource within the package.
    """
    package, filename = resolve_asset_spec(path, config.package_name)
    if package is None:
        raise ValueError("Package relative paths are required")
    path = '%s:%s' % (package, filename)
    if urlparse(name).scheme:
        # Name is an absolute url to CDN
        while name.endswith('/'):
            name = name[:-1]
        dist = get_distribution(package)
        for enc in [None] + list(encodings):
            parts = [name, dist.project_name, dist.version]
            p = path
            if enc:
                parts.append(enc)
                pack, p = p.split(':', 1)
                p = ':'.join([pack, '/'.join([enc, p])])
            parts.append(filename)
            n = '/'.join(parts)
            config.add_static_view(name=n, path=p)
    else:
        if encodings:
            raise NotImplementedError('Refusing to guess what a static filesystem view with encodings mean (for now)')
        config.add_static_view(name=name, path=path)


def extract_cmd(resources=None, target=None, yui_compressor=False,
                ignore_stamps=False, encodings=None, args=sys.argv):
    """Export from the command line"""
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    res_help = "Resource to dump (may be repeated)."
    if resources is not None:
        res_help += '\nDefaults are: %s' % ', '.join(resources)
    parser.add_option("--resource",
                      dest="resources",
                      action='append',
                      help=res_help)
    parser.add_option("--yui-compressor", dest="yui_compressor",
                      action="store_true",
                      help=("Compress the files with the yui-compressor "
                            "(must be on the path)"))
    parser.add_option("--no-yui-compressor", dest="yui_compressor",
                      action="store_false",
                      help="Do not compress the files with yui-compressor")
    parser.add_option("--target", dest="target",
                      help=("Where to put the resources (can be the name of a "
                            "local directory, or a url on S3 "
                            "(eg: s3://bucket_name/path) you will need boto "
                            "available to push the files"))
    parser.add_option("--encoding", dest="encodings",
                      action="append",
                      help=("This option exists to support serving compressed "
                            "resources over HTTP. For each --encoding a "
                            "compressed copy of the file will be uploaded "
                            "to the target with the relevant 'Content-Encoding' "
                            "header. The local-filesystem does not support this. "
                            "The path of the encoded file upload is prefixed by "
                            "the encoding."))
    parser.add_option("--ignore-stamps", dest="ignore_stamps",
                      action="store_true",
                      help=("Stamp files are placed in the target to optimize "
                            "repeated uploads. If these files are found the "
                            "resource upload is skipped. Use this option to "
                            "ignore these files and always updload"))
    parser.add_option("--aws-access-key", dest="aws_access_key",
                      help="AWS access key")
    parser.add_option("--aws-secret-key", dest="aws_secret_key",
                      help="AWS secret key")
    parser.add_option("--loglevel", dest="loglevel",
                      help="The logging level to use.",
                      default='WARN')
    parser.set_defaults(
            yui_compressor=yui_compressor,
            target=target,
            ignore_stamps=ignore_stamps)
    options, args = parser.parse_args(args)
    if not options.encodings:
        # set our default
        options.encodings = encodings
    if not options.resources:
        # set our default
        options.resources = resources
    loglevel = getattr(logging, options.loglevel)
    logging.basicConfig(level=loglevel)
    if not options.target:
        raise AssertionError("Target is required")
    if not options.resources:
        raise AssertionError("Resources are required")
    kw = {}
    if options.aws_access_key:
        kw['aws_access_key'] = options.aws_access_key
    if options.aws_secret_key:
        kw['aws_secret_key'] = options.aws_secret_key
    if options.encodings:
        kw['encodings'] = options.encodings
    assert len(args) == 1, args
    extract(options.resources,
            options.target,
            options.yui_compressor,
            ignore_stamps=options.ignore_stamps,
            **kw)

def _never_has_stamp(dist, path):
    return False

def extract(resources, target, yui_compressor=True, ignore_stamps=False, **kw):
    """Export the resources"""
    putter = _get_putter(target, **kw)
    try:
        stamps = mkdtemp()
        try:
            has_stamp = _never_has_stamp
            if not ignore_stamps:
                has_stamp = putter.has_stamp
            r_files = _walk_resources(resources, has_stamp, stamps)
            comp = None
            try:
                if yui_compressor:
                    comp = _YUICompressor()
                    r_files = comp.compress(r_files)
                putter.put(r_files)
            finally:
                if comp is not None:
                    comp.dispose()
        finally:
            shutil.rmtree(stamps)
    finally:
        putter.close()


def _get_putter(target, **kw):
    schema = target.split(':')[0]
    putter = {
            'file': _PutLocal,
            's3': _PutS3}[schema]
    return putter(target, **kw)


def config_static(config, static_resources, static_cdn=None):
    """Configure a Pyramid application with a list of static resources.

    .. warning::
        This method is deprecated, please use the add_cdn_view directive
        instead. At same future point ``config_static`` will be removed.

    If static_cdn is None, the resource will be configured to use the local
    server. Ideal for development.

    If static_cdn is a URL, resources will be loaded from there under this
    schema:

        http://cdn.example.com/path/${package_name}/${package_version}/path

    Note that `path` is the path to the resource within the package.
    """
    if static_cdn is None:
        for name, path in static_resources:
            assert ':' in path, 'Is not relative to a package: %r' % path
            add_cdn_view(config, name=name, path=path)
    else:
        for name, path in static_resources:
            add_cdn_view(config, name=static_cdn, path=path)


def _walk_resource_directory(pname, resource_directory):
    """Walk a resource directory and yield all files.

    Files are yielded as the path to the resource.
    """
    yield resource_directory, 'dir'
    for member in resource_listdir(pname, resource_directory):
        if member.startswith('.'):
            continue
        r_path = '/'.join([resource_directory, member])
        if resource_isdir(pname, r_path):
            logging.info("_walk_resource_directory: Recursing into directory "
                         "%s:%s", pname, r_path)
            for r in _walk_resource_directory(pname, r_path):
                yield r
        else:
            logging.info("_walk_resource_directory: Found resource "
                         "%s:%s", pname, r_path)
            yield r_path, 'file'


def _walk_resources(resources, has_stamp, tmpdir):
    for res in resources:
        pname, r_path = res.split(':', 1)
        dist = get_distribution(pname)
        if has_stamp(dist, r_path):
            logging.info("Stamp found, skipping %s:%s", pname, r_path)
            continue
        logging.info("Walking %s:%s", pname, r_path)
        resources = _walk_resource_directory(pname, r_path)
        for r, type in resources:
            fs_r = resource_filename(pname, r)
            yield _to_dict(r, fs_r, pname, dist, type)
        handle, fs_r = mkstemp(dir=tmpdir)
        f = os.fdopen(handle, 'w')
        try:
            f.write('Stamping %s' % res)
        finally:
            f.close()
        yield _to_dict(r_path, fs_r, pname, dist, 'stamp')

def _stamp_resource(dist, resource_path, encodings=None):
    _stamp_dist = get_distribution('van.static')
    r_path = resource_path
    if _PY3:
        r_path32 = base64.b32encode(r_path.encode('utf-8')).decode('ascii')
    else:
        r_path32 = base64.b32encode(r_path)
    if not encodings:
        return _stamp_dist, '%s-%s-%s.stamp' % (dist.project_name, dist.version, r_path32)
    encodings = '-'.join(sorted(encodings))
    return _stamp_dist, '%s-%s-%s-%s.stamp' % (dist.project_name, dist.version, encodings, r_path32)

class _PutLocal:

    _hard_link = True

    def __init__(self, target):
        assert target.startswith('file:///')
        self._target_dir = target = target[7:]
        logging.info("Putting resources in %s", self._target_dir)

    def close(self):
        pass

    def _if_not_exist(self, func, *args, **kw):
        # call for file operations that may fail with
        #   OSError: [Errno 17] File exists
        try:
            func(*args, **kw)
        except OSError:
            e = sys.exc_info()[1]
            if e.errno != 17:
                raise

    def has_stamp(self, dist, resource_path):
        stamp_dist, stamp_path = _stamp_resource(dist, resource_path)
        return self.exists(stamp_dist, stamp_path)

    def exists(self, dist, path):
        target = os.path.join(self._target_dir, dist.project_name,
                              dist.version, path)
        return os.path.exists(target)

    def put(self, files):
        proj_dirs = set([])
        for f in files:
            rpath = f['resource_path']
            fs_rpath = f['filesystem_path']
            pname = f['distribution_name']
            dist = f['distribution']
            type = f['type']
            if type == 'stamp':
                dist, rpath = _stamp_resource(dist, rpath)
                type = 'file'
            fs_path = rpath.replace('/', os.sep)  # enough for windows?
            target = os.path.join(self._target_dir, dist.project_name,
                                  dist.version, fs_path)
            if pname not in proj_dirs:
                self._if_not_exist(os.makedirs, os.path.join(self._target_dir,
                                                             dist.project_name,
                                                             dist.version))
                proj_dirs.add(pname)
            if type == 'file':
                self._copy(fs_rpath, target)
            else:
                self._if_not_exist(os.makedirs, target)

    def _copy(self, source, target):
        if self._hard_link:
            try:
                logging.debug("Hard linking %s to %s", source, target)
                os.link(source, target) # hard links are fast!
            except:
                logging.debug("Hard linking failed, falling back to normal copy")
                e = sys.exc_info()[1]
                if isinstance(e, OSError) and e.errno == 17:
                    # file exists, let's try removing it
                    os.remove(target)
                else:
                    # another error, don't try hard linking after first failure
                    # this may be because the files are on differnt devices or windows
                    self._hard_link = False
                self._copy(source, target)
        else:
            logging.debug("Copying %s to %s", source, target)
            shutil.copy(source, target)

_GZ_MIMETYPES = frozenset([
        'text/plain',
        'text/html',
        'text/css',
        'application/javascript',
        'application/x-javascript',
        'text/xml',
        'application/json',
        'application/xml',
        'image/svg+xml'])

class _PutS3:

    _cached_bucket = None

    def __init__(self, target, aws_access_key=None, aws_secret_key=None, encodings=()):
        # parse URL by hand as urlparse in python2.5 doesn't
        assert target.startswith('s3://')
        target = target[5:]
        bucket, path = target.split('/', 1)
        self._encodings = encodings
        self._bucket_name = bucket
        self._path = '/%s' % path
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key
        self._tmpdir = mkdtemp()

    def _get_temp_file(self):
        handle, filename = mkstemp(dir=self._tmpdir)
        return os.fdopen(handle, 'wb'), filename

    @property
    def _bucket(self):
        if self._cached_bucket is None:
            S3Connection = self._get_conn_class()
            conn = S3Connection(self._aws_access_key, self._aws_secret_key)
            self._cached_bucket = conn.get_bucket(self._bucket_name, validate=False)
        return self._cached_bucket

    def has_stamp(self, dist, resource_path):
        stamp_dist, stamp_path = _stamp_resource(dist, resource_path, encodings=self._encodings)
        return self.exists(stamp_dist, stamp_path)

    def exists(self, dist, path):
        target = '/'.join([self._path, dist.project_name, dist.version,
                           path])
        return self._bucket.get_key(target) is not None

    def _get_conn_class(self):
        # lazy import to not have a hard dependency on boto
        # Also so we can mock them in tests
        from boto.s3.connection import S3Connection
        return S3Connection

    def _get_key_class(self):
        from boto.s3.key import Key
        return Key

    def _should_gzip(self, mimetype):
        return mimetype in _GZ_MIMETYPES

    def close(self):
        if self._tmpdir is not None:
            logging.debug("_S3Putter: removing temp workspace: %s",
                          self._tmpdir)
            shutil.rmtree(self._tmpdir)
            self._tmpdir = None

    def put(self, files):
        logging.info("S3: putting resources to bucket %s with encodings: %s", self._bucket_name, self._encodings)
        Key = self._get_key_class()
        bucket = self._bucket
        encodings = [None] + list(self._encodings)
        for f in files:
            if f['type'] == 'dir':
                continue
            elif f['type'] == 'stamp':
                dist, rpath = _stamp_resource(f['distribution'], f['resource_path'], encodings=self._encodings)
                target = '/'.join([self._path, dist.project_name, dist.version, rpath])
                logging.info("Stamping resource %s:%s in S3: %s", f['distribution_name'], f['resource_path'], target)
                key = Key(bucket)
                key.key = target
                key.set_contents_from_filename(
                        f['filesystem_path'],
                        reduced_redundancy=True,
                        policy='public-read')
                continue
            dist = f['distribution']
            prefix = '/'.join([self._path, dist.project_name, dist.version])
            filename = f['resource_path'].split('/')[-1]
            mimetype = mimetypes.guess_type(filename)[0]
            for enc in encodings:
                headers = {'Cache-Control': 'max-age=32140800'}
                if mimetype:
                    headers['Content-Type'] = mimetype
                if enc is None:
                    target = '/'.join([prefix, f['resource_path']])
                    fs_path = f['filesystem_path']
                elif enc == 'gzip':
                    target = '/'.join([prefix, enc, f['resource_path']])
                    if self._should_gzip(mimetype):
                        headers['Content-Encoding'] = 'gzip'
                        source = f['filesystem_path']
                        c_file, fs_path = self._get_temp_file()
                        try:
                            file = gzip.GzipFile(filename, 'wb', 9, c_file)
                            try:
                                source = open(source, 'rb')
                                try:
                                    file.write(source.read())
                                finally:
                                    source.close()
                            finally:
                                file.close()
                        finally:
                            c_file.close()
                    else:
                        fs_path = f['filesystem_path']
                else:
                    raise NotImplementedError()
                logging.info("putting to S3: %s with headers: %s", target, headers)
                key = Key(bucket)
                key.key = target
                key.set_contents_from_filename(
                        fs_path,
                        reduced_redundancy=True,
                        headers=headers,
                        policy='public-read')

def _to_dict(resource_path, filesystem_path, distribution_name, distribution, type):
    """Convert a tuple of values to a more plugin friendly dictionary.

    - `resource_path` is the path to file within resource (distribution)
    - `filesystem_path` is path to file on local filesystem
    - `distribution` is the pkg_resources distribution object
    - `distribution_name` is the pkg_resources distribution name
    - `type` is a string indicating the resource type, `file` for a filesystem file and `dir` for a directory
    """
    return locals()

class _YUICompressor:

    def __init__(self):
        self._tmpdir = mkdtemp()
        self._counter = 0

    def dispose(self):
        if self._tmpdir is not None:
            logging.debug("_YUICompressior: removing temp workspace: %s",
                          self._tmpdir)
            shutil.rmtree(self._tmpdir)
            self._tmpdir = None

    def __del__(self):
        self.dispose()

    def compress(self, files):
        for f in files:
            rpath = f['resource_path']
            f_type = f['type']
            if f_type == 'file' and rpath.endswith('.js'):
                type = 'js'
            elif f_type == 'file' and rpath.endswith('.css'):
                type = 'css'
            else:
                yield f
                continue
            self._counter += 1
            fs_rpath = f['filesystem_path']
            target = os.path.join(self._tmpdir, str(self._counter) + '-' +
                                                os.path.basename(fs_rpath))
            args = ['yui-compressor', '--type', type, '-o', target, fs_rpath]
            logging.debug('Compressing with YUI Compressor %s file, '
                          'from %s to %s', type, fs_rpath, target)
            subprocess.check_call(args)
            f['filesystem_path'] = target
            yield f

if __name__ == "__main__":
    extract_cmd()
