import os
import sys
import shutil
import tempfile
from unittest import TestCase

from mock import patch, Mock

_PY3 = sys.version_info[0] == 3
if _PY3:
    def b(s):
        return s.encode("latin-1")
else:
    def b(s):
        return s

def _iter_to_dict(i):
    from van.static.cdn import _to_dict
    for e in i:
        yield _to_dict(*e)

class TestExtractCmd(TestCase):

    @patch("van.static.cdn.logging")
    @patch("van.static.cdn.extract")
    def test_defaults(self, extract, logging):
        from van.static.cdn import extract_cmd
        extract_cmd(
                resources=['van.static.tests:static'],
                yui_compressor=True,
                target='file:///wherever',
                args=['extract_cmd'])
        extract.assert_called_once_with(
                ['van.static.tests:static'],
                'file:///wherever',
                True,
                ignore_stamps=False)
        extract.reset_mock()
        extract_cmd(
                resources=['van.static.tests:static'],
                yui_compressor=True,
                target='file:///wherever',
                args=[
                    'extract_cmd',
                    '--resource', 'van.static.tests:static',
                    '--target', 'file:///somewhere_else',
                    '--resource', 'van.static.tests:another_static',
                    '--no-yui-compressor',
                    '--ignore-stamps'
                    ])
        extract.assert_called_once_with(
                ['van.static.tests:static', 'van.static.tests:another_static'],
                'file:///somewhere_else',
                False,
                ignore_stamps=True)

    @patch("van.static.cdn.logging")
    @patch("van.static.cdn.extract")
    def test_args(self, extract, logging):
        from van.static.cdn import extract_cmd
        # all possible arguments
        extract_cmd(
                args=[
                    'export_cmd',
                    '--resource', 'van.static.tests:static',
                    '--target', 's3:///somewhere_else',
                    '--resource', 'van.static.tests:another_static',
                    '--yui-compressor',
                    '--encoding', 'gzip',
                    '--aws-access-key', '1234',
                    '--aws-secret-key', '12345',
                    '--loglevel', 'DEBUG',
                    ])
        extract.assert_called_once_with(
                ['van.static.tests:static', 'van.static.tests:another_static'],
                's3:///somewhere_else',
                True,
                encodings=['gzip'],
                aws_secret_key='12345',
                aws_access_key='1234',
                ignore_stamps=False)
        logging.basicConfig.assert_called_once_with(level=logging.DEBUG)
        logging.reset_mock()
        extract.reset_mock()
        # minimum arguments
        extract_cmd(
                args=[
                    'extract_cmd',
                    '--resource', 'van.static.tests:static',
                    '--target', 'file:///somewhere_else',
                    ])
        extract.assert_called_once_with(
                ['van.static.tests:static'],
                'file:///somewhere_else',
                False,
                ignore_stamps=False)
        logging.basicConfig.assert_called_once_with(level=logging.WARN)

    @patch("van.static.cdn.logging")
    def test_err(self, logging):
        from van.static.cdn import extract_cmd
        self.assertRaises(AssertionError, extract_cmd, args=['extract_cmd'])
        only_resource = ['extract_cmd', '--resource', 'van.static.tests:static']
        self.assertRaises(AssertionError, extract_cmd, args=only_resource)
        only_target = ['extract_cmd', '--target', 'file:///somewhere_else']
        self.assertRaises(AssertionError, extract_cmd, args=only_target)


