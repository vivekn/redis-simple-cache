"""
A simple redis-cache interface for storing python objects.
"""
from functools import wraps
import pickle
import json
import hashlib
import redis
import logging

class RedisConnect(object):
    '''
    A simple object to store and pass database connection information.
    This makes the Simple Cache class a little more flexible, for cases
    where redis connection configuration needs customizing.
    '''

    def __init__(self, host=None, port=None, db=None):
        self.host = host if host else 'localhost'
        self.port = port if port else 6379
        self.db = db if db else 0

    def connect(self):
        '''
        We cannot assume that connection will succeed, as such we use a ping()
        method in the redis client library to validate ability to contact redis.
        RedisNoConnException is raised if we fail to ping.
        '''
        try:
            redis.StrictRedis(host=self.host, port=self.port).ping()
        except redis.ConnectionError as e:
            raise RedisNoConnException, ("Failed to create connection to redis",
                                         (self.host,
                                          self.port)
                )
        return redis.StrictRedis(host=self.host, port=self.port, db=self.db)


class CacheMissException(Exception):
    pass


class ExpiredKeyException(Exception):
    pass


class RedisNoConnException(Exception):
    pass


class SimpleCache(object):

    def __init__(self, limit=10000, expire=60 * 60 * 24,
                 hashkeys=False, host=None, port=None, db=None, namespace="SimpleCache"):
        self.limit = limit  # No of json encoded strings to cache
        self.expire = expire  # Time to keys to expire in seconds

        self.prefix = namespace

        ## database number, host and port are optional, but passing them to
        ## RedisConnect object is best accomplished via optional arguments to
        ## the __init__ function upon instantiation of the class, instead of
        ## storing them in the class definition. Passing in None, which is a
        ## default already for database host or port will just assume use of
        ## Redis defaults.
        self.host = host
        self.port = port
        self.db = db
        ## We cannot assume that connection will always succeed. A try/except
        ## clause will assure unexpected behavior and an unhandled exception do not result.
        try:
            self.connection = RedisConnect(host=self.host, port=self.port, db=0).connect()
        except RedisNoConnException, e:
            self.connection = None
            pass

        ## There may be instances where we want to create hashes for
        ## keys to have a consistent length.
        self.hashkeys = hashkeys

    def make_key(self, key):
        return "SimpleCache-{0}:{1}".format(self.prefix, key)

    def get_set_name(self):
        return "SimpleCache-{0}-keys".format(self.prefix)

    def store(self, key, value, expire=None):
        """ Stores a value after checking for space constraints and freeing up space if required """
        key = to_unicode(key)
        value = to_unicode(value)
        set_name = self.get_set_name()

        while self.connection.scard(set_name) >= self.limit:
            del_key = self.connection.spop(set_name)
            self.connection.delete(self.make_key(del_key))

        pipe = self.connection.pipeline()
        if expire is None:
            expire = self.expire
        pipe.setex(self.make_key(key), expire, value)
        pipe.sadd(set_name, key)
        pipe.execute()

    def expire_all_in_set(self):
        """
        Method expires all keys in the namespace of this object. At times there is
        a need to invalidate cache in bulk, because a single change may result
        in all data returned by a decorated function to be altered.
        Method returns a tuple where first value is total number of keys in the set of
        this object's namespace and second value is a number of keys successfully expired.
        """
        all_members = self.keys()
        
        pipe = self.connection.pipeline()
        for member in all_members:
            pipe.expire("{0}:{1}".format(self.prefix, member), 0)
        expired = len(filter(pipe.execute()))

        return len(self), expired

    def store_json(self, key, value):
        self.store(key, json.dumps(value))

    def store_pickle(self, key, value):
        self.store(key, pickle.dumps(value))

    def get(self, key):
        key = to_unicode(key)
        if key in self:
            val = self.connection.get(self.make_key(key))
            if val is None:  # expired key
                self.connection.srem(self.get_set_name(), key)
                raise ExpiredKeyException
            else:
                return val
        raise CacheMissException

    def get_json(self, key):
        return json.loads(self.get(key))

    def get_pickle(self, key):
        return pickle.loads(self.get(key))

    def __contains__(self, key):
        return self.connection.sismember(self.get_set_name(), key)

    def __iter__(self):
        "Returns a list of redis keys in this cache namespace"
        return iter(["{0}:{1}".format(self.prefix, x)
                    for x in self.connection.smembers(self.get_set_name())])

    def __len__(self):
        "Return number of members in the given key namespace."
        return self.connection.scard(self.get_set_name())

    def keys(self):
        return self.connection.smembers(self.get_set_name())

    def flush(self):
        keys = self.keys()
        pipe = self.connection.pipeline()
        for del_key in keys:
            pipe.delete(self.make_key(del_key))
        pipe.delete(self.get_set_name())
        pipe.execute()


def cache_it(limit=10000, expire=60 * 60 * 24, cache=None):
    """
    Apply this decorator to cache any function returning a value. Arguments and function result
    must be pickleable.
    """
    cache_ = cache  ## Since python 2.x doesn't have the nonlocal keyword, we need to do this
    def decorator(function):
        cache = cache_
        if cache is None:
            cache = SimpleCache(limit, expire, hashkeys=True, namespace=function.__module__)

        @wraps(function)
        def func(*args):
            ## Handle cases where caching is down or otherwise not available.
            if cache.connection is None:
                result = function(*args)
                return result

            ## Key will be either a md5 hash or just pickle object,
            ## in the form of `function name`:`key`
            if cache.hashkeys:
                key = hashlib.md5(pickle.dumps(args)).hexdigest()
            else:
                key = pickle.dumps(args)
            cache_key = '%s:%s' % (function.__name__, key)

            if cache_key in cache:
                try:
                    return cache.get_pickle(cache_key)
                except (ExpiredKeyException, CacheMissException) as e:
                    pass
                except:
                    logging.exception("Unknown redis-simple-cache error. Please check your Redis free space.")

            result = function(*args)
            cache.store_pickle(cache_key, result)
            return result
        return func
    return decorator


def cache_it_json(limit=10000, expire=60 * 60 * 24, cache=None):
    """
    A decorator similar to cache_it, but it serializes the return value to json, while storing
    in the database. Useful for types like list, tuple, dict, etc.
    """
    cache_ = cache  ## Since python 2.x doesn't have the nonlocal keyword, we need to do this
    def decorator(function):
        cache = cache_
        if cache is None:
            cache = SimpleCache(limit, expire, hashkeys=True, namespace=function.__module__)

        @wraps(function)
        def func(*args):
            ## Handle cases where caching is down or otherwise not available.
            if cache.connection is None:
                result = function(*args)
                return result

            ## Key will be either a md5 hash or just pickle object,
            ## in the form of `function name`:`key`
            if cache.hashkeys:
                key = hashlib.md5(json.dumps(args)).hexdigest()
            else:
                key = json.dumps(args)
            cache_key = '%s:%s' % (function.__name__, key)

            if cache_key in cache:
                try:
                    return cache.get_json(cache_key)
                except (ExpiredKeyException, CacheMissException) as e:
                    pass
                except:
                    logging.exception("Unknown redis-simple-cache error. Please check your Redis free space.")

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