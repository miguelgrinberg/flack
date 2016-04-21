#!/usr/bin/env python
from flask_script import Manager

from flack import app, db

manager = Manager(app)


@manager.command
def createdb(drop_first=False):
    """Creates the database."""
    if drop_first:
        db.drop_all()
    db.create_all()


if __name__ == '__main__':
    manager.run()
