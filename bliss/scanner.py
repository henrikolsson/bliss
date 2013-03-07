# -*- coding: utf-8 -*-
import types
import couchdb
import os
import re
import urllib
import urllib2
import simplejson
import Levenshtein
import functools
import HTMLParser
import pprint
import memcache
from operator import itemgetter, attrgetter
from pymediainfo import MediaInfo
from bliss.client import get_json
from bliss.utils import escape_generic

def parse_name(name):
    match = re.search('(.+?[^0-9])([0-9]{4})[^0-9]', name)
    year = None
    if match:
        name = match.group(1)
        year = match.group(2)
    name = name.decode('utf-8')
    name = re.sub(r"[^\w]", " ", name, flags=re.IGNORECASE+re.UNICODE)
    name = re.sub(r"_", " ", name)
    name = re.sub(r"dvdrip.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"720p.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"1080p.*", "", name, flags=re.IGNORECASE)
    name = name.replace("UNRATED", "")
    name = name.encode('utf-8')
    return name, year

def ratio(s1, s2):
    r = Levenshtein.ratio(s1, s2)
    return r

def correct_year(year, item):
    if year is None:
        return 0
    match = re.search('^([0-9]{4})', item["description"])
    if match:
        return abs(int(match.group(0)) - int(year))
    else:
        return 20

def search(title, year, dur):
    title = title.strip()
    data = get_json('http://www.imdb.com/xml/find', {'q': title, 'json': '1', 'tt': 'on', 'nr': '1'})
    weights = {"title_popular": 2.5,
               "title_exact": 1.8,
               "title_substring": 0.8,
               "title_approx": 0.6}
    matches = []
    for key in weights.iterkeys():
        if key in data:
            i = 0
            for match in data[key]:
                match["score"] = {}
                match["title"] = HTMLParser.HTMLParser().unescape(match["title"])
                match["title"] = match["title"].encode("utf-8")
                match["score"]["position"] = (len(data[key]) - i) / float(len(data[key]))
                match["score"]["type"] = weights[key]
                match["score"]["year"] = correct_year(year, match)
                match["score"]["ratio"] = Levenshtein.ratio(match["title"],
                                                            title)
                match["score"]["distance"] = Levenshtein.distance(match["title"],
                                                                  title)
                
                matches.append(match)
                i = i + 1
    for match in matches:
        score = match["score"]
        match["score_value"] = 1
        match["score_value"] = match["score_value"] - score["year"] / 8.0
        match["score_value"] = match["score_value"] + score["position"] * 1.4
        match["score_value"] = match["score_value"] + score["ratio"] * 1.5
        match["score_value"] = match["score_value"] - score["distance"] / 100.0
        match["score_value"] = match["score_value"] * score["type"]
    matches = sorted(matches, key=lambda match: match["score_value"], reverse=True)
    if dur > 0:
        ids = ""
        for match in matches[:10]:
            ids = ids + match["id"] + ","
        ids = reduce(lambda acc, match: acc + match["id"] + ',', matches[:10], '')
#        print "ids: %s" % ids
        if len(ids) > 0:
            js = get_json('http://imdbapi.org/', {'episode': '0', 'format': 'json', 'ids': ids})
            for item in js:
                for mm in matches[:10]:
                    if mm['id'] == item["imdb_id"]:
                        if "runtime" in item:
                            d = None
                            
                            for rt in item['runtime']:
                                d2 = abs((dur / 1000 / 60) - long(re.search(r"([0-9]+)", rt).group(0)))
                                if d is None:
                                    d = d2
                                else:
                                    d = min(d, d2)
                            if d is None:
                                d = 30
                            else:
#                                print mm["title"], (dur / 1000 / 60), d
                                mm["score"]["duration"] = d
    for match in matches:
        score = match["score"]
        if "duration" in score:
#            print score["duration"]
            if score["duration"] < 10:
                match["score_value"] = match["score_value"] + ((12 - score["duration"]) / 4.0)
            else:
                match["score_value"] = match["score_value"] - score["duration"] / 8.0
        else:
            match["score_value"] = match["score_value"] - 0.5
    matches = sorted(matches, key=lambda match: match["score_value"], reverse=True)
    for match in matches:
        score = match["score"]
#        print "%f - (p: %f t: %f y: %f r: %f d: %f) %s %s" % (match["score_value"], score["position"], score["type"], score["year"], score["ratio"], score["distance"], match["title"], match["id"])
    pp = pprint.PrettyPrinter()
    if len(matches) == 0 or matches[0]["score_value"] < 1.5:
         fuzz = " ".join(title.split()[:-1])
         if len(fuzz) > 0 and not fuzz == title:
             return search(fuzz, year, dur)
         elif year is not None:
             return search(title, None, dur)
         else:
             if matches[0]["score_value"] < 1.4:
                 return None
             else:
                 return matches[0]
    return matches[0]

def get_files(n):
    base = '/mnt/pub/movies'
    fs = []
    for f in os.listdir(os.path.join(base, n)):
        ext = os.path.splitext(f)[1].lower()
        if ext in ['.avi', '.mpg', '.mkv']:
            fs.append(f)
    return sorted(fs)

def get_duration(n):
    base = '/mnt/pub/movies'
    mc = memcache.Client(['127.0.0.1:11211'], debug=0)
    key = escape_generic(n)
    d = mc.get(key)
    if d is not None:
        return d
    else:
        d = 0
    for f in get_files(n):
        info = MediaInfo.parse(os.path.join(base, n, f))
        for track in info.tracks:
            if getattr(track, 'duration') is not None:
                d = d + track.duration
                break
    mc.set(key, d)
    return d
            
if __name__ == "__main__":
    couch = couchdb.Server()
    if not 'bliss' in couch:
        db = couch.create('bliss')
    else:
        db = couch['bliss']
    base = '/mnt/pub/movies'
    for name in os.listdir(base):
        if os.path.isdir(os.path.join(base, name)):
            o = name
            if not o in db:
                d = get_duration(name)
                name, year = parse_name(name)
                m = search(name, year, d)
                if m is None:
                    print "FAIL | %s | FAIL" % (o)
                else:
                    data = {"_id": o,
                            "imdbid": m["id"],
                            "title": m["title"],
                            "files": {}}
                    for f in get_files(o):
                        data["files"][f] = []
                        print os.path.join(base, o, f)
                        info = MediaInfo.parse(os.path.join(base, o, f))
                        for track in info.tracks:
                            d = {}
                            for k, v in track.__dict__.iteritems():
                                if not type(v) == types.InstanceType:
                                    d[k] = v
                            data["files"][f].append(d)
                    db.save(data)
                    print "%s | %s | %s" % (m['id'], o, m['title'])
                    print
