import os
import threading
import time

from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap

from config import config
from .utils import timestamp

app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLACK_CONFIG', 'development')])

# Flask extensions
db = SQLAlchemy(app)
Bootstrap(app)

# We use a list to calculate requests per second
request_stats = []

# Import models so that they are registered with SQLAlchemy
from .models import User, Message  # noqa

# Registed API routes with the application
from .api import api as api_blueprint
app.register_blueprint(api_blueprint, url_prefix='/api')


@app.before_first_request
def before_first_request():
    """Start a background thread that looks for users that leave."""
    def find_offline_users():
        while True:
            User.find_offline_users()
            db.session.remove()
            time.sleep(5)

    if not app.config['TESTING']:
        thread = threading.Thread(target=find_offline_users)
        thread.start()


@app.before_request
def before_request():
    """Update requests per second stats."""
    t = timestamp()
    while len(request_stats) > 0 and request_stats[0] < t - 15:
        del request_stats[0]
    request_stats.append(t)


@app.route('/')
def index():
    """Serve client-side application."""
    return render_template('index.html')


@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({'requests_per_second': len(request_stats) / 15})