class TestExtract(TestCase):

    @patch("van.static.cdn._get_putter")
    @patch("van.static.cdn._walk_resources")
    def test_putter_closed(self, walk_resources, putter):
        from van.static.cdn import extract
        extract(['r1', 'r2'], 'file:///path/to/local', False, ignore_stamps=True)
        self.assertTrue(putter().close.called)

    @patch("van.static.cdn.mkdtemp")
    @patch("van.static.cdn._get_putter")
    @patch("van.static.cdn._YUICompressor")
    @patch("van.static.cdn._walk_resources")
    def test_no_comp(self, walk_resources, comp, putter, mkdtemp):
        mkdtemp.return_value = tmpdir = tempfile.mkdtemp()
        from van.static.cdn import extract, _never_exists
        extract(['r1', 'r2'], 'file:///path/to/local', False, ignore_stamps=True, another_kw=1)
        walk_resources.assert_called_once_with(['r1', 'r2'], _never_exists, tmpdir)
        putter.assert_called_once_with('file:///path/to/local', another_kw=1)
        putter().put.assert_called_once_with(walk_resources())
        self.assertFalse(comp.called)
        self.assertFalse(comp.compresss.called)
        self.assertFalse(comp.dispose.called)
        # the temporary directory was removed
        self.assertFalse(os.path.exists(tmpdir))

    @patch("van.static.cdn.mkdtemp")
    @patch("van.static.cdn._get_putter")
    @patch("van.static.cdn._YUICompressor")
    @patch("van.static.cdn._walk_resources")
    def test_comp(self, walk_resources, comp, putter, mkdtemp):
        mkdtemp.return_value = tmpdir = tempfile.mkdtemp()
        from van.static.cdn import extract, _never_exists
        extract(['r1', 'r2'], 'file:///path/to/local', True, ignore_stamps=True, another_kw=1)
        walk_resources.assert_called_once_with(['r1', 'r2'], _never_exists, tmpdir)
        # comp was called
        comp.assert_called_once_with()
        comp().compress.assert_called_once_with(walk_resources())
        comp().dispose.assert_called_once_with()
        # and putter with the result of comp
        putter.assert_called_once_with('file:///path/to/local', another_kw=1)
        putter().put.assert_called_once_with(comp().compress())
        # the temporary directory was removed
        self.assertFalse(os.path.exists(tmpdir))

    @patch("van.static.cdn.mkdtemp")
    @patch("van.static.cdn._get_putter")
    @patch("van.static.cdn._YUICompressor")
    @patch("van.static.cdn._walk_resources")
    def test_stamps(self, walk_resources, comp, putter, mkdtemp):
        mkdtemp.return_value = tmpdir = tempfile.mkdtemp()
        from van.static.cdn import extract
        extract(['r1', 'r2'], 'file:///path/to/local', False, another_kw=1)
        walk_resources.assert_called_once_with(['r1', 'r2'], putter().exists, tmpdir)
        putter().put.assert_called_once_with(walk_resources())
        # the temporary directory was removed
        self.assertFalse(os.path.exists(tmpdir))


class TestGetPutter(TestCase):

    def test_get_putter(self):
        from van.static.cdn import _get_putter
        from van.static.cdn import _PutLocal
        from van.static.cdn import _PutS3
        p = _get_putter('file:///tmp/whatever')
        self.assertTrue(isinstance(p, _PutLocal))
        p.close()
        p = _get_putter('s3://bucket/whatever')
        self.assertTrue(isinstance(p, _PutS3))
        p.close()

class DummyStaticURLInfo:
    # copied from pyramid tests
    def __init__(self):
        self.added = []

    def add(self, config, name, spec, **kw):
        self.added.append((config, name, spec, kw))

