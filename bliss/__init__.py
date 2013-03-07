import os
from flask import Flask
app = Flask(__name__)
app.config.from_object('bliss.config')
if 'BLISS_SETTINGS' in os.environ:
    app.config.from_envvar('BLISS_SETTINGS')
import bliss.views

