from unittest import TestCase

class TestExtractRequires(TestCase):

    def test_it(self):
        from van.static.yui import _extract_requires
        self.assertEqual(
                _extract_requires("}, '1', { requires: ['yui-base', 'yui-later', 'json', 'io-base'] });"),
                ['yui-base', 'yui-later', 'json', 'io-base'])