class TestDirective(TestCase):

    def _one(self):
        from pyramid.config import Configurator
        from pyramid.interfaces import IStaticURLInfo
        info = DummyStaticURLInfo()
        config = Configurator(
                autocommit=True,
                settings=dict(info=info))
        config.registry.registerUtility(info, IStaticURLInfo)
        config.include('van.static.cdn')
        return config

    def test_no_cdn(self):
        config = self._one()
        config.add_cdn_view('name1', 'package1:path1')
        self.assertEqual(
                config.registry.settings['info'].added,
                [(config, 'name1', 'package1:path1', {})])

    def test_cdn(self):
        config = self._one()
        import pkg_resources
        version = pkg_resources.get_distribution('van.static').version
        config.add_cdn_view('http://cdn.example.com/path', 'van.static:static_files')
        self.assertEqual(
                config.registry.settings['info'].added,
                [(config, 'http://cdn.example.com/path/van.static/%s/static_files' % version, 'van.static:static_files', {})])

    def test_cdn_encodings(self):
        config = self._one()
        import pkg_resources
        version = pkg_resources.get_distribution('van.static').version
        config.add_cdn_view('http://cdn.example.com/path', 'van.static:static_files', encodings=['gzip'])
        self.assertEqual(
                config.registry.settings['info'].added,
                [(config, 'http://cdn.example.com/path/van.static/%s/static_files' % version, 'van.static:static_files', {}),
                 (config, 'http://cdn.example.com/path/van.static/%s/gzip/static_files' % version, 'van.static:gzip/static_files', {})])

    def test_functional(self):
        from pyramid.config import Configurator
        from pyramid.testing import DummyRequest
        import pkg_resources
        version = pkg_resources.get_distribution('van.static').version
        config = Configurator(autocommit=True)
        config.include('van.static.cdn')
        config.add_cdn_view('http://cdn.example.com/path', 'van.static:static_files')
        config.add_cdn_view('name1', 'package1:path1')
        req = DummyRequest()
        req.registry = config.registry
        # req.static_url actually generates the right urls
        self.assertEqual(req.static_url('package1:path1/path2'), 'http://example.com/name1/path2')
        self.assertEqual(req.static_url('van.static:static_files/file1.js'), 'http://cdn.example.com/path/van.static/%s/static_files/file1.js' % version)


class TestConfigStatic(TestCase):

    def test_no_cdn(self):
        from van.static.cdn import config_static
        config = Mock(['add_static_view', 'package_name'])
        config.package_name = None
        config_static(
                config,
                [('name1', 'package1:path1'),
                    ('name2', 'package2:path2')])
        self.assertEqual(config.add_static_view.call_args_list,
                [((), dict(path='package1:path1', name='name1')),
                    ((), dict(path='package2:path2', name='name2'))])

    def test_cdn(self):
        from van.static.cdn import config_static
        config = Mock(['add_static_view', 'package_name'])
        config.package_name = None
        cdn_url = "http://cdn.example.com/path/to/wherever"
        config_static(
                config,
                [('name1', 'van.static:path1'),
                    ('name2', 'mock:path2')],
                static_cdn=cdn_url)
        from pkg_resources import get_distribution
        url1 = '%s/van.static/%s/path1' % (cdn_url, get_distribution('van.static').version)
        url2 = '%s/mock/%s/path2' % (cdn_url, get_distribution('mock').version)
        self.assertEqual(config.add_static_view.call_args_list,
                [((), dict(path='van.static:path1', name=url1)),
                    ((), dict(path='mock:path2', name=url2))])


