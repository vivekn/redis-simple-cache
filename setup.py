#coding=utf-8
import os
from setuptools import setup

def openf(fname):
    return open(os.path.join(os.path.dirname(__file__), fname))

setup(
    name="redis-simple-cache-3k",
    version="0.0.7",
    author="Vivek Narayanan, Flávio Juvenal, Sam Zaydel. Python 3 and Redis 4 support by Omer Hanetz",
    author_email="flaviojuvenal@gmail.com",
    description="redis-simple-cache is a pythonic interface for creating a cache over redis. "
                "It provides simple decorators that can be added to any function to cache its return values. ",
    license="3-clause BSD",
    keywords="decorator decorators redis cache",
    url="https://github.com/ohanetz/redis-simple-cache-3k",
    packages=['redis_cache'],
    long_description=openf("README.md").read(),
    long_description_content_type='text/markdown',
    install_requires=[line.strip() for line in openf("requirements.txt") if line.strip()],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
    ],
)
