# redis-simple-cache
redis-simple-cache is a pythonic interface for creating a cache over redis.  
It provides simple decorators that can be added to any function to cache its return values.

Requirements:
-------------
redis 2.6.2  
redis-py 2.7.1 (see requirements.txt file)

Installation:
-------------

    pip install redis-simple-cache

or to get the latest version

    git clone git://github.com/vivekn/redis-simple-cache.git
    cd redis-simple-cache
    python setup.py install

Usage:
------

    from redis_cache import cache_it_json

    @cache_it_json(limit=1000, expire=60 * 60 * 24)
    def fib(n):
        if n == 0:
            return 0
        elif n == 1:
            return 1
        else:
            return fib(n-1) + fib(n-2)

`limit` is the maximum number of keys, `expire` is the expire time in seconds.  
It is always recommended to specify a expire time, since by default redis-server will only remove keys with an expire time set in a event of full memory. But if you wish your keys to never expire, set `expire` to `None`.  
**Note that function arguments and result must be pickleable, since cache_it uses the pickle module.**

It is also possible to use redis-simple-cache as a object-oriented cache:
        
    >> from redis_cache import SimpleCache
    >> c = SimpleCache(10)  # cache that has a maximum limit of 10 keys
    >> c.store("foo", "bar")
    >> c.get("foo")
    'bar'
    >> "foo" in c  # efficient membership test, time-complexity O(1)
    True
    >> len(c)  # efficient cardinality calculation, time-complexity O(1)
    1
    >> c.keys()  # returns all keys, time-complexity O(N) with N being the cache c cardinality
    set(['foo'])
    >> c.flush()  # flushes the cache, time-complexity O(N) with N being the cache c cardinality
    >> "foo" in c
    False
    >> len(c)
    0

Check out more examples in the test_rediscache.py file.

Advanced:
---------
Advanced users can customize the decorators even more by passing a SimpleCache object. For example:
    
    my_cache = SimpleCache(limit=100, expire=60 * 60, hashkeys=True, host='localhost', port=6379, db=1, namespace='Fibonacci')
    @cache_it(cache=my_cache)
    def fib(n):
        # ...

`hashkeys` parameter makes the SimpleCache to store keys in md5 hash. It is `True` by default in decorators, but `False` by default in a new SimpleCache object.  
`host`, `port` and `db` are the same redis config params used in StrictRedis class of redis-py.
By default, the `namespace` is the name of the module from which the decorated function is called, but it can be overridden with the `namespace` parameter. 

AUTHOR: Vivek Narayanan  

CONTRIBUTORS: 

Flávio Juvenal

Sam Zaydel  

David Ng

DJ Gilcrease

Johannes Maximilian Toball

Robert Marshall

Ben Hayden


Python 3 support added by Omer Hanetz

LICENSE: BSD
