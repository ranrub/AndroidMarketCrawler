# Simple script for crawling the Android Marketplace.
The code is forked from 
[AndroidMarketCrawler by Alexandru Nedelcu](https://github.com/alexandru/AndroidMarketCrawler)

For implemetation, see this article for details:

[Crawling the Android Marketplace: 155,200 Apps](http://bionicspirit.com/blog/2011/12/15/crawling-the-android-marketplace-155200-apps.html)

The following modification has been applied to the original project:
1. Class AndroidAppFetcher to fetch the info of a single app;
2. Language setting could be specfied for fetching apps;
3. Fetch icon, screen and banner image links of an app.
4. A setup.py for the package installation.  

Installing dependencies:

```bash
easy_install pyquery
easy_install eventlet
```

Of if you're using pip:

```bash
pip install -r reqs.txt
```

Usage:

```
python android_app_fecher.py app.package.name
python android_market_crawler.py path/to/destination.json_lines
```
