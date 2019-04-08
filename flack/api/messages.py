from flask import request, abort, jsonify, g

from .. import db
from ..auth import token_auth, token_optional_auth
from ..models import Message
from ..utils import timestamp, url_for
from ..tasks import async_task
from . import api


@api.route('/messages', methods=['POST'])
@token_auth.login_required
@async_task
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
    r.headers['Location'] = url_for('api.get_message', id=msg.id)
    return r


@api.route('/messages', methods=['GET'])
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


@api.route('/messages/<id>', methods=['GET'])
@token_optional_auth.login_required
def get_message(id):
    """
    Return a message.
    This endpoint is publicly available, but if the client has a token it
    should send it, as that indicates to the server that the user is online.
    """
    return jsonify(Message.query.get_or_404(id).to_dict())


@api.route('/messages/<id>', methods=['PUT'])
@token_auth.login_required
@async_task
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
