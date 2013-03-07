import select
import os
import fcntl
import subprocess
import time
import shlex
import traceback
from flask import Response
import logging

logger = logging.getLogger('bliss.video')

def transcode(source, output, bitrate, baseline):
    def generate():
        ffmpeg = None
        try: 
            if output == "webm":
                c = "-codec:v libvpx -quality good -cpu-used 0 -b:v %dk -qmin 10 -qmax 42 -maxrate %dk -bufsize 1000k -threads 0 -codec:a libvorbis -b:a 128k -f webm" % (bitrate, bitrate)
            elif output == "mp4":
                c = "-c:v libx264 -crf 23 -maxrate %dk -bufsize 1835k -c:a libfaac -f mp4 -movflags frag_keyframe+empty_moov" % bitrate
                if baseline:
                    c = c + " -profile:v baseline"
            else:
                raise Exception("Don't know how to handle output: %s" % output)
            cmd = ("/usr/bin/ffmpeg -i '%s' "
                   #"-c:v libx264 "
                   #"-crf 20 "
                   #"-maxrate 400k "
                   #"-bufsize 1835k "
                   #"-c:a libfaac "
                   #"-vcodec libx264 -vprofile high -preset slow -b:v 500k -maxrate 500k -bufsize 1000k -vf scale=-1:480 -threads 0 -acodec libfaac -b:a 128k  -s 320x240 "
                   #"-f mp4 "
                   #"-codec:v libvpx -quality good -cpu-used 0 -b:v 500k -qmin 10 -qmax 42 -maxrate 500k -bufsize 1000k -threads 4 -codec:a libvorbis -b:a 128k -f webm "
                   '%s '
                   "-" % (source, c))
            logger.debug("cmd: %s" % cmd)
            ffmpeg = subprocess.Popen(shlex.split(cmd), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            out = ffmpeg.stdout.fileno()
            err = ffmpeg.stderr.fileno()
            set_nonblock(out)
            set_nonblock(err)

            while True:
                ready = select.select([out, err], [], [out, err])
                rlist = ready[0]
                if len(ready[2]) > 0:
                    raise Exception("Exceptional condition happened")
                    return
                if out in rlist:
                    yield ffmpeg.stdout.read()
                if err in rlist:
                    r = ffmpeg.stderr.read()
                    if len(r) == 0:
                        raise Exception("ffmpeg died")
                    print r
                time.sleep(.1)
        except:
            logger.exception("Something died")
            if ffmpeg is not None:
                ffmpeg.terminate()
    if output == "webm":
        mime = "video/webm"
    elif output == "mp4":
        mime = "video/mp4"
    return Response(generate(), mimetype=mime)
    
def set_nonblock(fd):
     fcntl.fcntl(fd,
                 fcntl.F_SETFL,
                 fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)    
