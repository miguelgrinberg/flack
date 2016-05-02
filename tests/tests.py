import base64
import json
import time
import unittest
import mock

import requests

from flack import create_app, db
from flack.models import User
from flack.tasks import async


class FlackTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')

        # add an additional route used only in tests
        @self.app.route('/foo')
        @async
        def foo():
            1 / 0

        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()  # just in case
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def get_headers(self, basic_auth=None, token_auth=None):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        if basic_auth is not None:
            headers['Authorization'] = 'Basic ' + base64.b64encode(
                basic_auth.encode('utf-8')).decode('utf-8')
        if token_auth is not None:
            headers['Authorization'] = 'Bearer ' + token_auth
        return headers

    def get(self, url, basic_auth=None, token_auth=None):
        rv = self.client.get(url,
                             headers=self.get_headers(basic_auth, token_auth))
        # clean up the database session, since this only occurs when the app
        # context is popped.
        db.session.remove()
        body = rv.get_data(as_text=True)
        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass
        return body, rv.status_code, rv.headers

    def post(self, url, data=None, basic_auth=None, token_auth=None):
        d = data if data is None else json.dumps(data)
        rv = self.client.post(url, data=d,
                              headers=self.get_headers(basic_auth, token_auth))
        # clean up the database session, since this only occurs when the app
        # context is popped.
        db.session.remove()
        body = rv.get_data(as_text=True)
        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass
        return body, rv.status_code, rv.headers

    def put(self, url, data=None, basic_auth=None, token_auth=None):
        d = data if data is None else json.dumps(data)
        rv = self.client.put(url, data=d,
                             headers=self.get_headers(basic_auth, token_auth))
        # clean up the database session, since this only occurs when the app
        # context is popped.
        db.session.remove()
        body = rv.get_data(as_text=True)
        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass
        return body, rv.status_code, rv.headers

    def delete(self, url, basic_auth=None, token_auth=None):
        rv = self.client.delete(url, headers=self.get_headers(basic_auth,
                                                              token_auth))
        # clean up the database session, since this only occurs when the app
        # context is popped.
        db.session.remove()
        body = rv.get_data(as_text=True)
        if body is not None and body != '':
            try:
                body = json.loads(body)
            except:
                pass
        return body, rv.status_code, rv.headers

    def test_user(self):
        # get users without auth
        r, s, h = self.get('/api/users')
        self.assertEqual(s, 200)

        # get users with bad auth
        r, s, h = self.get('/api/users', token_auth='bad-token')
        self.assertEqual(s, 401)

        # create a new user
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'bar'})
        self.assertEqual(s, 201)
        url = h['Location']

        # create a duplicate user
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'baz'})
        self.assertEqual(s, 400)

        # create an incomplete user
        r, s, h = self.post('/api/users', data={'nickname': 'foo1'})
        self.assertEqual(s, 400)

        # request a token
        r, s, h = self.post('/api/tokens', basic_auth='foo:bar')
        self.assertEqual(s, 200)
        token = r['token']

        # request a token with wrong password
        r, s, h = self.post('/api/tokens', basic_auth='foo:baz')
        self.assertEqual(s, 401)

        # use token to get user
        r, s, h = self.get(url, token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(r['nickname'], 'foo')
        self.assertEqual('http://localhost' + r['_links']['self'], url)
        self.assertEqual(r['_links']['tokens'], '/api/tokens')

        # modify nickname
        r, s, h = self.put(url, data={'nickname': 'foo2'}, token_auth=token)
        self.assertEqual(s, 204)

        # create second user
        r, s, h = self.post('/api/users', data={'nickname': 'bar',
                                                'password': 'baz'})
        self.assertEqual(s, 201)
        url2 = h['Location']

        # edit second user with first user token
        r, s, h = self.put(url2, data={'nickname': 'bar2'}, token_auth=token)
        self.assertEqual(s, 403)

        # check new nickname
        r, s, h = self.get(url, token_auth=token)
        self.assertEqual(r['nickname'], 'foo2')

        # get list of users
        r, s, h = self.get('/api/users', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 2)

        # revoke token
        self.delete('/api/tokens', token_auth=token)

        # use invalid token
        r, s, h = self.get(url, token_auth=token)
        self.assertEqual(s, 401)
        r, s, h = self.put(url, data={'nickname': 'foo3'}, token_auth=token)
        self.assertEqual(s, 401)

    def test_user_online_offline(self):
        # create a couple of users and a token
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'foo'})
        self.assertEqual(s, 201)
        r, s, h = self.post('/api/users', data={'nickname': 'bar',
                                                'password': 'bar'})
        self.assertEqual(s, 201)
        r, s, h = self.post('/api/tokens', basic_auth='foo:foo')
        self.assertEqual(s, 200)
        token = r['token']

        # update online status
        User.find_offline_users()

        # get list of offline users
        r, s, h = self.get('/api/users?online=0', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'bar')

        # get list of online users
        r, s, h = self.get('/api/users?online=1', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'foo')

        # alter last seen time of the two users
        user = User.query.filter_by(nickname='foo').first()
        user.last_seen_at = int(time.time()) - 65
        db.session.add(user)
        user = User.query.filter_by(nickname='bar').first()
        user.last_seen_at = int(time.time()) - 1000
        db.session.add(user)
        db.session.commit()

        # update online status
        User.find_offline_users()

        # get list of offline users
        r, s, h = self.get('/api/users?online=0', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'bar')

        # get list of online users (only foo, who owns the token)
        r, s, h = self.get('/api/users?online=1', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'foo')

        # get users updated since a timestamp
        since = r['users'][0]['updated_at']
        with mock.patch('flack.utils.time.time', return_value=since + 10):
            r, s, h = self.get('/api/users?updated_since=' + str(since),
                               token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 1)
        self.assertEqual(r['users'][0]['nickname'], 'foo')

        # update the other user
        user = User.query.filter_by(nickname='bar').first()
        user.password = 'bar2'
        db.session.add(user)
        db.session.commit()

        # get updated users again
        with mock.patch('flack.utils.time.time', return_value=since + 10):
            r, s, h = self.get('/api/users?updated_since=' + str(since - 1),
                               token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['users']), 2)
        self.assertEqual(r['users'][0]['nickname'], 'bar')
        self.assertEqual(r['users'][1]['nickname'], 'foo')

    def test_message(self):
        # create a user and a token
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'bar'})
        self.assertEqual(s, 201)
        r, s, h = self.post('/api/tokens', basic_auth='foo:bar')
        self.assertEqual(s, 200)
        token = r['token']

        # create a message
        r, s, h = self.post('/api/messages', data={'source': 'hello *world*!'},
                            token_auth=token)
        self.assertEqual(s, 201)
        url = h['Location']

        # create incomplete message
        r, s, h = self.post('/api/messages', data={'foo': 'hello *world*!'},
                            token_auth=token)
        self.assertEqual(s, 400)

        # get message
        r, s, h = self.get(url, token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(r['source'], 'hello *world*!')
        self.assertEqual(r['html'], 'hello <em>world</em>!')

        # modify message
        r, s, h = self.put(url, data={'source': '*hello* world!'},
                           token_auth=token)
        self.assertEqual(s, 204)

        # check modified message
        r, s, h = self.get(url, token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(r['source'], '*hello* world!')
        self.assertEqual(r['html'], '<em>hello</em> world!')

        # create a new message
        with mock.patch('flack.utils.time.time',
                        return_value=int(time.time()) + 5):
            r, s, h = self.post('/api/messages',
                                data={'source': 'bye *world*!'},
                                token_auth=token)
        self.assertEqual(s, 201)

        # get list of messages
        r, s, h = self.get('/api/messages', token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['messages']), 2)
        self.assertEqual(r['messages'][0]['source'], '*hello* world!')
        self.assertEqual(r['messages'][1]['source'], 'bye *world*!')

        # get list of messages since
        r, s, h = self.get(
            '/api/messages?updated_since=' + str(int(time.time())),
            token_auth=token)
        self.assertEqual(s, 200)
        self.assertEqual(len(r['messages']), 1)
        self.assertEqual(r['messages'][0]['source'], 'bye *world*!')

        # create a second user and token
        r, s, h = self.post('/api/users', data={'nickname': 'bar',
                                                'password': 'baz'})
        self.assertEqual(s, 201)
        r, s, h = self.post('/api/tokens', basic_auth='bar:baz')
        self.assertEqual(s, 200)
        token2 = r['token']

        # modify message from first user with second user's token
        r, s, h = self.put(url, data={'source': '*hello* world!'},
                           token_auth=token2)
        self.assertEqual(s, 403)

        def responses():
            rv = requests.Response()
            rv.status_code = 200
            rv.encoding = 'utf-8'
            rv._content = (b'<html><head><title>foo</title>'
                           b'<meta name="blah" content="blah">'
                           b'<meta name="description" content="foo descr">'
                           b'</head></html>')
            yield rv
            rv = requests.Response()
            rv.status_code = 200
            rv.encoding = 'utf-8'
            rv._content = b'<html><head><title>bar</title></head></html>'
            yield rv
            rv = requests.Response()
            rv.status_code = 200
            rv.encoding = 'utf-8'
            rv._content = (b'<html><head>'
                           b'<meta name="description" content="baz descr">'
                           b'</head></html>')
            yield rv
            yield requests.exceptions.ConnectionError()

        with mock.patch('flack.models.requests.get', side_effect=responses()):
            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello http://foo.com!'},
                token_auth=token)
            self.assertEqual(s, 201)

            self.assertEqual(
                r['html'],
                'hello <a href="http://foo.com" rel="nofollow">'
                'http://foo.com</a>!<blockquote><p><a href="http://foo.com">'
                'foo</a></p><p>foo descr</p></blockquote>')

            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello http://foo.com!'},
                token_auth=token)
            self.assertEqual(s, 201)

            self.assertEqual(
                r['html'],
                'hello <a href="http://foo.com" rel="nofollow">'
                'http://foo.com</a>!<blockquote><p><a href="http://foo.com">'
                'bar</a></p><p>No description found.</p></blockquote>')

            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello foo.com!'},
                token_auth=token)
            self.assertEqual(s, 201)

            self.assertEqual(
                r['html'],
                'hello <a href="http://foo.com" rel="nofollow">'
                'foo.com</a>!<blockquote><p><a href="http://foo.com">'
                'http://foo.com</a></p><p>baz descr</p></blockquote>')

            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello foo.com!'},
                token_auth=token)
            self.assertEqual(s, 201)

            self.assertEqual(
                r['html'],
                'hello <a href="http://foo.com" rel="nofollow">'
                'foo.com</a>!')

    def test_celery(self):
        # create a user and a token
        r, s, h = self.post('/api/users', data={'nickname': 'foo',
                                                'password': 'bar'})
        self.assertEqual(s, 201)
        r, s, h = self.post('/api/tokens', basic_auth='foo:bar')
        self.assertEqual(s, 200)
        token = r['token']

        with mock.patch('flack.tasks.run_flask_request.apply_async',
                        return_value=mock.MagicMock(state='PENDING')) as m:
            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello!'},
                token_auth=token)
            self.assertEqual(s, 202)
            self.assertEqual(m.call_count, 1)
            environ = m.call_args_list[0][1]['args'][0]
            self.assertEqual(environ['_wsgi.input'], b'{"source": "hello!"}')

        with mock.patch('flack.tasks.run_flask_request.apply_async',
                        return_value=mock.MagicMock(state='STARTED')) as m:
            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello!'},
                token_auth=token)
            self.assertEqual(s, 202)
            self.assertEqual(m.call_count, 1)
            environ = m.call_args_list[0][1]['args'][0]
            self.assertEqual(environ['_wsgi.input'], b'{"source": "hello!"}')

        with mock.patch('flack.tasks.run_flask_request.apply_async',
                        return_value=mock.MagicMock(
                            state='SUCCESS',
                            info=('foo', 201, {'a': 'b'}))) as m:
            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello!'},
                token_auth=token)
            self.assertEqual(s, 201)
            self.assertEqual(r, 'foo')
            self.assertIn('a', h)
            self.assertEqual(h['a'], 'b')
            self.assertEqual(m.call_count, 1)
            environ = m.call_args_list[0][1]['args'][0]
            self.assertEqual(environ['_wsgi.input'], b'{"source": "hello!"}')

        with mock.patch('flack.api.messages.jsonify', side_effect=ValueError):
            r, s, h = self.post(
                '/api/messages',
                data={'source': 'hello!'},
                token_auth=token)
            self.assertEqual(s, 500)
