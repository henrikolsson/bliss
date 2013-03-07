from datetime import datetime, date
import select
import os
import fcntl
import subprocess
import time
import shlex
import traceback
import couchdb
from pymediainfo import MediaInfo
from flask import Flask, Response, render_template, request, g, redirect, url_for
from bliss import app
import logging
from bliss.video import transcode
from bliss.client import post_json
import urllib
from markupsafe import Markup

logger = logging.getLogger('bliss.views')

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
    s = urllib.quote_plus(s)
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
        bitrate = 4000
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

@app.route("/video/tv/<int:channel>/<format>")
def video_tv(channel, format):
    return transcode('http://chani:9981/stream/channelid/%d' % channel, format, g.bitrate, g.h264_compatability)

@app.route("/movies")
def movies():
    couch = couchdb.Server()
    if not 'bliss' in couch:
        db = couch.create('bliss')
    else:
        db = couch['bliss']
    return render_template("movies.html", movies=db.__iter__())

@app.route("/movie/<movieid>")
def movie(movieid):
    couch = couchdb.Server()
    if not 'bliss' in couch:
        db = couch.create('bliss')
    else:
        db = couch['bliss']
    movie = db[movieid]
    width = 320
    height = 240
    for fn in movie["files"]:
        for track in movie["files"][fn]:
            if "width" in track:
                width = track["width"]
            if "height" in track:
                height = track["height"]
    return render_template("movie.html", movie=movie, width=width, height=height)

@app.route("/video/movie/<movieid>/<fileid>/<format>")
def video_movie(movieid, fileid, format):
    return transcode('/mnt/pub/movies/%s/%s' % (movieid, fileid), format, g.bitrate, g.h264_compatability)

