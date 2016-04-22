from flask import Blueprint

api = Blueprint('api', __name__)

from . import tokens, users, messages  # noqa
