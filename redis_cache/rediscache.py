"""
A simple redis-cache interface for storing python objects.
"""
from functools import wraps
import pickle
import json
import base64
import redis

connection = redis.StrictRedis()


class CacheMissException(Exception):
    pass


class ExpiredKeyException(Exception):
    pass


class SimpleCache(object):

    def __init__(self, limit=1000, expire=60 * 60 * 24):
        self.limit = limit  # No of json encoded strings to cache
        self.expire = expire  # Time to keys to expire in seconds

    def make_key(self, key):
        return "SimpleCache-%s::%s" % (id(self), key)

    def get_set_name(self):
        return "SimpleCache-%s-keys" % id(self)
        
    def store(self, key, value, expire=None):
        """ Stores a value after checking for space constraints and freeing up space if required """
        key = to_unicode(key)
        value = to_unicode(value)
        set_name = self.get_set_name()
    
        while connection.scard(set_name) >= self.limit:
            del_key = connection.spop(set_name)
            connection.delete(self.make_key(del_key))

        pipe = connection.pipeline()
        if expire is None:
            expire = self.expire
        pipe.setex(self.make_key(key), expire, value)
        pipe.sadd(set_name, key)
        pipe.execute()

    def store_json(self, key, value):
        self.store(key, json.dumps(value))

    def store_pickle(self, key, value):
        self.store(key, base64.b64encode(pickle.dumps(value)))

    def get(self, key):
        key = to_unicode(key)
        if key in self:
            val = connection.get(self.make_key(key))
            if val is None:  # expired key
                connection.srem(self.get_set_name(), key)
                raise ExpiredKeyException
            else:
                return val
        raise CacheMissException

    def get_json(self, key):
        return json.loads(self.get(key))

    def get_pickle(self, key):
        return pickle.loads(base64.b64decode(self.get(key)))

    def __contains__(self, key):
        return connection.sismember(self.get_set_name(), key)

    def __len__(self):
        return connection.scard(self.get_set_name())

    def keys(self):
        return connection.smembers(self.get_set_name())

    def flush(self):
        keys = self.keys()
        pipe = connection.pipeline()
        for key in keys:
            pipe.delete(key)
        pipe.delete(self.get_set_name())
        pipe.execute()


def cache_it(limit=1000, expire=60 * 60 * 24):
    """
    Apply this decorator to cache any function returning a value. Arguments and function result
    must be pickleable.
    """
    def decorator(function):
        cache = SimpleCache(limit, expire)
        
        @wraps(function)
        def func(*args):
            key = pickle.dumps(args)
            cache_key = '%s:%s' % (function.__name__, key)
            if cache_key in cache:
                try:
                    return cache.get_pickle(cache_key)
                except (ExpiredKeyException, CacheMissException) as e:
                    pass
        
            result = function(*args)
            cache.store_pickle(cache_key, result)
            return result
        return func
    return decorator


def cache_it_json(limit=1000, expire=60 * 60 * 24):
    """
    A decorator similar to cache_it, but it serializes the return value to json, while storing
    in the database. Useful for types like list, tuple, dict, etc.
    """
    def decorator(function):
        cache = SimpleCache()
        
        @wraps(function)
        def func(*args):
            key = json.dumps(args)
            cache_key = '%s:%s' % (function.__name__, key)
            if cache_key in cache:
                try:
                    return cache.get_json(cache_key)
                except (ExpiredKeyException, CacheMissException) as e:
                    pass
                
            result = function(*args)
            cache.store_json(cache_key, result)
            return result
        return func
    return decorator


def to_unicode(obj, encoding='utf-8'):
    if isinstance(obj, basestring):
        if not isinstance(obj, unicode):
            obj = unicode(obj, encoding)
    return obj
