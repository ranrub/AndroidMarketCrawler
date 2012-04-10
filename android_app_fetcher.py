#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import urllib
import simplejson as json
import sys
import urllib2

# using PyQuery for querying retrieved HTML content using CSS3
# selectors (awesome!)
from pyquery import pyquery as pq

class AndroidAppFetcher(object):
    '''
    Fetcher of a single app.
    '''
    urllib = urllib2
    
    def __init__(self, url, lang='en'):
        '''
        lang is used to specify the result language of the crawler.
        '''
        self.url = url
        self.browser = self.urllib.build_opener()
        self.browser.addheaders.append(('Cookie', 'hlSession2=%s'%lang))
        self.app_info = None
        self.all_links = []

    def fetch_content(self):
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
            resp = self.browser.open(self.url)

        except urllib2.HTTPError, ex:
            # silently ignores errors, even though the script will not
            # block here.
            if ex.code == 404: 
                return

            # this is a slight problem, it shouldn't happen but it
            # does sometimes, so keeping tracking is useful to see how
            # often it does happen
            raise urllib2.HTTPError, ex

        content = resp.read()
        self.doc = pq.PyQuery(content.decode('utf-8'))

        # we must do our best to ignore pages that are not
        # relevant (music, movies, other pages that don't have
        # links to apps in them)
        if not self.is_page_valid():
            return         

        # I like keeping a log of URLs processed
        sys.stderr.write(self.url + "\n")

        # fetches links in this page, by regular expressions. 
        # we are interested in app links and publisher links.
        self.all_links = [
            a.attrib['href']
            for a in self.doc('a') 
            if re.search(r'\/(details|developer)[?]', a.attrib.get('href', '')) \
            and not re.search('reviewId', a.attrib.get('href', '')) \
            and not re.search('accounts\/ServiceLogin', a.attrib.get('href', ''))
        ]

        # fetches app info from the fetched content, but ONLY in
        # case the URL is about an actual app
        self.app_info = self.fetch_app_info()

    def is_page_valid(self):
        """
        This is a hackish method to determine if the visited page is
        useful at all.

        The big problem is that I cannot infer the type of item I've
        got just from the link. Links for audio, movies and apps have
        the same format.

        `doc` is therefore an instantiated PyQuery document with the
        fetched content.

        What this buys us is that we can then ignore links from
        invalid pages (as movies will tend to link to other movies,
        not to other apps).
        """
        if self.url == "https://play.google.com/store/apps/":
            return True
        if self.url.startswith("https://play.google.com/store/apps/details?id=apps_topselling_paid"):
            return True
        if self.url.startswith("https://play.google.com/store/apps/details?id=apps_topselling_free"):
            return True
        if not re.search(r'details|developer', self.url):
            return False
        if re.search('reviewId', self.url):
            return False
        params = self.query_vars(self.url)
        if not params.get('id') and not params.get('pub'): 
            return False
        if re.search(r'developer', self.url):
            if not (self.doc('h1.page-banner-text').text() or '').lower().startswith('apps by'):
                return False
            return True
        if not self.doc('div.apps.details-page'): 
            return False
        if not any( [re.search(r'/apps', a.get('href', '')) for a in self.doc('.breadcrumbs a')] ):
            return True
        #if 'Apps' not in self.doc('.page-content .breadcrumbs a').text():
        #    return False
        return True

    def fetch_app_info(self):
        """
        At this point, we are almost sure we have an app, so this
        method attempts parsing the content into a dictionary.

        We are using PyQuery and CSS3 selectors heavily.
        """
        params = self.query_vars(self.url)
        if not params.get('id'): return None
        if not self.doc('div.apps.details-page'): return None
        #if not any( [re.search(r'/apps', a.get('href', '')) for a in self.doc('.breadcrumbs a')] ):
        #    return None
        #if 'Apps' not in self.doc('.page-content .breadcrumbs a').text():
        #    return None

        app_info = {
            'uid': params['id'],
            'name': self.doc('h1.doc-banner-title').text(),
            'app_link': self.absolute_url('/details?id=' + params['id']),
            'dev_name': self.doc('a.doc-header-link').text(),
            'dev_link': self.absolute_url(self.doc('a.doc-header-link').attr['href']),
            'dev_web_links': list(set([
                self.query_vars(a.attrib['href'])['q'] 
                for a in self.doc('.doc-overview a') 
                if a.text and "Visit Developer's Website" in a.text
            ])),
            'dev_emails': list(set([
                a.attrib['href'][len('mailto:'):] 
                for a in self.doc('.doc-overview a') 
                if a.attrib.get('href', '').startswith('mailto:')
            ])),
            'rating_count': int(re.sub(r'\D+', '', self.doc('[itemprop=ratingCount]').text() or '0')),
            'rating_value': self.doc('[itemprop=ratingValue]').attr['content'],
            'description_html': self.doc('#doc-original-text').html(),
            'more-from-developer': [
                self.query_vars(a.attrib['href'])['id'] 
                for a in self.doc('[data-analyticsid=more-from-developer] a.common-snippet-title')
            ],
            'users_also_installed': [
                self.query_vars(a.attrib['href'])['id'] 
                for a in self.doc('[data-analyticsid=users-also-installed] a.common-snippet-title')
            ],
            'users_also_viewed': [
                self.query_vars(a.attrib['href'])['id'] 
                for a in self.doc('[data-analyticsid=related] a.common-snippet-title')
            ],
            'icon_link': self.doc('.doc-banner-icon img').attr('src'),
            'screenshot_links': [ a.get('src') for a in self.doc('.screenshot-carousel-content-container img') ],
            'banner_link': self.doc('.doc-banner-image-container img').attr('src'),
            
        }

        match = re.findall(r'.*[\d\.]+', self.doc('.buy-button-price').text())
        if match:
            app_info['is_free'] = False
            app_info['price'] = match[0]
        else:
            app_info['is_free'] = True
            app_info['price'] = 0

        match = [a.text for a in self.doc('.doc-metadata-list dd a') if 'category' in a.attrib.get('href')]
        if match: app_info['category'] = match[0]
            
        match = [re.search(r'/store/apps/category/(\w+)\?', a.get('href', '')) for a in self.doc('dd a')]
        if match and match[-1]:
            app_info['category_tag'] = match[-1].groups()[0]
            
        match = re.findall('([\d,]+)\s*-\s*([\d,]+)', self.doc('[itemprop=numDownloads]').text() or '')
        if match:
            imin, imax = [re.sub(r'\D+', '', m) for m in match[0]]
            app_info['installs_min'] = int(imin)
            app_info['installs_max'] = int(imax)

        return app_info

    def get_id(self, url):
        """
        Extracts the ID param from a Marketplace URL.
        """
        params = self.query_vars(url)
        return params.get('id')

    def query_vars(self, url):
        """
        Parses the query part of an URL. It was faster to implement
        this myself, than to find something already available.
        """
        v = {}
        match = re.findall('[^?]+[?](.*)$', url)

        if match:
            query = match[0]
            parts = query.split('&')
            for part in parts:
                keyval = [urllib.unquote_plus(i) for i in part.split('=', 1)]
                key, val = keyval if len(keyval) == 2 else (keyval[0], '')
                v[key] = val

        return v

    def absolute_url(self, url):
        """
        Converts relative URL to a Marketplace absolute URL.
        """
        if url and url.startswith('/'):
            return "https://play.google.com/store/apps" + url
        return url or ''
        
if __name__ == '__main__':
    if len(sys.argv) <= 1:
        sys.stderr.write("\nERROR: target package name is missing!\n\n")
        sys.exit(1)

    url = "https://play.google.com/store/apps/details?id=%s"%sys.argv[1]
    fetcher = AndroidAppFetcher(url)
    fetcher.fetch_content()
    if fetcher.app_info:
        print json.dumps(fetcher.app_info, indent='    ')