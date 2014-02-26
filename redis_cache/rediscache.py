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
    """
    A simple object to store and pass database connection information.
    This makes the Simple Cache class a little more flexible, for cases
    where redis connection configuration needs customizing.
    """
    def __init__(self, host=None, port=None, db=None, password=None):
        self.host = host if host else 'localhost'
        self.port = port if port else 6379
        self.db = db if db else 0
        self.password = password

    def connect(self):
        """
        We cannot assume that connection will succeed, as such we use a ping()
        method in the redis client library to validate ability to contact redis.
        RedisNoConnException is raised if we fail to ping.
        :return: redis.StrictRedis Connection Object
        """
        try:
            redis.StrictRedis(host=self.host, port=self.port, password=self.password).ping()
        except redis.ConnectionError as e:
            raise RedisNoConnException("Failed to create connection to redis",
                                       (self.host,
                                        self.port)
            )
        return redis.StrictRedis(host=self.host,
                                 port=self.port,
                                 db=self.db,
                                 password=self.password)


class CacheMissException(Exception):
    pass


class ExpiredKeyException(Exception):
    pass


class RedisNoConnException(Exception):
    pass


class SimpleCache(object):
    def __init__(self,
                 limit=10000,
                 expire=60 * 60 * 24,
                 hashkeys=False,
                 host=None,
                 port=None,
                 db=None,
                 password=None,
                 namespace="SimpleCache"):

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
            self.connection = RedisConnect(host=self.host,
                                           port=self.port,
                                           db=0,
                                           password=password).connect()
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
        """
        Method stores a value after checking for space constraints and
        freeing up space if required.
        :param key: key by which to reference datum being stored in Redis
        :param value: actual value being stored under this key
        :param expire: time-to-live (ttl) for this datum
        """
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
        :return: int, int
        """
        all_members = self.keys()

        pipe = self.connection.pipeline()
        for member in all_members:
            pipe.expire(self.make_key(member), 0)
        expired = len(filter(None, pipe.execute()))
        return len(self), expired

    def isexpired(self, key):
        """
        Method determines whether a given key is already expired. If not expired,
        we expect to get back current ttl for the given key.
        :param key: key being looked-up in Redis
        :return: bool (True) if expired, or int representing current time-to-live (ttl) value
        """
        ttl = self.connection.pttl("SimpleCache-{0}".format(key))
        if ttl == -1:
            return True
        if not ttl is None:
            return ttl
        else:
            return self.connection.pttl("{0}:{1}".format(self.prefix, key))

    def store_json(self, key, value):
        self.store(key, json.dumps(value))

    def store_pickle(self, key, value):
        self.store(key, pickle.dumps(value))

    def get(self, key):
        key = to_unicode(key)
        if key:  # No need to validate membership, which is an O(1) operation, but seems we can do without.
            value = self.connection.get(self.make_key(key))
            if value is None:  # expired key
                if not key in self:  # If key does not exist at all, it is a straight miss.
                    raise CacheMissException

                self.connection.srem(self.get_set_name(), key)
                raise ExpiredKeyException
            else:
                return value

    def get_json(self, key):
        return json.loads(self.get(key))

    def get_pickle(self, key):
        return pickle.loads(self.get(key))

    def __contains__(self, key):
        return self.connection.sismember(self.get_set_name(), key)

    def __iter__(self):
        if not self.connection:
            return iter([])
        return iter(
            ["{0}:{1}".format(self.prefix, x)
                for x in self.connection.smembers(self.get_set_name())
            ])

    def __len__(self):
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
    Apply this decorator to cache any pure function returning a value. Any function
    with side-effects should be wrapped.
    Arguments and function result must be pickleable.
    :param limit: maximum number of keys to maintain in the set
    :param expire: period after which an entry in cache is considered expired
    :param cache: SimpleCache object, if created separately
    :return: decorated function
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

            try:
                return cache.get_pickle(cache_key)
            except (ExpiredKeyException, CacheMissException) as e:
                ## Add some sort of cache miss handing here.
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
    Apply this decorator to cache any pure function returning a value. Any function
    with side-effects should be wrapped. Arguments and function result
    must be able to convert to JSON.
    :param limit: maximum number of keys to maintain in the set
    :param expire: period after which an entry in cache is considered expired
    :param cache: SimpleCache object, if created separately
    :return: decorated function
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