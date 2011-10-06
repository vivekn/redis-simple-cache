#SimpleCache Tests
#~~~~~~~~~~~~~~~~~~~
from simplecache import SimpleCache, cache_it, cache_it_json
from simplejson import dumps
from unittest import TestCase

class SimpleCacheTest(TestCase):

    def setUp(self):
        self.c = SimpleCache(10) #Cache that has a maximum limit of 1000 keys

    def test_store_retrieve(self):
        self.c.store("foo", "bar")
        foo = self.c.get("foo")
        self.assertEqual(foo, "bar")


    def test_json(self):
        payload = { 'example': "data" }
        json_str = dumps(payload)
        self.c.store_json('json', payload)
        self.assertEqual(self.c.get('json'), json_str)

    def test_decorator(self):
        @cache_it
        def excess_3(n):
            return str(n + 3)
        self.assertEqual(excess_3(3), '6')

    def test_decorator_json(self):
        @cache_it_json
        def excess_4(n):
            return {str(n):n+4}
        print excess_4(31)

    def test_cache_limit(self):
        for i in range(100):
            self.c.store("foo%d" % i, "foobar")
            self.failUnless(len(self.c) <= 10)


