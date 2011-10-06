"""
A simple redis-cache interface for storing python objects.
"""
from simplejson import loads, dumps
from django.utils.encoding import smart_unicode
import redis

connection = redis.Redis(host=None, port=None, password=None)

class CacheMissException(Exception):
    pass

class SimpleCache(object):

    def __init__(self, limit = 1000):
        self.limit = limit #No of json encoded strings to cache

    def store(self, key, value):
        """ Stores a value after checking for space constraints and freeing up space if required """
        if value is not None:
            while connection.scard('SimpleCache:keys') >= self.limit:
                deleted = connection.spop('SimpleCache:keys')
                connection.delete("SimpleCache::%s" % key)

            connection.set('SimpleCache::%s' % key, value)
            connection.sadd("SimpleCache:keys", key)

    def store_json(self, key, value):
        self.store(key, dumps(value))

    def get(self, key):
        if key in self:
            return connection.get("SimpleCache::%s" % key)
        raise CacheMissException

    def get_json(self, key):
        return loads(smart_unicode(self.get(key)))

    def __contains__(self, key):
        return connection.sismember("SimpleCache:keys", key)

    def __len__(self):
        return connection.scard("SimpleCache:keys")


def cache_it (function):
    """
    Apply this decorator to cache any function returning a value.
    """
    cache = SimpleCache()
    def func(key):
        if key in cache:
            return cache.get('%s:%s' % (function.__name__, key))
        else:
            result = function(key)
            cache.store('%s:%s' % (function.__name__, key), result)
            return result
    return func


def cache_it_json (function):
    """
    A decorator similar to cache_it, but it serializes the return value to json, while storing
    in the database. Useful for types like list, tuple, dict, etc.
    """
    cache = SimpleCache()
    def func(key):
        if key in cache:
            return cache.get_json('%s:%s' % (function.__name__, key))
        else:
            result = function(key)
            cache.store_json('%s:%s' % (function.__name__, key), result)
            return result
    return func
