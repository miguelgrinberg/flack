import threading
import time

from flask import Blueprint, render_template, jsonify, current_app

from .models import User
from .events import push_model
from . import db, stats

main = Blueprint('main', __name__)


@main.before_app_first_request
def before_first_request():
    """Start a background thread that looks for users that leave."""
    def find_offline_users(app):
        with app.app_context():
            while True:
                users = User.find_offline_users()
                for user in users:
                    push_model(user)
                db.session.remove()
                time.sleep(5)

    if not current_app.config['TESTING']:
        thread = threading.Thread(target=find_offline_users,
                                  args=(current_app._get_current_object(),))
        thread.start()


@main.before_app_request
def before_request():
    """Update requests per second stats."""
    stats.add_request()


@main.route('/')
def index():
    """Serve client-side application."""
    return render_template('index.html')


@main.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({'requests_per_second': stats.requests_per_second()})