class TestWalkResources(TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_walk(self):
        from van.static.cdn import _walk_resources
        exists = Mock()
        exists.return_value = False
        i = _walk_resources([
            'van.static:tests/example',
            'van.static:tests/example/js'], exists, self.tmpdir)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        stamp_file1 = 'van.static-%s-ORSXG5DTF5SXQYLNOBWGK===.stamp' % dist.version
        stamp_path1 = os.path.join(self.tmpdir, stamp_file1)
        stamp_file2 = 'van.static-%s-ORSXG5DTF5SXQYLNOBWGKL3KOM======.stamp' % dist.version
        stamp_path2 = os.path.join(self.tmpdir, stamp_file2)
        self.assertEqual(list(i), list(_iter_to_dict([
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ('tests/example/images', here + '/example/images', 'van.static', dist, 'dir'),
            ('tests/example/images/example.jpg', here + '/example/images/example.jpg', 'van.static', dist, 'file'),
            ('tests/example/js', here + '/example/js', 'van.static', dist, 'dir'),
            ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file'),
            (stamp_file1, stamp_path1, 'van.static', dist, 'file'),
            # the duplicate of js is from the declaration of 'van.static:tests/example/js'
            ('tests/example/js', here + '/example/js', 'van.static', dist, 'dir'),
            ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file'),
            (stamp_file2, stamp_path2, 'van.static', dist, 'file'),
            ])))


class TestPutLocalMixin:

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir)

    def make_one(self):
        target_url = 'file://%s' % self._tmpdir
        from van.static.cdn import _PutLocal
        return _PutLocal(target_url)

    def test_put_twice(self):
        # we can put to local twice without issue
        # https://github.com/jinty/van.static/issues/1
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        one = self.make_one()
        to_put = [
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ]
        ex = os.path.join(self._tmpdir, 'van.static', dist.version, 'tests', 'example', 'example.txt')
        one.put(_iter_to_dict(to_put))
        # change the file we wrote
        os.remove(ex)
        exf = open(ex, 'w')
        exf.write('changed')
        exf.close()
        # put again, our file should again be written
        one.put(_iter_to_dict(to_put))
        exf = open(ex, 'r')
        self.assertEqual(exf.read(), 'Example Text\n')
        exf.close()

    def test_put(self):
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        one = self.make_one()
        one.put(_iter_to_dict([
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ]))
        d = self._tmpdir
        self.assertEqual(os.listdir(d), ['van.static'])
        d = os.path.join(d, 'van.static')
        self.assertEqual(os.listdir(d), [dist.version])
        d = os.path.join(d, dist.version)
        self.assertEqual(os.listdir(d), ['tests'])
        d = os.path.join(d, 'tests')
        self.assertEqual(os.listdir(d), ['example'])
        d = os.path.join(d, 'example')
        self.assertEqual(os.listdir(d), ['css', 'example.txt'])
        f = open(os.path.join(d, 'example.txt'), 'r')
        self.assertEqual(
                f.read(),
                'Example Text\n')
        f.close()
        d = os.path.join(d, 'css')
        self.assertEqual(os.listdir(d), ['example.css'])

    def test_exists(self):
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        one = self.make_one()
        self.assertFalse(one.exists(dist, 'example.txt'))
        one.put(_iter_to_dict([
            ('example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ]))
        self.assertTrue(one.exists(dist, 'example.txt'))


class TestPutLocal(TestPutLocalMixin, TestCase):

    @patch('os.link')
    @patch('shutil.copy')
    def test_fallback_to_copy(self, copy, link):
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        one = self.make_one()
        to_put = [
            ('tests/example/css/example.css', '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', '/example/example.txt', 'van.static', dist, 'file'),
            ]
        # if link never fails it gets called twice
        self.assertTrue(one._hard_link)
        one.put(_iter_to_dict(to_put))
        self.assertTrue(one._hard_link)
        self.assertEqual(link.call_count, 2)
        self.assertEqual(copy.call_count, 0)
        # if link now fails, we fall back to copy
        link.reset_mock()
        link.side_effect = Exception('boom')
        one.put(_iter_to_dict(to_put))
        self.assertFalse(one._hard_link)
        self.assertEqual(link.call_count, 1)
        self.assertEqual(copy.call_count, 2)


class TestPutLocalNoHardlink(TestPutLocalMixin, TestCase):
    """Run all TestPutLocalMixin tests with hard linking disabled"""

    def make_one(self):
        one = TestPutLocalMixin.make_one(self)
        self.assertTrue(one._hard_link)
        one._hard_link = False
        return one


class TestPutS3(TestCase):

    @patch("van.static.cdn._PutS3._get_conn_class")
    def test_exists(self, conn_class):
        conn = Mock()
        conn_class.return_value = conn
        target_url = 's3://mybucket/path/to/dir'
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        from van.static.cdn import _PutS3
        putter = _PutS3(target_url, aws_access_key='key', aws_secret_key='secret')
        bucket = conn().get_bucket()
        bucket.get_key.return_value = None
        self.assertFalse(putter.exists(dist, 'whatever/wherever'))
        bucket.get_key.assert_called_once_with('/path/to/dir/%s/%s/whatever/wherever' % (dist.project_name, dist.version))
        bucket.get_key.return_value = 'not none'
        self.assertTrue(putter.exists(dist, 'whatever/wherever'))
        putter.close()

    @patch("van.static.cdn._PutS3._get_key_class")
    @patch("van.static.cdn._PutS3._get_conn_class")
    def test_put(self, conn_class, key_class):
        conn = Mock()
        key = Mock()
        css_key = Mock()
        txt_key = Mock()
        rv = [css_key, txt_key]
        def se(bucket):
            return rv.pop(0)
        key.side_effect = se
        conn_class.return_value = conn
        key_class.return_value = key
        target_url = 's3://mybucket/path/to/dir'
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        from van.static.cdn import _PutS3
        putter = _PutS3(target_url, aws_access_key='key', aws_secret_key='secret')
        putter.put(_iter_to_dict([
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ]))
        conn.assert_called_once_with('key', 'secret')
        conn().get_bucket.assert_called_once_with('mybucket', validate=False)
        bucket = conn().get_bucket()
        self.assertEqual(key.call_args_list, [
            ((bucket, ), ),
            ((bucket, ), ),
            ])
        self.assertEqual(
                css_key.key,
                '/path/to/dir/van.static/%s/tests/example/css/example.css' % dist.version)
        css_key.set_contents_from_filename.assert_called_once_with(
                here + '/example/css/example.css',
                reduced_redundancy=True,
                headers={'Cache-Control': 'max-age=32140800'},
                policy='public-read')
        self.assertEqual(
                txt_key.key,
                '/path/to/dir/van.static/%s/tests/example/example.txt' % dist.version)
        txt_key.set_contents_from_filename.assert_called_once_with(
                here + '/example/example.txt',
                reduced_redundancy=True,
                headers={'Cache-Control': 'max-age=32140800'},
                policy='public-read')
        putter.close()

    @patch("van.static.cdn._PutS3._get_key_class")
    @patch("van.static.cdn._PutS3._get_conn_class")
    def test_put_encodings(self, conn_class, key_class):
        keys = []
        def record_keys(bucket):
            mock = Mock()
            keys.append(mock)
            return mock
        key_class().side_effect = record_keys
        target_url = 's3://mybucket/path/to/dir'
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        from van.static.cdn import _PutS3
        putter = _PutS3(target_url, aws_access_key='key', aws_secret_key='secret', encodings=['gzip'])
        putter.put(_iter_to_dict([
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/images/example.jpg', here + '/example/images/example.jpg', 'van.static', dist, 'file'),
            ]))
        css_key, css_gz_key, jpg_key, jpg_gz_key = keys
        self.assertEqual(
                css_key.key,
                '/path/to/dir/van.static/%s/tests/example/css/example.css' % dist.version)
        css_key.set_contents_from_filename.assert_called_once_with(
                here + '/example/css/example.css',
                reduced_redundancy=True,
                headers={'Cache-Control': 'max-age=32140800'},
                policy='public-read')
        self.assertEqual(
                css_gz_key.key,
                '/path/to/dir/van.static/%s/gzip/tests/example/css/example.css' % dist.version)
        args, kw = css_gz_key.set_contents_from_filename.call_args
        # the file uploaded was a gzipped version of the CSS
        self.assertNotEqual(here + '/example/css/example.css', args[0])
        import gzip
        f = open(args[0], 'rb')
        try:
            file_contents = f.read()
            f.seek(0)
            decoded_css = gzip.GzipFile('', 'r', fileobj=f).read()
        finally:
            f.close()
        self.assertTrue(file_contents.startswith(b('\x1f\x8b'))) # gzip magic number
        self.assertEqual(decoded_css.decode('ascii'), '.example {\n\twidth: 80px\n}\n')
        self.assertEqual(kw, dict(
                reduced_redundancy=True,
                headers={'Cache-Control': 'max-age=32140800',
                    'Content-Encoding': 'gzip'},
                policy='public-read'))
        self.assertEqual(
                jpg_key.key,
                '/path/to/dir/van.static/%s/tests/example/images/example.jpg' % dist.version)
        jpg_key.set_contents_from_filename.assert_called_once_with(
                here + '/example/images/example.jpg',
                reduced_redundancy=True,
                headers={'Cache-Control': 'max-age=32140800'},
                policy='public-read')
        # the jpeg was re-uploaded to the gzip prefixed url but NOT compressed
        self.assertEqual(
                jpg_gz_key.key,
                '/path/to/dir/van.static/%s/gzip/tests/example/images/example.jpg' % dist.version)
        jpg_gz_key.set_contents_from_filename.assert_called_once_with(
                here + '/example/images/example.jpg',
                reduced_redundancy=True,
                headers={'Cache-Control': 'max-age=32140800'},
                policy='public-read')
        putter.close()

class TestYUICompressor(TestCase):

    def setUp(self):
        from van.static.cdn import _YUICompressor
        self.one = _YUICompressor()

    def tearDown(self):
        self.one.dispose()

    @patch('van.static.cdn.subprocess')
    def test_uncompressible(self, subprocess):
        # directories and non js/css
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        input = list(_iter_to_dict(
            [('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
             ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file')]))
        self.assertEqual(list(self.one.compress(iter(input))), input)
        self.assertFalse(subprocess.check_call.called)

    @patch('van.static.cdn.subprocess')
    def test_compress(self, subprocess):
        # js/css files are compressed to a temporary directory
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        input = list(_iter_to_dict([('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
                 ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file')]))
        out = list(_iter_to_dict([('tests/example/css/example.css', self.one._tmpdir + '/1-example.css', 'van.static', dist, 'file'),
               ('tests/example/js/example.js', self.one._tmpdir + '/2-example.js', 'van.static', dist, 'file')]))
        self.assertEqual(list(self.one.compress(iter(input))), out)
        self.assertEqual(subprocess.check_call.call_args_list, [
            ((['yui-compressor', '--type', 'css', '-o', self.one._tmpdir + '/1-example.css', here + '/example/css/example.css'], ), ),
            ((['yui-compressor', '--type', 'js', '-o', self.one._tmpdir + '/2-example.js', here + '/example/js/example.js'], ), )])

class TestFunctional(TestCase):

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir)

    def test_local_copy(self):
        here = os.path.dirname(__file__)
        target_url = 'file://%s' % self._tmpdir
        from van.static.cdn import extract_cmd
        extract_cmd(
                target=target_url,
                resources=['van.static:tests/example'],
                args=['export_cmd'])
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        d = self._tmpdir
        self.assertEqual(os.listdir(d), ['van.static'])
        d = os.path.join(d, 'van.static')
        self.assertEqual(os.listdir(d), [dist.version])
        d = os.path.join(d, dist.version)
        self.assertEqual(os.listdir(d), ['tests', 'van.static-%s-ORSXG5DTF5SXQYLNOBWGK===.stamp' % dist.version])
        d = os.path.join(d, 'tests')
        self.assertEqual(os.listdir(d), ['example'])
        d = os.path.join(d, 'example')
        self.assertEqual(sorted(os.listdir(d)), ['css', 'example.txt', 'images', 'js'])
        f = open(os.path.join(d, 'example.txt'), 'r')
        self.assertEqual(
                f.read(),
                'Example Text\n')
        f.close()
        d = os.path.join(d, 'css')
        self.assertEqual(os.listdir(d), ['example.css'])
