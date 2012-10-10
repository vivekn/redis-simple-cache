"""
A simple redis-cache interface for storing python objects.
"""
from json import loads, dumps
import redis

connection = redis.Redis()

class CacheMissException(Exception):
    pass

class SimpleCache(object):

    def __init__(self, limit = 1000):
        self.limit = limit #No of json encoded strings to cache

    def store(self, key, value):
        """ Stores a value after checking for space constraints and freeing up space if required """
        key = to_unicode(key)
        value = to_unicode(value)
        if value is not None:
            while connection.scard('SimpleCache:keys') >= self.limit:
                del_key = connection.spop('SimpleCache:keys')
                connection.delete("SimpleCache::%s" % del_key)

            connection.set('SimpleCache::%s' % key, value)
            connection.sadd("SimpleCache:keys", key)

    def store_json(self, key, value):
        self.store(key, dumps(value))

    def get(self, key):
        key = to_unicode(key)
        if key in self:
            return connection.get("SimpleCache::%s" % key)
        raise CacheMissException

    def get_json(self, key):
        return loads(self.get(key))

    def __contains__(self, key):
        return connection.sismember("SimpleCache:keys", key)

    def __len__(self):
        return connection.scard("SimpleCache:keys")

    def keys(self):
        keys = connection.keys("SimpleCache::*")
        return keys

    def flush(self):
        keys = self.keys()
        pipe = connection.pipeline()
        for key in keys:
            key_suffix = key[len("SimpleCache::"):]
            pipe.srem('SimpleCache:keys', key_suffix)
            pipe.delete(key)
        pipe.execute()


def cache_it (function):
    """
    Apply this decorator to cache any function returning a value.
    """
    cache = SimpleCache()
    def func(*args):
        key = dumps(args)
        cache_key = '%s:%s' % (function.__name__, key)
        if cache_key in cache:
            return cache.get(cache_key)
        else:
            result = function(*args)
            cache.store(cache_key, result)
            return result
    return func


def cache_it_json (function):
    """
    A decorator similar to cache_it, but it serializes the return value to json, while storing
    in the database. Useful for types like list, tuple, dict, etc.
    """
    cache = SimpleCache()
    def func(*args):
        key = dumps(args)
        cache_key = '%s:%s' % (function.__name__, key)
        if cache_key in cache:
            return cache.get_json(cache_key)
        else:
            result = function(*args)
            cache.store_json(cache_key, result)
            return result
    return func

def to_unicode(obj, encoding='utf-8'):
     if isinstance(obj, basestring):
         if not isinstance(obj, unicode):
             obj = unicode(obj, encoding)
     return obj
