#SimpleCache Tests
#~~~~~~~~~~~~~~~~~~~
from simplecache import connection, SimpleCache, cache_it, cache_it_json
from simplejson import dumps
from unittest import TestCase, main


class SimpleCacheTest(TestCase):

    def setUp(self):
        self.c = SimpleCache(10)  # Cache that has a maximum limit of 10 keys

    def test_store_retrieve(self):
        self.c.store("foo", "bar")
        foo = self.c.get("foo")
        self.assertEqual(foo, "bar")

    def test_json(self):
        payload = {'example': "data"}
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
            print "Calculating value"
            return {str(n): n + 4}
        print excess_4(0)
        print excess_4(0)
        self.assertEqual(excess_4(0), excess_4(0))

    def test_cache_limit(self):
        for i in range(100):
            self.c.store("foo%d" % i, "foobar")
            self.failUnless(len(self.c) <= 10)
            self.failUnless(len(self.c.keys()) <= 10)

    def test_flush(self):
        connection.set("will_not_be_deleted", '42')
        self.c.store("will_be_deleted", '10')
        len_before = len(self.c)
        self.c.flush()
        len_after = len(self.c)
        self.assertEqual(len_before, 1)
        self.assertEqual(len_after, 0)
        self.assertEqual(connection.get("will_not_be_deleted"), '42')
        connection.delete("will_not_be_deleted", '42')

    def tearDown(self):
        self.c.flush()

main()
