#!/usr/bin/env python

sdict = {
    'name' : 'android-market-crawler',
    'version' : "0.1",
    'license' : 'MIT',
    'py_modules' : ['android_app_fetcher', 'android_market_crawler'],
    'install_requires' : ['pyquery', 'eventlet'],
    'classifiers' : [
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python']
}

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
    
setup(**sdict)
