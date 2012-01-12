import os
from unittest import TestCase

from mock import patch, Mock

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
                True)
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
                    '--no-yui-compressor'
                    ])
        extract.assert_called_once_with(
                ['van.static.tests:static', 'van.static.tests:another_static'],
                'file:///somewhere_else',
                False)

    @patch("van.static.cdn.logging")
    @patch("van.static.cdn.extract")
    def test_args(self, extract, logging):
        from van.static.cdn import extract_cmd
        # all possible arguments
        extract_cmd(
                args=[
                    'export_cmd',
                    '--resource', 'van.static.tests:static',
                    '--target', 'file:///somewhere_else',
                    '--resource', 'van.static.tests:another_static',
                    '--yui-compressor',
                    '--aws-access-key', '1234',
                    '--aws-secret-key', '12345',
                    '--loglevel', 'DEBUG',
                    ])
        extract.assert_called_once_with(
                ['van.static.tests:static', 'van.static.tests:another_static'],
                'file:///somewhere_else',
                True,
                aws_secret_key='12345',
                aws_access_key='1234')
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
                False)
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
    @patch("van.static.cdn._YUICompressor")
    @patch("van.static.cdn._walk_resources")
    def test_no_comp(self, walk_resources, comp, putter):
        from van.static.cdn import extract
        extract(['r1', 'r2'], 'file:///path/to/local', False, another_kw=1)
        walk_resources.assert_called_once_with(['r1', 'r2'])
        putter.assert_called_once_with('file:///path/to/local', another_kw=1)
        putter().put.assert_called_once_with(walk_resources())
        self.assertFalse(comp.called)
        self.assertFalse(comp.compresss.called)
        self.assertFalse(comp.dispose.called)

    @patch("van.static.cdn._get_putter")
    @patch("van.static.cdn._YUICompressor")
    @patch("van.static.cdn._walk_resources")
    def test_comp(self, walk_resources, comp, putter):
        from van.static.cdn import extract
        extract(['r1', 'r2'], 'file:///path/to/local', True, another_kw=1)
        walk_resources.assert_called_once_with(['r1', 'r2'])
        # comp was called
        comp.assert_called_once_with()
        comp().compress.assert_called_once_with(walk_resources())
        comp().dispose.assert_called_once_with()
        # and putter with the result of comp
        putter.assert_called_once_with('file:///path/to/local', another_kw=1)
        putter().put.assert_called_once_with(comp().compress())


class TestGetPutter(TestCase):

    def test_get_putter(self):
        from van.static.cdn import _get_putter
        from van.static.cdn import _PutLocal
        from van.static.cdn import _PutS3
        p = _get_putter('file:///tmp/whatever')
        self.assertTrue(isinstance(p, _PutLocal))
        p = _get_putter('s3://bucket/whatever')
        self.assertTrue(isinstance(p, _PutS3))


class TestConfigStatic(TestCase):

    def test_no_cdn(self):
        from van.static.cdn import config_static
        config = Mock(['add_static_view'])
        config_static(
                config,
                [('name1', 'package1:path1'),
                    ('name2', 'package2:path2')])
        self.assertEqual(config.add_static_view.call_args_list,
                [((), dict(path='package1:path1', name='name1')),
                    ((), dict(path='package2:path2', name='name2'))])

    def test_cdn(self):
        from van.static.cdn import config_static
        config = Mock(['add_static_view'])
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

    def test_walk(self):
        from van.static.cdn import _walk_resources
        i = _walk_resources([
            'van.static:tests/example',
            'van.static:tests/example/js'])
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        self.assertEqual(list(i), [
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ('tests/example/js', here + '/example/js', 'van.static', dist, 'dir'),
            ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file'),
            # the duplicate of js is from the declaration of 'van.static:tests/example/js'
            ('tests/example/js', here + '/example/js', 'van.static', dist, 'dir'),
            ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file'),
            ])


class TestPutLocal(TestCase):

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir)

    def test_put_twice(self):
        # we can put to local twice without issue
        # https://github.com/jinty/van.static/issues/1
        here = os.path.dirname(__file__)
        target_url = 'file://%s' % self._tmpdir
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        from van.static.cdn import _PutLocal
        putter = _PutLocal(target_url)
        to_put = [
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ]
        putter.put(to_put)
        putter.put(to_put)

    def test_put(self):
        here = os.path.dirname(__file__)
        target_url = 'file://%s' % self._tmpdir
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        from van.static.cdn import _PutLocal
        putter = _PutLocal(target_url)
        putter.put([
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ])
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


class TestPutS3(TestCase):

    @patch("van.static.cdn._PutS3._get_imports")
    def test_put(self, get_imports):
        conn = Mock()
        key = Mock()
        css_key = Mock()
        txt_key = Mock()
        rv = [css_key, txt_key]
        def se(bucket):
            return rv.pop(0)
        key.side_effect = se
        get_imports.return_value = conn, key
        target_url = 's3://mybucket/path/to/dir'
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        here = os.path.dirname(__file__)
        from van.static.cdn import _PutS3
        putter = _PutS3(target_url, aws_access_key='key', aws_secret_key='secret')
        putter.put([
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ])
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
        input =[('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
                ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file')]
        self.assertEqual(list(self.one.compress(iter(input))), input)
        self.assertFalse(subprocess.check_call.called)

    @patch('van.static.cdn.subprocess')
    def test_compress(self, subprocess):
        # js/css files are compressed to a temporary directory
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        input = [('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
                 ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file')]
        out = [('tests/example/css/example.css', self.one._tmpdir + '/1-example.css', 'van.static', dist, 'file'),
               ('tests/example/js/example.js', self.one._tmpdir + '/2-example.js', 'van.static', dist, 'file')]
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
        self.assertEqual(os.listdir(d), ['tests'])
        d = os.path.join(d, 'tests')
        self.assertEqual(os.listdir(d), ['example'])
        d = os.path.join(d, 'example')
        self.assertEqual(sorted(os.listdir(d)), ['css', 'example.txt', 'js'])
        f = open(os.path.join(d, 'example.txt'), 'r')
        self.assertEqual(
                f.read(),
                'Example Text\n')
        f.close()
        d = os.path.join(d, 'css')
        self.assertEqual(os.listdir(d), ['example.css'])
