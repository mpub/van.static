import os
import shutil
import tempfile
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
        self.assertEqual(list(i), [
            ('tests/example', here + '/example', 'van.static', dist, 'dir'),
            ('tests/example/css', here + '/example/css', 'van.static', dist, 'dir'),
            ('tests/example/css/example.css', here + '/example/css/example.css', 'van.static', dist, 'file'),
            ('tests/example/example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ('tests/example/js', here + '/example/js', 'van.static', dist, 'dir'),
            ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file'),
            (stamp_file1, stamp_path1, 'van.static', dist, 'file'),
            # the duplicate of js is from the declaration of 'van.static:tests/example/js'
            ('tests/example/js', here + '/example/js', 'van.static', dist, 'dir'),
            ('tests/example/js/example.js', here + '/example/js/example.js', 'van.static', dist, 'file'),
            (stamp_file2, stamp_path2, 'van.static', dist, 'file'),
            ])


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
        one.put(to_put)
        # change the file we wrote
        os.remove(ex)
        exf = open(ex, 'w')
        exf.write('changed')
        exf.close()
        # put again, our file should again be written
        one.put(to_put)
        exf = open(ex, 'r')
        self.assertEqual(exf.read(), 'Example Text\n')
        exf.close()

    def test_put(self):
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        one = self.make_one()
        one.put([
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

    def test_exists(self):
        here = os.path.dirname(__file__)
        from pkg_resources import get_distribution
        dist = get_distribution('van.static')
        one = self.make_one()
        self.assertFalse(one.exists(dist, 'example.txt'))
        one.put([
            ('example.txt', here + '/example/example.txt', 'van.static', dist, 'file'),
            ])
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
        one.put(to_put)
        self.assertTrue(one._hard_link)
        self.assertEqual(link.call_count, 2)
        self.assertEqual(copy.call_count, 0)
        # if link now fails, we fall back to copy
        link.reset_mock()
        link.side_effect = Exception('boom')
        one.put(to_put)
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
        self.assertEqual(os.listdir(d), ['tests', 'van.static-%s-ORSXG5DTF5SXQYLNOBWGK===.stamp' % dist.version])
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
