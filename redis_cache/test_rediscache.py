#SimpleCache Tests
#~~~~~~~~~~~~~~~~~~~
from rediscache import SimpleCache, cache_it, cache_it_json, CacheMissException, ExpiredKeyException
from unittest import TestCase, main
import time

class ComplexNumber(object):  # used in pickle test
    def __init__(self, real, imag):
        self.real = real
        self.imag = imag

    def __eq__(self, other):
        return self.real == other.real and self.imag == other.imag


class SimpleCacheTest(TestCase):

    def setUp(self):
        self.c = SimpleCache(10)  # Cache that has a maximum limit of 10 keys
        self.assertIsNotNone(self.c.connection)

    def test_expire(self):
        quick_c = SimpleCache()
        quick_c.store("foo", "bar", expire=1)
        time.sleep(1.1)
        self.assertRaises(ExpiredKeyException, quick_c.get, "foo")
        quick_c.flush()

    def test_miss(self):
        self.assertRaises(CacheMissException, self.c.get, "blablabla")

    def test_kwargs_decorator(self):
        @cache_it_json(cache=self.c)
        def add_it(a, b=10, c=5):
            return a + b + c
        add_it(3)
        self.assertEqual(add_it(3), 18)
        add_it(5, b=7)
        self.assertEqual(add_it(5, b=7), 17)
        add_it(6, c=3)
        self.assertEqual(add_it(6, c=3), 19)

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
        mutable = []
        @cache_it(cache=self.c)
        def append(n):
            mutable.append(n)
            return mutable
        append(1)
        len_before = len(mutable)
        mutable_cached = append(1)
        len_after = len(mutable)
        self.assertEqual(len_before, len_after)
        self.assertNotEqual(id(mutable), id(mutable_cached))
        self.assertEqual(mutable, mutable_cached)

    def test_decorator_json(self):
        import random

        mutable = {}
        @cache_it_json(cache=self.c)
        def set_key(n):
            mutable[str(random.random())] = n
            return mutable
        set_key('a')
        len_before = len(mutable)
        mutable_cached = set_key('a')
        len_after = len(mutable)
        self.assertEqual(len_before, len_after)
        self.assertNotEqual(id(mutable), id(mutable_cached))
        self.assertEqual(mutable, mutable_cached)

    def test_decorator_complex_type(self):
        import math

        @cache_it(cache=self.c)
        def add(x, y):
            return ComplexNumber(x.real + y.real, x.imag + y.imag)
        result = add(ComplexNumber(3,4), ComplexNumber(4,5))
        result_cached = add(ComplexNumber(3,4), ComplexNumber(4,5))
        self.assertNotEqual(id(result), id(result_cached))
        self.assertEqual(result, result_cached)
        self.assertEqual(result, complex(3,4) + complex(4,5))

    def test_cache_limit(self):
        for i in range(100):
            self.c.store("foo%d" % i, "foobar")
            self.failUnless(len(self.c) <= 10)
            self.failUnless(len(self.c.keys()) <= 10)

    def test_flush(self):
        connection = self.c.connection
        connection.set("will_not_be_deleted", '42')
        self.c.store("will_be_deleted", '10')
        len_before = len(self.c)
        len_keys_before = len(connection.keys(self.c.make_key("*")))
        self.c.flush()
        len_after = len(self.c)
        len_keys_after = len(connection.keys(self.c.make_key("*")))
        self.assertEqual(len_before, 1)
        self.assertEqual(len_after, 0)
        self.assertEqual(len_keys_before, 1)
        self.assertEqual(len_keys_after, 0)
        self.assertEqual(connection.get("will_not_be_deleted"), '42')
        connection.delete("will_not_be_deleted")

    def test_flush_multiple(self):
        c1 = SimpleCache(10, namespace=__name__)
        c2 = SimpleCache(10)
        c1.store("foo", "bar")
        c2.store("foo", "bar")
        c1.flush()
        self.assertEqual(len(c1), 0)
        self.assertEqual(len(c2), 1)
        c2.flush()

    def test_expire_all_in_set(self):
        self.c.store("foo", "bir")
        self.c.store("fuu", "bor")
        self.c.store("fii", "bur")
        self.assertEqual(self.c.expire_all_in_set(), (3,3))
        self.assertTrue(self.c.isexpired("foo"))
        self.assertTrue(self.c.isexpired("fuu"))
        self.assertTrue(self.c.isexpired("fii"))

    def test_mget(self):
        self.c.store("a1", "a")
        self.c.store("a2", "aa")
        self.c.store("a3", "aaa")
        d = self.c.mget(["a1", "a2", "a3"])
        self.assertEqual(d["a1"], "a")
        self.assertEqual(d["a2"], "aa")
        self.assertEqual(d["a3"], "aaa")

    def test_mget_nonexistant_key(self):
        self.c.store("b1", "b")
        self.c.store("b3", "bbb")
        d = self.c.mget(["b1", "b2", "b3"])
        self.assertEqual(d["b1"], "b")
        self.assertEqual(d["b2"], None)
        self.assertEqual(d["b3"], "bbb")

    def test_mget_expiry(self):
        self.c.store("c1", "c")
        self.c.store("c2", "cc", expire=1)
        self.c.store("c3", "ccc")
        time.sleep(1.1)
        d = self.c.mget(["c1", "c2", "c3"])
        self.assertEqual(d["c1"], "c")
        self.assertEqual(d["c2"], None)
        self.assertEqual(d["c3"], "ccc")

    def test_mget_json(self):
        payload_a1 = {"example_a1": "data_a1"}
        payload_a2 = {"example_a2": "data_a2"}
        self.c.store_json("json_a1", payload_a1)
        self.c.store_json("json_a2", payload_a2)
        d = self.c.mget_json(["json_a1", "json_a2"])
        self.assertEqual(d["json_a1"], payload_a1)
        self.assertEqual(d["json_a2"], payload_a2)
        
    def test_mget_json_nonexistant_key(self):
        payload_b1 = {"example_b1": "data_b1"}
        payload_b3 = {"example_b3": "data_b3"}
        self.c.store_json("json_b1", payload_b1)
        self.c.store_json("json_b3", payload_b3)
        d = self.c.mget_json(["json_b1", "json_b2", "json_b3"])
        self.assertEqual(d["json_b1"], payload_b1)
        self.assertEqual(d["json_b2"], None)
        self.assertEqual(d["json_b3"], payload_b3)

    def tearDown(self):
        self.c.flush()

main()
