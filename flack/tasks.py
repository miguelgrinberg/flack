from functools import wraps
import threading
import time
import uuid

from flask import Blueprint, abort, current_app, g, request
from werkzeug.exceptions import HTTPException, InternalServerError

from . import db
from .models import User
from .utils import timestamp, url_for

tasks_bp = Blueprint('tasks', __name__)
tasks = {}


@tasks_bp.before_app_first_request
def before_first_request():
    """Start a background thread that cleans up old tasks."""
    def clean_old_tasks():
        """
        This function cleans up old tasks from our in-memory data structure.
        """
        global tasks
        while True:
            # Only keep tasks that are running or that finished less than 5
            # minutes ago.
            five_min_ago = timestamp() - 5 * 60
            tasks = {id: task for id, task in tasks.items()
                     if 't' not in task or task['t'] > five_min_ago}
            time.sleep(60)

    if not current_app.config['TESTING']:
        thread = threading.Thread(target=clean_old_tasks)
        thread.start()


def async(f):
    """
    This decorator transforms a sync route to asynchronous by running it
    in a background thread.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        def task(app, environ, current_user_nickname):
            # Create a request context similar to that of the original request
            # so that the task can have access to flask.g, flask.request, etc.
            with app.request_context(environ):
                # Install the current user in the thread's flask.g
                current_user = User.query.filter_by(
                    nickname=current_user_nickname).first()
                if current_user is None:
                    raise RuntimeError('Invalid user.')
                g.current_user = current_user
                try:
                    # Run the route function and record the response
                    tasks[id]['rv'] = f(*args, **kwargs)
                except HTTPException as e:
                    tasks[id]['rv'] = current_app.handle_http_exception(e)
                except Exception as e:
                    # The function raised an exception, so we set a 500 error
                    tasks[id]['rv'] = InternalServerError()
                    if current_app.debug:
                        # We want to find out if something happened so reraise
                        raise
                finally:
                    # We record the time of the response, to help in garbage
                    # collecting old tasks
                    tasks[id]['t'] = timestamp()

                    # close the database session
                    db.session.remove()

        # Assign an id to the asynchronous task
        id = uuid.uuid4().hex

        # Record the task, and then launch it
        tasks[id] = {'task': threading.Thread(
            target=task, args=(current_app._get_current_object(),
                               request.environ, g.current_user.nickname))}
        tasks[id]['task'].start()

        # Return a 202 response, with a link that the client can use to
        # obtain task status
        return '', 202, {'Location': url_for('tasks.get_status', id=id)}
    return wrapped


@tasks_bp.route('/status/<id>', methods=['GET'])
def get_status(id):
    """
    Return status about an asynchronous task. If this request returns a 202
    status code, it means that task hasn't finished yet. Else, the response
    from the task is returned.
    """
    task = tasks.get(id)
    if task is None:
        abort(404)
    if 'rv' not in task:
        return '', 202, {'Location': url_for('tasks.get_status', id=id)}
    return task['rv']
