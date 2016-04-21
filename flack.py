#!/usr/bin/env python
import os
import threading
import time

from flask import Flask, render_template, request, abort, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
from flask_bootstrap import Bootstrap

from utils import timestamp, url_for

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = '51f52814-0071-11e6-a247-000ec6c2372c'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'db.sqlite'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask extensions
db = SQLAlchemy(app)
Bootstrap(app)

# Authentication objects for username/password auth, token auth, and a
# token optional auth that is used for open endpoints.
basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth('Bearer')
token_optional_auth = HTTPTokenAuth('Bearer')

# We use a list to calculate requests per second
request_stats = []

# Import models so that they are registered with SQLAlchemy
from models import User, Message


@basic_auth.verify_password
def verify_password(nickname, password):
    """Password verification callback."""
    if not nickname or not password:
        return False
    user = User.query.filter_by(nickname=nickname).first()
    if user is None or not user.verify_password(password):
        return False
    user.ping()
    db.session.add(user)
    db.session.commit()
    g.current_user = user
    return True


@basic_auth.error_handler
def password_error():
    """Return a 401 error to the client."""
    # To avoid login prompts in the browser, use the "Bearer" realm.
    return (jsonify({'error': 'authentication required'}), 401,
            {'WWW-Authenticate': 'Bearer realm="Authentication Required"'})


@token_auth.verify_token
def verify_token(token):
    """Token verification callback."""
    user = User.query.filter_by(token=token).first()
    if user is None:
        return False
    user.ping()
    db.session.add(user)
    db.session.commit()
    g.current_user = user
    return True


@token_auth.error_handler
def token_error():
    """Return a 401 error to the client."""
    return (jsonify({'error': 'authentication required'}), 401,
            {'WWW-Authenticate': 'Bearer realm="Authentication Required"'})


@token_optional_auth.verify_token
def verify_optional_token(token):
    """Alternative token authentication that allows anonymous logins."""
    if token == '':
        # no token provided, mark the logged in users as None and continue
        g.current_user = None
        return True
    # but if a token was provided, make sure it is valid
    return verify_token(token)


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


@app.route('/api/users', methods=['POST'])
def new_user():
    """
    Register a new user.
    This endpoint is publicly available.
    """
    user = User.create(request.get_json() or {})
    if User.query.filter_by(nickname=user.nickname).first() is not None:
        abort(400)
    db.session.add(user)
    db.session.commit()
    r = jsonify(user.to_dict())
    r.status_code = 201
    r.headers['Location'] = url_for('get_user', id=user.id)
    return r


@app.route('/api/users', methods=['GET'])
@token_optional_auth.login_required
def get_users():
    """
    Return list of users.
    This endpoint is publicly available, but if the client has a token it
    should send it, as that indicates to the server that the user is online.
    """
    users = User.query.order_by(User.updated_at.asc(), User.nickname.asc())
    if request.args.get('online'):
        users = users.filter_by(online=(request.args.get('online') != '0'))
    if request.args.get('updated_since'):
        users = users.filter(
            User.updated_at > int(request.args.get('updated_since')))
    return jsonify({'users': [user.to_dict() for user in users.all()]})


@app.route('/api/users/<id>', methods=['GET'])
@token_optional_auth.login_required
def get_user(id):
    """
    Return a user.
    This endpoint is publicly available, but if the client has a token it
    should send it, as that indicates to the server that the user is online.
    """
    return jsonify(User.query.get_or_404(id).to_dict())


@app.route('/api/users/<id>', methods=['PUT'])
@token_auth.login_required
def edit_user(id):
    """
    Modify an existing user.
    This endpoint is requires a valid user token.
    Note: users are only allowed to modify themselves.
    """
    user = User.query.get_or_404(id)
    if user != g.current_user:
        abort(403)
    user.from_dict(request.get_json() or {})
    db.session.add(user)
    db.session.commit()
    return '', 204


@app.route('/api/tokens', methods=['POST'])
@basic_auth.login_required
def new_token():
    """
    Request a user token.
    This endpoint is requires basic auth with nickname and password.
    """
    if g.current_user.token is None:
        g.current_user.generate_token()
        db.session.add(g.current_user)
        db.session.commit()
    return jsonify({'token': g.current_user.token})


@app.route('/api/tokens', methods=['DELETE'])
@token_auth.login_required
def revoke_token():
    """
    Revoke a user token.
    This endpoint is requires a valid user token.
    """
    g.current_user.token = None
    db.session.add(g.current_user)
    db.session.commit()
    return '', 204


@app.route('/api/messages', methods=['POST'])
@token_auth.login_required
def new_message():
    """
    Post a new message.
    This endpoint is requires a valid user token.
    """
    msg = Message.create(request.get_json() or {})
    db.session.add(msg)
    db.session.commit()
    r = jsonify(msg.to_dict())
    r.status_code = 201
    r.headers['Location'] = url_for('get_message', id=msg.id)
    return r


@app.route('/api/messages', methods=['GET'])
@token_optional_auth.login_required
def get_messages():
    """
    Return list of messages.
    This endpoint is publicly available, but if the client has a token it
    should send it, as that indicates to the server that the user is online.
    """
    since = int(request.args.get('updated_since', '0'))
    day_ago = timestamp() - 24 * 60 * 60
    if since < day_ago:
        # do not return more than a day worth of messages
        since = day_ago
    msgs = Message.query.filter(Message.updated_at > since).order_by(
        Message.updated_at)
    return jsonify({'messages': [msg.to_dict() for msg in msgs.all()]})


@app.route('/api/messages/<id>', methods=['GET'])
@token_optional_auth.login_required
def get_message(id):
    """
    Return a message.
    This endpoint is publicly available, but if the client has a token it
    should send it, as that indicates to the server that the user is online.
    """
    return jsonify(Message.query.get_or_404(id).to_dict())


@app.route('/api/messages/<id>', methods=['PUT'])
@token_auth.login_required
def edit_message(id):
    """
    Modify an existing message.
    This endpoint is requires a valid user token.
    Note: users are only allowed to modify their own messages.
    """
    msg = Message.query.get_or_404(id)
    if msg.user != g.current_user:
        abort(403)
    msg.from_dict(request.get_json() or {})
    db.session.add(msg)
    db.session.commit()
    return '', 204


@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({'requests_per_second': len(request_stats) / 15})


if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', debug=True)
