#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
The code is forked from 

Simple script for crawling the Android Marketplace.
See this article for details:

  http://bionicspirit.com/blog/2011/12/15/crawling-the-android-marketplace-155200-apps.html

Usage:

  python crawler.py path/to/destination.json_lines

Warnings:

  - Google may not allow this for long, you may get your IP blocked
  - this will eat several GB of your monthly allocated bandwidth
  - I ran this from a VPS in San Franscisco, with good bandwidth and
    it still took ~ 5 hours to complete
"""

# we are using eventlet for concurrent requests by means of async I/O
# and greenthreads, see the sample at:
#   http://eventlet.net/doc/examples.html#recursive-web-crawler
import eventlet
import os
import re
import urllib
import simplejson as json
import sys

from eventlet.green import urllib2
from android_app_fetcher import AndroidAppFetcher

AndroidAppFetcher.urllib = urllib2

class AndroidMarketCrawler(object):
    """
    Our Marketplace crawler.

    Usage:
    
      for app in AndroidMarketCrawler(concurrency=10):
          # app is a dictionary with the values of a retrieved app
          print app['dev_name']
    """
    def __init__(self, concurrency=10):
        # a green pool is a pool of greenthreads - you're pushing
        # tasks to it and they get executed when eventlet's loop is
        # active
        self.pool = eventlet.GreenPool(concurrency)        
        # the queue receives URLs to visit
        self.queue = eventlet.Queue()
        # our root URL, the first to be fetched
        self.queue.put("https://play.google.com/store/apps/details?id=com.google.android.gm")
        # after a fetch of an app is finished, results get pushed in
        # this queue
        self.results = eventlet.Queue()
        # we need to make sure we don't fetch the same URL more than
        # once, otherwise the script might never finish
        self.seen = set()
        # `seen_app_ids` cuts down on fetching apps that have been
        # fetched before; it is necessary in addition to `seen`
        self.seen_app_ids = set()
        # just a counter for statistics
        self.failed = 0

        # our opener
        #self.browser = urllib2.build_opener()
        #self.browser.addheaders.append(('Cookie', 'hlSession2=en'))

    def next(self):
        """
        Implements the iterator protocol for `AndroidMarketCrawler`
        (see usage example above)
        """

        # when there are results, then return them even though you've
        # got other things to do, too
        if not self.results.empty():
            return self.results.get()

        # as long as there are tasks scheduled in the queue, or as
        # long as there are active scripts running ...
        while not self.queue.empty() or self.pool.running() != 0:
            # gets a new URL from the queue, to be fetched. if the
            # queue is empty, then waits until it isn't (eventlet's
            # run-loop can continue processing during this wait)
            url = eventlet.with_timeout(0.1, self.queue.get, timeout_value='')

            # if we have a new URL, then we spawn another green thread for fetching the content
            if url:
                if url in self.seen: continue
                self.seen.add(url)
                self.pool.spawn_n(self.fetch_content, url)

            # in case we have results waiting to be served, then
            # return
            if not self.results.empty():
                return self.results.get()

        raise StopIteration


    def fetch_content(self, url):
        """
        Fetches the content of an URL, gets app links from it and
        pushes them down the queue. Then parses the content to
        determine if it is an app and if it is, then push the parsed
        result in the `results` queue for later processing.

        This logic is getting executed inside green threads. You
        shouldn't spawn new green threads here, as this is not the
        parent and trouble may arise.
        """
        try:
            fetcher = AndroidAppFetcher(url)
            fetcher.fetch_content()

            # fetches app info from the fetched content, but ONLY in
            # case the URL is about an actual app
            app_info = fetcher.app_info
            if app_info:
                # prevents going to already visited IDs
                self.seen_app_ids.add(app_info['uid'])                
                self.results.put(app_info)          
            
            # pushing new links down the queue for processing later
            for link in fetcher.all_links:
                if not link: continue
                uid = fetcher.get_id(link)
                if uid in self.seen_app_ids or (link.find('/details?')==-1): continue
                self.queue.put(fetcher.absolute_url('/details?id='+uid))

        except urllib2.HTTPError, ex:
            # silently ignores errors, even though the script will not
            # block here.
            if ex.code == 404: 
                return

            # this is a slight problem, it shouldn't happen but it
            # does sometimes, so keeping tracking is useful to see how
            # often it does happen
            self.failed += 1
            return

        except urllib2.URLError:
            self.failed += 1
            return

    def __iter__(self):
        return self



if __name__ == '__main__':
    if len(sys.argv) <= 1:
        sys.stderr.write("\nERROR: destination filepath is missing!\n\n")
        sys.exit(1)
        
    fh = open(sys.argv[1], 'w')

    # we are dumping JSON objects, one on each line (this file will be
    # huge, so it's a bad idea to serialize the whole thing as an
    # array
    for app in AndroidMarketCrawler(concurrency=10):
        fh.write(json.dumps(app) + "\n")
        fh.flush()

    fh.close()
