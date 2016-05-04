from flask import g, session

from . import db, socketio
from .models import User, Message
from .auth import verify_token


def push_model(model):
    """Push the model to all connected Socket.IO clients."""
    socketio.emit('updated_model', {'class': model.__class__.__name__,
                                    'model': model.to_dict()})


@socketio.on('ping_user')
def on_ping_user(token):
    """Clients must send this event periodically to keep the user online."""
    verify_token(token, add_to_session=True)
    if g.current_user:
        # Mark the user as still online
        g.current_user.ping()


@socketio.on('post_message')
def on_post_message(data, token):
    """Clients send this event to when the user posts a message."""
    verify_token(token, add_to_session=True)
    if g.current_user:
        # Write the message to the database
        msg = Message.create(data)
        db.session.add(msg)
        db.session.commit()

        # broadcast the message to all clients
        push_model(msg)


@socketio.on('disconnect')
def on_disconnect():
    """A Socket.IO client has disconnected. If we know who the user is, then
    update our state accordingly.
    """
    nickname = session.get('nickname')
    if nickname:
        # we have the nickname in the session, we can mark the user as offline
        user = User.query.filter_by(nickname=nickname).first()
        if user:
            user.online = False
            db.session.commit()
            push_model(user)
