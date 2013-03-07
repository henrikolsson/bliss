import logging

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

DEBUG = True
DB = "bliss"
