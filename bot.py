from requests import Session, auth
from json import loads, dump
from stem import Signal
from stem.control import Controller
from random import choice
import jwt
import time
import _config

with open('dev_accounts.json', 'r') as f:
    dev_accounts = loads(f.read())


def _setpixel_payload(coordinates, color, canvas):
    x, y = coordinates
    return {'operationName': 'setPixel',
            'query': "mutation setPixel($input: ActInput!) {\n  act(input: $input) {\n    data {\n      ... on BasicMessage {\n        id\n        data {\n          ... on GetUserCooldownResponseMessageData {\n            nextAvailablePixelTimestamp\n            __typename\n          }\n          ... on SetPixelResponseMessageData {\n            timestamp\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
            'variables': {
                'input': {
                    'PixelMessageData': {'coordinate': {'x': x, 'y': y}, 'colorIndex': color, 'canvasIndex': canvas},
                    'actionName': "r/replace:set_pixel"
                }
            }
            }


def _add_developer_account(name):
    def _write_file(client_id, secret):
        dev_accounts[name] = {"client-id": client_id, "secret": secret}
        with open('dev_accounts.json', 'r') as f:
            accounts = loads(f.read())
        with open('dev_accounts.json', 'w') as f:
            accounts.update({name: {"client-id": client_id, "secret": secret}})
            dump(accounts, f)

    s = _tor_session() if _config.config['tor'] else Session()
    text = s.get('https://www.reddit.com/login').text
    csrf = text[text.find('csrf_token') + 19:text.find('csrf_token') + 59]
    r = s.post('https://www.reddit.com/login',
               data={
                   'username': _config.config['main-dev-account']['username'],
                   'password': _config.config['main-dev-account']['password'],
                   'csrf_token': csrf,
                   'otp': '',
                   'dest': 'https://www.reddit.com'
               }, headers={'content-type': 'application/x-www-form-urlencoded',
                           'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'}
               )
    time.sleep(1)
    text = s.get('https://reddit.com/prefs/apps', headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'}).text
    uh = text[text.find('<input type="hidden" name="uh" value=') + 38:text.find('<input type="hidden" name="uh" value=') + 88]
    time.sleep(1)
    while True:
        app = choice(_config.config['apps'])
        client_id = app['client-id']
        secret = app['secret']
        r = s.post('https://www.reddit.com/api/adddeveloper',
                   data={
                       'uh': uh,
                       'client_id': client_id,
                       'name': name,
                       'id': f'#app-developer-{client_id}',
                       'renderstyle': 'html'
                   }, headers={'content-type': 'application/x-www-form-urlencoded',
                               'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'}
                   )
        if (r.status_code != 200) or (not loads(r.text)['success']):
            continue
        else:
            break
    _write_file(client_id, secret)


def _tor_session():
    s = Session()
    s.proxies = {'http':  'socks5://localhost:9050',
                 'https': 'socks5://localhost:9050'}
    return s


class account:
    def __init__(self, username, password, auth_token=None):
        self.username = username
        self.password = password
        if _config.config['tor']:
            self.session = _tor_session()
            self.setup_tor()
        else:
            self.session = Session()
        self.auth_token = auth_token
        self.auth_token_expiry = 0

    def setup_tor(self):
        self.tor_controller = Controller.from_port(port=9051)
        self.tor_controller.authenticate(password='r-placer')

    def get_auth_token(self):
        if self.username not in dev_accounts.keys():
            _add_developer_account(self.username)
        client_id = dev_accounts[self.username]['client-id']
        secret = dev_accounts[self.username]['secret']
        j = loads(self.session.post('https://ssl.reddit.com/api/v1/access_token', data={'grant_type': 'password',
                                                                                        'username': self.username,
                                                                                        'password': self.password},
                                    auth=auth.HTTPBasicAuth(client_id, secret),
                                    headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'}).text)
        while True:  # might hit rate limit. retry later to obtain access token.
            try:
                self.auth_token = 'Bearer ' + j['access_token']
                break
            except Exception:
                time.sleep(5)
        self.auth_token_expiry = time.time() + j['expires_in']

    def set_pixel(self, coordinates, color, canvas):
        if not self.auth_token or (self.auth_token_expiry - time.time() <= 50):
            self.get_auth_token()
        if _config.config['tor']:
            self.tor_controller.signal(Signal.NEWNYM)
        r = self.session.post('https://gql-realtime-2.reddit.com/query', headers={'content-type': 'application/json',
                                                                                  'origin': 'https://hot-potato.reddit.com',
                                                                                  'referer': 'https://hot-potato.reddit.com/',
                                                                                  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
                                                                                  'apollographql-client-name': 'mona-lisa',
                                                                                  'apollographql-client-version': '0.0.1',
                                                                                  'authorization': self.auth_token}, json=_setpixel_payload(coordinates, color, canvas))
        return r.text
