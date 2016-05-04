from flask import g, jsonify, session
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth

from . import db
from .models import User


# Authentication objects for username/password auth, token auth, and a
# token optional auth that is used for open endpoints.
basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth('Bearer')
token_optional_auth = HTTPTokenAuth('Bearer')


@basic_auth.verify_password
def verify_password(nickname, password):
    """Password verification callback."""
    if not nickname or not password:
        return False
    user = User.query.filter_by(nickname=nickname).first()
    if user is None or not user.verify_password(password):
        return False
    if user.ping():
        from .events import push_model
        push_model(user)
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
def verify_token(token, add_to_session=False):
    """Token verification callback."""
    if add_to_session:
        # clear the session in case auth fails
        if 'nickname' in session:
            del session['nickname']
    user = User.query.filter_by(token=token).first()
    if user is None:
        return False
    if user.ping():
        from .events import push_model
        push_model(user)
    db.session.add(user)
    db.session.commit()
    g.current_user = user
    if add_to_session:
        session['nickname'] = user.nickname
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
