# -*- coding: utf-8 -*-
import logging
import types
import couchdb
import os
import re
import urllib
import urllib2
import json
import Levenshtein
import functools
import HTMLParser
import pprint
import memcache
import hashlib
from apiclient import discovery
from apiclient import model
from operator import itemgetter, attrgetter
from pymediainfo import MediaInfo
from bliss.client import get_json
from bliss.utils import escape_generic, Unbuffered
import bliss.config as config

logger = logging.getLogger('bliss.scanner')

model.JsonModel.alt_param = ""
freebase = discovery.build('freebase', 'v1', developerKey=config.FB_KEY)

def parse_name(name):
    match = re.search('(.+?[^0-9])([0-9]{4})[^0-9]', name)
    year = None
    if match:
        name = match.group(1)
        year = match.group(2)
    name = name.decode('utf-8')
    name = re.sub(r"[^\w-]", " ", name, flags=re.IGNORECASE+re.UNICODE)
    name = re.sub(r"_", " ", name)
    name = re.sub(r"dvdrip.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"720p.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"1080p.*", "", name, flags=re.IGNORECASE)
    name = name.replace("UNRATED", "")
    name = name.encode('utf-8')
    return name, year


def get_files(n):
    fs = []
    for f in os.listdir(os.path.join(config.BASEDIR, n)):
        if f.lower().find("sample") == -1:
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.avi', '.mpg', '.mkv']:
                fs.append(f)
    return sorted(fs)

def get_duration(f):
    mc = memcache.Client(['127.0.0.1:11211'], debug=0)
    key = escape_generic(f)
    d = mc.get(key)
    if d is not None:
        return d
    else:
        d = 0
    info = MediaInfo.parse(f)
    for track in info.tracks:
        if getattr(track, 'duration') is not None:
            d = track.duration
            break
    mc.set(key, d)
    return d


def search(name, year, duration, alias=False):
    name = name.strip()
    logger.debug("Trying to match %s, %s, %s, %s" % (name, year, duration, alias))
    query = [{
            "imdb_id":        {"value" : None, "optional" : True, "limit" : 1},
            "type":          "/film/film",
            "id":            None,
            "name":  None,
            "/common/topic/alias": [{}],
            "limit":         1}]
    if alias:
        query[0]["/common/topic/alias~="] = name
    else:
        query[0]["name~="] = name
    
    if year is not None:
        query[0]["initial_release_date"] = [{
                "type":    "/type/datetime",
                "value<":  "%d" % (int(year)+2),
                "value>": "%d" % (int(year)-2), 
                }]
    else:
        query[0]["sort"] = "-initial_release_date"
        query[0]["initial_release_date"] = None
    if duration is not None:
        query[0]["runtime"] = [{
                "id":            None,
                "runtime>":       (duration-10),
                "runtime<":       (duration+10),
                "type_of_film_cut": None,
                "film_release_region": None,
                "note":          None
                }]
    else:
        query[0]["runtime"] = [{
                "id":            None,
                "runtime":       None,
                "type_of_film_cut": None,
                "film_release_region": None,
                "note":          None
                }]
    logger.debug("executing query:\n%s" % json.dumps(query, indent=4))
    res = freebase.mqlread(query=json.dumps(query)).execute()
    response = json.loads(res)
    if len(response['result']) > 0:
        return response['result'][0]
    else:
        if not alias:
            return search(name, year, duration, True)
        else:
            if duration is not None:
                return search(name, year, None, True)
            else:
                fuzz = " ".join(name.split()[:-1])
                if len(fuzz) > 0 and not fuzz == name:
                    return search(fuzz, year, duration, False)
                else:
                    return None
                
def get_poster(imdb_id):
    data = get_json('http://api.rottentomatoes.com/api/public/v1.0/movie_alias.json?type=imdb&id=%s&apikey=%s&_prettyprint=true' % (imdb_id.replace("tt", ""), config.RT_KEY), {})
    if "error" in data:
        return (None, None)
    
    url = data["posters"]["original"]
    response = urllib2.urlopen(url)
    data = response.read()
    
    return (response.headers["Content-Type"], data)
    
if __name__ == "__main__":
    import sys
    sys.stdout=Unbuffered(sys.stdout)
    for name in os.listdir(config.BASEDIR):
#    for name in ['50-50.mkv']:
        if os.path.isdir(os.path.join(config.BASEDIR, name)):
            o = name
            files = get_files(o)
            d = 0
            for f in files:
                d = d + get_duration(os.path.join(config.BASEDIR, o, f))
            realid = hashlib.md5(",".join(files)).hexdigest()
            if realid in config.db:
                continue
            name, year = parse_name(name)
            match = search(name, year, d / 1000 / 60)
            if match is None:
                print "FAIL | %s | FAIL" % (o)
            else:
                data = {"_id": realid,
                        "title": match["name"],
                        "type": "movie"}
                data["files"] = {}
                for f in files:
                    data["files"][f] = []
                    print os.path.join(config.BASEDIR, o, f)
                    info = MediaInfo.parse(os.path.join(config.BASEDIR, o, f))
                    for track in info.tracks:
                        d = {}
                        for k, v in track.__dict__.iteritems():
                            if not type(v) == types.InstanceType:
                                d[k] = v
                        data["files"][f].append(d)
                print config.db.save(data)
                try:
                    content_type, poster = get_poster(match["imdb_id"]["value"])
                    if not poster is None:
                        config.db.put_attachment(data, poster, "poster", content_type)
                except:
                    del config.db[data['_id']]
                    raise
        else:
            split = os.path.splitext(name)
            ext = split[1].lower()
            if ext in ['.avi', '.mpg', '.mkv']:
                o = name
                d = get_duration(os.path.join(base, o))
                name = split[0]
                name, year = parse_name(name)
                m = search(name, year, d)
                # TODO: Implement
