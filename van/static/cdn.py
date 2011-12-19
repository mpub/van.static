import os
import shutil
import logging
import optparse
import tempfile
import urlparse

from pkg_resources import get_distribution, resource_listdir, resource_isdir, resource_filename

def export_cmd(resources=None, target=None, yui_compressor=False):
    """Export from the command line"""
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    res_help = "Resource to dump (may be repeated)."
    if resources is not None:
        res_help += '\nDefaults are: %s' % ', '.join(resources)
    parser.add_option("--resource",
                      dest="resources",
                      action='append',
                      help=res_help)
    parser.add_option("--yui-compressor", dest="yui_compressor", action="store_true",
                      help="Compress the files with the yui-compressor (must be on the path)")
    parser.add_option("--no-yui-compressor", dest="yui_compressor", action="store_false",
                      help="Do not compress the files with yui-compressor")
    parser.add_option("--target", dest="target",
                      help="Where to put the resources (can be the name of a local directory, or a url on S3 (eg: s3://bucket_name/path) you will need s3cmd available to push the files")
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
    options, args = parser.parse_args()
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
    assert len(args) == 0
    export(options.resources, options.target, options.yui_compressor, **kw)

def export(resources, target, yui_compressor=True, **kw):
    """Export the resources"""
    r_files = _walk_resources(resources)
    comp = None
    schema = target.split(':')[0]
    putter = {
            'file': _PutLocal,
            's3': _PutS3}[schema]
    putter = putter(target, **kw)
    try:
        if yui_compressor:
            comp = _YUICompressor()
            r_files = comp.compress(r_files)
        putter.put(r_files)
    finally:
        if comp is not None:
            comp.dispose()

def _walk_resource_directory(pname, resource_directory):
    """Walk a resource directory and yield all files.

    Files are yielded as the path to the resource.
    """
    yield resource_directory, 'dir'
    for member in resource_listdir(pname, resource_directory):
        r_path = '/'.join([resource_directory, member])
        if resource_isdir(pname, r_path):
            logging.info("_walk_resource_directory: Recursing into directory %s:%s", pname, r_path)
            for r in _walk_resource_directory(pname, r_path):
                yield r
        else:
            logging.info("_walk_resource_directory: Found resource %s:%s", pname, r_path)
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

    def __init__(self, target):
        assert target.startswith('file:///')
        self._target_dir = target = target[7:]
        logging.info("Putting resources in %s", self._target_dir)

    def put(self, files):
        proj_dirs = set([])
        for rpath, fs_rpath, pname, dist, type in files:
            fs_path = rpath.replace('/', os.sep) # enough for windows?
            target = os.path.join(self._target_dir, dist.project_name, dist.version, fs_path)
            if pname not in proj_dirs:
                os.mkdir(os.path.join(self._target_dir, dist.project_name))
                os.mkdir(os.path.join(self._target_dir, dist.project_name, dist.version))
                proj_dirs.add(pname)
            if type == 'file':
                self._copy(fs_rpath, target)
            else:
                os.makedirs(target)

    def _copy(self, source, target):
        logging.debug("Hard linking %s to %s", source, target)
        os.link(source, target) # hard links are fast!

class _PutS3:

    def __init__(self, target, aws_access_key=None, aws_secret_key=None):
        # lazy import to not have a hard dependency on boto
        from boto.s3.connection import S3Connection
        from boto.s3.key import Key
        target = urlparse.urlparse(target)
        assert target.scheme == 's3'
        self._Key = Key
        conn = S3Connection(aws_access_key, aws_secret_key)
        self._bucket = conn.get_bucket(target.netloc)
        self._target_path = target.path

    def put(self, files):
        for rpath, fs_rpath, pname, dist, type in files:
            if type == 'dir':
                continue
            logging.debug("putting to S3: %s", (rpath, fs_rpath, pname, dist, type))
            target = '/'.join([self._target_path, dist.project_name, dist.version, rpath])
            key = self._Key(self._bucket)
            key.key = target
            key.set_contents_from_filename(
                    fs_rpath,
                    reduced_redundancy=True,
                    headers={'Cache-Control': 'max-age=32140800'},
                    policy='public-read',
                    )

class _YUICompressor:

    def __init__(self):
        self._tmpdir = tempfile.mkdtemp()
        self._counter = 0

    def dispose(self):
        if self._tmpdir is not None:
            logging.debug("_YITCompressior: removing temp workspace: %s", self._tmpdir)
            shutil.rmtree(self._tmpdir)
            self._tmpdir = None

    def __del__(self):
        self.dispose()

    def compress(files):
        for rpath, fs_rpath, pname, dist, in files:
            if rpath.endswith('.js'):
                type = 'js'
            elif rpath.endswith('.css'):
                type = 'css'
            else:
                yield rpath, fs_rpath, pname, dist
            self._counter += 1
            target = os.path.join(tmpdir, str(self._counter) + '-' + os.path.basename(fs_rpath))
            args = ['yui-compressor', '--type', type, '-o', target, fs_rpath]
            logging.debug('Compressing with YUI Compressor %s file, from %s to %s', type, in_filename, target)
            subprocess.check_call(args)
            yield rpath, target, pname, dist

if __name__ == "__main__":
    export_cmd()
