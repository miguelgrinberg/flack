import binascii
import os

from flask import abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from markdown import markdown
import bleach
from bs4 import BeautifulSoup
import requests

from . import db
from .utils import timestamp, url_for


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
        last_online = self.online
        self.online = True
        return last_online != self.online

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
                'self': url_for('api.get_user', id=self.id),
                'messages': url_for('api.get_messages', user_id=self.id),
                'tokens': url_for('api.new_token')
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
        return users


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
    def create(data, user=None, expand_links=True):
        """Create a new message. The user is obtained from the context unless
        provided explicitly.
        """
        msg = Message(user=user or g.current_user)
        msg.from_dict(data, partial_update=False)
        if expand_links:
            msg.expand_links()
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
                'self': url_for('api.get_message', id=self.id),
                'user': url_for('api.get_user', id=self.user.id)
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

db.event.listen(Message.source, 'set', Message.on_changed_source)
