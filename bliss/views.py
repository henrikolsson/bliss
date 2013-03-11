from datetime import datetime, date
import memcache
import select
import os
import fcntl
import subprocess
import time
import shlex
import traceback
import couchdb
from pymediainfo import MediaInfo
from flask import Flask, Response, render_template, request, g, redirect, url_for, send_file
from bliss import app
import logging
from bliss.video import transcode
from bliss.client import post_json
import urllib
from markupsafe import Markup
import mimetypes
import re
import bliss.config as config

logger = logging.getLogger('bliss.views')

@app.after_request
def after_request(response):
    response.headers.add('Accept-Ranges', 'bytes')
    return response


def send_file_partial(path):
    """ 
        Simple wrapper around send_file which handles HTTP 206 Partial Content
        (byte ranges)
        TODO: handle all send_file args, mirror send_file's error handling
        (if it has any)
    """
    range_header = request.headers.get('Range', None)
    if not range_header: return send_file(path)
    logger.info("Range: %s" % range_header)
    size = os.path.getsize(path)    
    byte1, byte2 = 0, None
    
    m = re.search('(\d+)-(\d*)', range_header)
    g = m.groups()
    
    if g[0]: byte1 = int(g[0])
    if g[1]: byte2 = int(g[1])

    length = size - byte1
    if byte2 is not None:
        length = byte2 - byte1
    
    data = None
    with open(path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)

    rv = Response(data, 
        206,
        mimetype=mimetypes.guess_type(path)[0], 
        direct_passthrough=True)
    rv.headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(byte1, byte1 + length - 1, size))

    return rv

def after_this_request(f):
    if not hasattr(g, 'after_request_callbacks'):
        g.after_request_callbacks = []
    g.after_request_callbacks.append(f)
    return f

@app.after_request
def per_request_callbacks(response):
    for func in getattr(g, 'after_request_callbacks', ()):
        func(response)
    return response

@app.template_filter('urlencode')
def urlencode_filter(s):
    if type(s) == 'Markup':
        s = s.unescape()
    s = s.encode('utf8')
    s = urllib.quote(s)
    return Markup(s)

@app.template_filter('ts2date')
def urlencode_ts2date(s):
    return Markup(datetime.fromtimestamp(int(s)).strftime("%a, %d %b %H:%M"))

@app.before_request
def handle_settings():
    h264_compatability = None
    if request.cookies.get('h264_compatability') is not None:
        h264_compatability = request.cookies.get('h264_compatability') == "True"
    bitrate = request.cookies.get('bitrate')
    if h264_compatability is None:
        h264_compatability = False
        @after_this_request
        def remember_h264_compatability(response):
            response.set_cookie('h264_compatability', h264_compatability)
    if bitrate is None:
        bitrate = 400
        @after_this_request
        def remember_settings(response):
            response.set_cookie('bitrate', bitrate)
    else:
        bitrate = int(bitrate)
    g.h264_compatability = h264_compatability
    g.bitrate = bitrate

@app.route("/save", methods=['POST'])
def save():
    g.h264_compatability = "h264_compatability" in request.form
    g.bitrate = request.form["bitrate"]
    @after_this_request
    def remember_settings(response):
            response.set_cookie('h264_compatability', g.h264_compatability)
            response.set_cookie('bitrate', g.bitrate)
    return redirect(url_for('index'))

@app.route("/")
def index():
    return render_template("index.html", h264_compatability=g.h264_compatability, bitrate=g.bitrate)

@app.route("/tv")
def tv():
    epg = post_json("http://192.168.70.3:9981/epg", {"start": "0", "limit": 300})
    return render_template("tv.html", entries=epg["entries"])

@app.route("/channel/<int:channel>")
def channel(channel):
    return render_template("channel.html", channel=channel)

@app.route("/movies")
def movies():
    result = config.db.view('_design/movie/_view/all')
    return render_template("movies.html", movies=list(result))

@app.route("/player/<type>/<playid>")
def player(type, playid):
    return render_template("player.html", type=type, id=playid)

@app.route("/poster/<movieid>")
def poster(movieid):
    poster = config.db.get_attachment(movieid, "poster")
    if poster is None:
        poster = open(os.path.join(os.path.dirname(__file__), "static", "img", "question.png"), "r")
    return poster.read()

@app.route("/movie/<movieid>")
def movie(movieid):
    movie = config.db[movieid]
    width = 320
    height = 240
    for fn in movie["files"]:
        for track in movie["files"][fn]:
            if "width" in track:
                width = track["width"]
            if "height" in track:
                height = track["height"]
    return render_template("movie.html", movie=movie, width=width, height=height)

@app.route("/video/<type>/<playid>/<format>")
def video_movie(type, playid, format):
    if (type == "movie"):
        doc = config.db[playid]
        sources = map(lambda f: '/mnt/pub/movies/%s/%s' % (playid, f), sorted(doc['files'].keys()))
        return transcode(sources, format, g.bitrate, g.h264_compatability)
    elif (type == "tv"):
        return transcode(['http://chani:9981/stream/channelid/%d' % int(playid)], format, g.bitrate, g.h264_compatability)
    else:
        raise Exception("Unhandled type: %s" % type)
