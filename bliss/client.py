import os
import urllib
import urllib2
import simplejson
import re
from collections import OrderedDict
from bliss.utils import escape_generic

def get_json(url, data):
    url = '%s?%s' % (url, urllib.urlencode(OrderedDict(sorted(data.items()))))
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'resources', 'cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    fn = os.path.join(cache_dir, escape_generic(url))
    if os.path.exists(fn):
        with open(fn, "r") as f:
            return simplejson.loads(f.read())
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; WOW64; Trident/6.0)')]
    response = opener.open(url)
    data = response.read()
    if not os.path.exists(fn):
        with open(fn, "w") as f:
            f.write(data)
    data = simplejson.loads(data)
    return data

def post_json(url, data):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; WOW64; Trident/6.0)')]
    response = opener.open(url, urllib.urlencode(data))
    data = response.read()
    data = simplejson.loads(data)
    return data

