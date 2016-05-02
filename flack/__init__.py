import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from celery import Celery

from config import config

# Flask extensions
db = SQLAlchemy()
bootstrap = Bootstrap()
celery = Celery(__name__,
                broker=os.environ.get('CELERY_BROKER_URL', 'redis://'),
                backend=os.environ.get('CELERY_BROKER_URL', 'redis://'))
celery.config_from_object('celeryconfig')

# Import models so that they are registered with SQLAlchemy
from . import models  # noqa

# Import celery task so that it is registered with the Celery workers
from .tasks import run_flask_request  # noqa


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLACK_CONFIG', 'development')
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize flask extensions
    db.init_app(app)
    bootstrap.init_app(app)
    celery.conf.update(config[config_name].CELERY_CONFIG)

    # Register web application routes
    from .flack import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Register API routes
    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    # Register async tasks support
    from .tasks import tasks_bp as tasks_blueprint
    app.register_blueprint(tasks_blueprint, url_prefix='/tasks')

    return app
