# Flask At Scale Tutorial at PyCon 2016

This repository contains the companion code to my PyCon 2016 "Flask At Scale"
class.

**IMPORTANT NOTE**: The initial commit in this repository has a version of
this application that has a few scalability problems discussed during class.
These problems are addressed in subsequent commits.

## Installation

All the code and examples were tested on Python 3.5. Older versions of Python
including 2.7 will likely work as well.

As usual, create a virtual environment and install the requirements with pip.

    pip install -r requirements.txt

## Running

The application uses Flask-Script to simplify common tasks such as starting
a development server. To run the application run the following command:

    python manage.py runserver

You can add `--help` to see what other start up options are available.

##  Usage

That application allows multiple users to chat online. You can launch the
application on your browser by typing `http://127.0.0.1:5000` on the address
bar.

Since authentication is not a topic in this class, I've decided to use a 
simplified flow that combines the registration and login forms in one. If you
are a new user, enter your chosen nickname and password to register. If the
nickname was not seen before the server will register you. If you are a
returning user, provide your login in the same form. If the nickname is
registered then the password will be validated.

Once you are logged in you can type messages in the bottom text entry field,
and these messages will be seen by all other users. You can use simple
MarkDown formatting to add style to your messages. If you enter any links as
part of your message, these will be shown in expanded form below the message.
