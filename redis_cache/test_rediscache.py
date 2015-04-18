#SimpleCache Tests
#~~~~~~~~~~~~~~~~~~~
from datetime import timedelta
from rediscache import SimpleCache, RedisConnect, cache_it, cache_it_json, CacheMissException, ExpiredKeyException, DoNotCache
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
        self.redis = RedisConnect().connect()
    def test_expire(self):
        quick_c = SimpleCache()

        quick_c.store("foo", "bar", expire=1)
        time.sleep(1.1)
        self.assertRaises(ExpiredKeyException, quick_c.get, "foo")
        quick_c.flush()

        quick_c.store("foo", "bar", expire=timedelta(seconds=1))
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
        self.redis.flushall()
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

    def test_decorator_do_not_cache(self):
        @cache_it(cache=self.c)
        def test_no_cache(n):
            result = n * 10
            raise DoNotCache(result)

        keys_before = len(self.c.keys())
        r1 = test_no_cache(20)
        r2 = test_no_cache(10)
        r3 = test_no_cache(30)
        r4 = test_no_cache(20)

        self.assertEqual(r1, (10 * 20))
        self.assertEqual(r2, (10 * 10))
        self.assertEqual(r3, (10 * 30))
        self.assertEqual(r4, (10 * 20))

        keys_after = len(self.c.keys())

        self.assertEqual(keys_before, keys_after)

    def test_decorator_do_not_cache_reraised(self):
        @cache_it(cache=self.c)
        def test_no_cache(n):
            result = n * 10
            try:
                raise DoNotCache(result)
            except DoNotCache as e:
                raise e
            except Exception:
                pass

        keys_before = len(self.c.keys())
        r1 = test_no_cache(20)
        r2 = test_no_cache(10)
        r3 = test_no_cache(30)
        r4 = test_no_cache(20)

        self.assertEqual(r1, (10 * 20))
        self.assertEqual(r4, (10 * 20))
        self.assertEqual(r2, (10 * 10))
        self.assertEqual(r3, (10 * 30))

        keys_after = len(self.c.keys())

        self.assertEqual(keys_before, keys_after)

    def test_decorator_do_not_cache_wrapping_exception(self):
        @cache_it(cache=self.c)
        def test_no_cache(n):
            try:
                result = n / 0
            except ZeroDivisionError as e:
                raise DoNotCache(e)

        keys_before = len(self.c.keys())
        r1 = test_no_cache(20)
        self.assertTrue(isinstance(r1, ZeroDivisionError))
        keys_after = len(self.c.keys())
        self.assertEqual(keys_before, keys_after)

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
        len_keys_after = connection.get("will_not_be_deleted")
        self.assertTrue(len_before > 0)
        self.assertEqual(len_after, 0)
        self.assertTrue(len_keys_before > 0)
        self.assertEqual(len_keys_after, '42')
        self.assertEqual(connection.get("will_not_be_deleted"), '42')
        connection.delete("will_not_be_deleted")

    def test_flush_namespace(self):
    	self.redis.flushall()
        self.c.store("foo:one", "bir")
        self.c.store("foo:two", "bor")
        self.c.store("fii", "bur")
        len_keys_before = len(self.c.keys())
        self.c.flush_namespace('foo')
        len_keys_after = len(self.c.keys())
        self.assertEqual((len_keys_before - len_keys_after), 2)
        self.assertEqual(self.c.get('fii'), 'bur')
        self.assertRaises(CacheMissException, self.c.get, "foo:one")
        self.assertRaises(CacheMissException, self.c.get, "foo:two")
        self.c.flush()

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
        self.assertEqual(self.c.expire_all_in_set(), (3, 3))
        self.assertRaises(ExpiredKeyException, self.c.get, "foo")
        self.assertRaises(ExpiredKeyException, self.c.get, "fuu")
        self.assertRaises(ExpiredKeyException, self.c.get, "fii")
        self.assertTrue(self.c.isexpired("foo"))
        self.assertTrue(self.c.isexpired("fuu"))
        self.assertTrue(self.c.isexpired("fii"))

    def test_expire_namespace(self):
        self.c.store("foo:one", "bir")
        self.c.store("foo:two", "bor")
        self.c.store("fii", "bur")
        self.assertEqual(self.c.expire_namespace('foo'), (3, 2))
        self.assertRaises(ExpiredKeyException, self.c.get, "foo:one")
        self.assertRaises(ExpiredKeyException, self.c.get, "foo:two")
        self.assertTrue(self.c.isexpired("foo:one"))
        self.assertTrue(self.c.isexpired("foo:two"))
        self.assertTrue(self.c.isexpired("fii") > 0)
        self.c.flush()

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
        self.assertTrue("b2" not in d)
        self.assertEqual(d["b3"], "bbb")

    def test_mget_expiry(self):
        self.c.store("c1", "c")
        self.c.store("c2", "cc", expire=1)
        self.c.store("c3", "ccc")
        time.sleep(1.1)
        d = self.c.mget(["c1", "c2", "c3"])
        self.assertEqual(d["c1"], "c")
        self.assertTrue("c2" not in d)
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
        self.assertTrue("json_b2" not in d)
        self.assertEqual(d["json_b3"], payload_b3)

    def test_invalidate_key(self):
        self.c.store("d1", "d")
        self.c.store("d2", "dd")
        self.c.store("d3", "ddd")
        self.c.invalidate("d2")
        d = self.c.mget(["d1", "d2", "d3"])
        self.assertEqual(d["d1"], "d")
        self.assertTrue("d2" not in d)
        self.assertEqual(d["d3"], "ddd")

    def tearDown(self):
        self.c.flush()

main()
