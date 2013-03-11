import logging
import couchdb

fh = logging.FileHandler('bliss.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logging.getLogger('').addHandler(fh)
logging.getLogger('').addHandler(ch)
logging.getLogger('').setLevel(logging.DEBUG)
logging.getLogger('apiclient').setLevel(logging.WARN)

DEBUG = True
DB = "bliss"
BASEDIR = '/mnt/pub/movies'
RT_KEY = 'X'
FB_KEY = 'Y'

couch = couchdb.Server()
if not DB in couch:
    db = couch.create(DB)
    movie_views = {
        "_id":"_design/movie",
        "language": "python",
        "views":
            {
            "all": {
                "map": """def fun(doc):
    if doc['type'] == 'movie':
        yield doc['_id'], doc"""
                }
            }
        }
    db.save(movie_views)
else:
    db = couch[DB]
