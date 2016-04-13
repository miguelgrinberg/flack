#!/usr/bin/env python
import binascii
import os
import threading
import time

from flask import Flask, render_template, url_for as _url_for, request, \
    _request_ctx_stack, current_app, abort, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash
from markdown import markdown
import bleach
from bs4 import BeautifulSoup
import requests


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


def timestamp():
    """Return the current timestamp as an integer."""
    return int(time.time())


def url_for(*args, **kwargs):
    """
    url_for replacement that works even when there is no request context.
    """
    if '_external' not in kwargs:
        kwargs['_external'] = False
    reqctx = _request_ctx_stack.top
    if reqctx is None:
        if kwargs['_external']:
            raise RuntimeError('Cannot generate external URLs without a '
                               'request context.')
        with current_app.test_request_context():
            return _url_for(*args, **kwargs)
    return _url_for(*args, **kwargs)


class User(db.Model):
    """The User model."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.Integer, default=timestamp)
    updated_at = db.Column(db.Integer, default=timestamp, onupdate=timestamp)
    last_seen_at = db.Column(db.Integer, default=timestamp)
    nickname = db.Column(db.String(32), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    token = db.Column(db.String(64), nullable=True, unique=True)
    online = db.Column(db.Boolean, default=False)
    messages = db.relationship('Message', lazy='dynamic', backref='user')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        self.token = None  # if user is changing passwords, also revoke token

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_token(self):
        """Creates a 64 character long randomly generated token."""
        self.token = binascii.hexlify(os.urandom(32)).decode('utf-8')
        return self.token

    def ping(self):
        """Marks the user as recently seen and online."""
        self.last_seen_at = timestamp()
        self.online = True

    @staticmethod
    def create(data):
        """Create a new user."""
        user = User()
        user.from_dict(data, partial_update=False)
        return user

    def from_dict(self, data, partial_update=True):
        """Import user data from a dictionary."""
        for field in ['nickname', 'password']:
            try:
                setattr(self, field, data[field])
            except KeyError:
                if not partial_update:
                    abort(400)

    def to_dict(self):
        """Export user to a dictionary."""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'nickname': self.nickname,
            'last_seen_at': self.last_seen_at,
            'online': self.online,
            '_links': {
                'self': url_for('get_user', id=self.id),
                'messages': url_for('get_messages', user_id=self.id),
                'tokens': url_for('new_token')
            }
        }

    @staticmethod
    def find_offline_users():
        """Find users that haven't been active and mark them as offline."""
        users = User.query.filter(User.last_seen_at < timestamp() - 60,
                                  User.online == True).all()  # noqa
        for user in users:
            user.online = False
            db.session.add(user)
        db.session.commit()


class Message(db.Model):
    """The Message model."""
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.Integer, default=timestamp)
    updated_at = db.Column(db.Integer, default=timestamp, onupdate=timestamp)
    source = db.Column(db.Text, nullable=False)
    html = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    @staticmethod
    def create(data, user=None):
        """Create a new message. The user is obtained from the context unless
        provided explicitly.
        """
        msg = Message(user=user or g.current_user)
        msg.from_dict(data, partial_update=False)
        return msg

    def from_dict(self, data, partial_update=True):
        """Import message data from a dictionary."""
        for field in ['source']:
            try:
                setattr(self, field, data[field])
            except KeyError:
                if not partial_update:
                    abort(400)

    def to_dict(self):
        """Export message to a dictionary."""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'source': self.source,
            'html': self.html,
            'user_id': self.user.id,
            '_links': {
                'self': url_for('get_message', id=self.id),
                'user': url_for('get_user', id=self.user.id)
            }
        }

    def render_markdown(self, source):
        """Render markdown source to HTML with a tag whitelist."""
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i',
                        'strong']
        self.html = bleach.linkify(bleach.clean(
            markdown(source, output_format='html'),
            tags=allowed_tags, strip=True))

    def expand_links(self):
        """Expand any links referenced in the message."""
        if '<blockquote>' in self.html:
            # links have been already expanded
            return False
        changed = False
        for link in BeautifulSoup(self.html, 'html5lib').select('a'):
            url = link.get('href', '')
            try:
                rv = requests.get(url)
            except requests.exceptions.ConnectionError:
                continue
            if rv.status_code == 200:
                soup = BeautifulSoup(rv.text, 'html5lib')
                title_tags = soup.select('title')
                if len(title_tags) > 0:
                    title = title_tags[0].string.strip()
                else:
                    title = url
                description = 'No description found.'
                for meta in soup.select('meta'):
                    if meta.get('name', '').lower() == 'description':
                        description = meta.get('content', description).strip()
                        break
                # add the detail of the link to the rendered message
                tpl = ('<blockquote><p><a href="{url}">{title}</a></p>'
                       '<p>{desc}</p></blockquote>')
                self.html += tpl.format(url=url, title=title, desc=description)
                changed = True
        return changed

    @staticmethod
    def on_changed_source(target, value, oldvalue, initiator):
        """SQLAlchemy event that automatically renders the message to HTML."""
        target.render_markdown(value)
        target.expand_links()

db.event.listen(Message.source, 'set', Message.on_changed_source)


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
