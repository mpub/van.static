import os
import sys
import shutil
import logging
import optparse
import tempfile
import subprocess

from pkg_resources import (get_distribution, resource_listdir, resource_isdir,
                           resource_filename)


def extract_cmd(resources=None, target=None, yui_compressor=False,
                args=sys.argv):
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
                            "(eg: s3://bucket_name/path) you will need s3cmd "
                            "available to push the files"))
    parser.add_option("--aws-access-key", dest="aws_access_key",
                      help="AWS access key")
    parser.add_option("--aws-secret-key", dest="aws_secret_key",
                      help="AWS secret key")
    parser.add_option("--loglevel", dest="loglevel",
                      help="The logging level to use.",
                      default='WARN')
    parser.set_defaults(
            yui_compressor=yui_compressor,
            target=target)
    options, args = parser.parse_args(args)
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
    assert len(args) == 1, args
    extract(options.resources, options.target, options.yui_compressor, **kw)


def extract(resources, target, yui_compressor=True, **kw):
    """Export the resources"""
    r_files = _walk_resources(resources)
    putter = _get_putter(target, **kw)
    comp = None
    try:
        if yui_compressor:
            comp = _YUICompressor()
            r_files = comp.compress(r_files)
        putter.put(r_files)
    finally:
        if comp is not None:
            comp.dispose()


def _get_putter(target, **kw):
    schema = target.split(':')[0]
    putter = {
            'file': _PutLocal,
            's3': _PutS3}[schema]
    return putter(target, **kw)


def config_static(config, static_resources, static_cdn=None):
    """Configure a Pyramid application with a list of static resources.

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
            config.add_static_view(name=name, path=path)
    else:
        for name, path in static_resources:
            pname, filepath = path.split(':', 1)
            dist = get_distribution(pname)
            name = '/'.join([static_cdn, dist.project_name, dist.version,
                             filepath])
            config.add_static_view(name=name, path=path)


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


def _walk_resources(resources):
    for res in resources:
        pname, r_path = res.split(':', 1)
        dist = get_distribution(pname)
        logging.info("Walking %s:%s", pname, r_path)
        resources = _walk_resource_directory(pname, r_path)
        for r, type in resources:
            fs_r = resource_filename(pname, r)
            yield r, fs_r, pname, dist, type


class _PutLocal:

    _hard_link = True

    def __init__(self, target):
        assert target.startswith('file:///')
        self._target_dir = target = target[7:]
        logging.info("Putting resources in %s", self._target_dir)

    def _if_not_exist(self, func, *args, **kw):
        # call for file operations that may fail with
        #   OSError: [Errno 17] File exists
        try:
            func(*args, **kw)
        except OSError:
            e = sys.exc_info()[1]
            if e.errno != 17:
                raise

    def put(self, files):
        proj_dirs = set([])
        for rpath, fs_rpath, pname, dist, type in files:
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


class _PutS3:

    def __init__(self, target, aws_access_key=None, aws_secret_key=None):
        # parse URL by hand as urlparse in python2.5 doesn't
        assert target.startswith('s3://')
        target = target[5:]
        bucket, path = target.split('/', 1)
        self._bucket = bucket
        self._path = '/%s' % path
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key

    def _get_imports(self):
        # lazy import to not have a hard dependency on boto
        # Also so we can mock them in tests
        from boto.s3.connection import S3Connection
        from boto.s3.key import Key
        return S3Connection, Key

    def put(self, files):
        S3Connection, Key = self._get_imports()
        conn = S3Connection(self._aws_access_key, self._aws_secret_key)
        bucket = conn.get_bucket(self._bucket, validate=False)
        for rpath, fs_rpath, pname, dist, type in files:
            if type == 'dir':
                continue
            logging.debug("putting to S3: %s",
                          (rpath, fs_rpath, pname, dist, type))
            target = '/'.join([self._path, dist.project_name, dist.version,
                               rpath])
            key = Key(bucket)
            key.key = target
            key.set_contents_from_filename(
                    fs_rpath,
                    reduced_redundancy=True,
                    headers={'Cache-Control': 'max-age=32140800'},
                    policy='public-read')


class _YUICompressor:

    def __init__(self):
        self._tmpdir = tempfile.mkdtemp()
        self._counter = 0

    def dispose(self):
        if self._tmpdir is not None:
            logging.debug("_YITCompressior: removing temp workspace: %s",
                          self._tmpdir)
            shutil.rmtree(self._tmpdir)
            self._tmpdir = None

    def __del__(self):
        self.dispose()

    def compress(self, files):
        for rpath, fs_rpath, pname, dist, f_type in files:
            if f_type == 'file' and rpath.endswith('.js'):
                type = 'js'
            elif f_type == 'file' and rpath.endswith('.css'):
                type = 'css'
            else:
                yield rpath, fs_rpath, pname, dist, f_type
                continue
            self._counter += 1
            target = os.path.join(self._tmpdir, str(self._counter) + '-' +
                                                os.path.basename(fs_rpath))
            args = ['yui-compressor', '--type', type, '-o', target, fs_rpath]
            logging.debug('Compressing with YUI Compressor %s file, '
                          'from %s to %s', type, fs_rpath, target)
            subprocess.check_call(args)
            yield rpath, target, pname, dist, f_type

if __name__ == "__main__":
    extract_cmd()
