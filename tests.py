#SimpleCache Tests
#~~~~~~~~~~~~~~~~~~~
from simplecache import SimpleCache, cache_it, cache_it_json, connection, CacheMissException, ExpiredKeyException
from unittest import TestCase, main


class ComplexNumber(object):  # used in pickle test
    def __init__(self, real, imag):
        self.real = real
        self.imag = imag

    def __eq__(self, other):
        return self.real == other.real and self.imag == other.imag


class SimpleCacheTest(TestCase):

    def setUp(self):
        self.c = SimpleCache(10)  # Cache that has a maximum limit of 10 keys

    def test_expire(self):
        import time

        quick_c = SimpleCache()
        quick_c.store("foo", "bar", expire=0.001)
        time.sleep(0.01)
        self.assertRaises(ExpiredKeyException, quick_c.get, "foo")
        quick_c.flush()

    def test_miss(self):
        self.assertRaises(CacheMissException, self.c.get, "blablabla")

    def test_store_retrieve(self):
        self.c.store("foo", "bar")
        foo = self.c.get("foo")
        self.assertEqual(foo, "bar")

    def test_json(self):
        payload = {"example": "data"}
        self.c.store_json("json", payload)
        self.assertEqual(self.c.get_json("json"), payload)

    def test_pickle(self):
        payload = ComplexNumber(3,4)
        self.c.store_pickle("pickle", payload)
        self.assertEqual(self.c.get_pickle("pickle"), payload)

    def test_decorator(self):
        @cache_it
        def excess_3(n):
            return n + 3
        self.assertEqual(excess_3(3), excess_3(3))

    def test_decorator_json(self):
        @cache_it_json
        def excess_4(n):
            return {str(n): n + 4}
        self.assertEqual(excess_4(0), excess_4(0))

    def test_decorator_complex_type(self):
        import math

        @cache_it
        def my_abs(c):
            return math.sqrt(c.real * c.real + c.imag * c.imag)
        self.assertEqual(my_abs(ComplexNumber(3,4)), abs(complex(3,4)))
        self.assertEqual(my_abs(ComplexNumber(3,4)), abs(complex(3,4)))

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
