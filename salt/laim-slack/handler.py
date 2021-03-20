import os
import textwrap

import requests
from laim import Laim
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class SlackHandler(Laim):

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=('GET', 'HEAD', 'POST', 'DELETE', 'PUT', 'OPTIONS', 'TRACE'),
            backoff_factor=2,
        )))
        self.session.headers.update({
            'Authorization': 'Bearer %s' % self.config['slack-token'],
            # Explicitly set charset to avoid warnings from slack
            'Content-Type': 'application/json; charset=utf-8',
        })

        self.channel_id = self.config['slack-channel-id']
        self.hostname = '{{ grains.id }}'


    def handle_message(self, sender, recipients, message):
        response = self.session.post('https://slack.com/api/chat.postMessage', json={
            'channel': self.channel_id,
            'text': textwrap.dedent('''\
                `%s` received mail for %s
                *From*: %s
                *To*: %s
                *Subject*: %s

                %s
            ''') % (
                self.hostname,
                ', '.join(recipients),
                message.get('From'),
                message.get('To'),
                message.get('Subject'),
                message.get_payload(),
            ),
        })
        body = response.json()
        if not body['ok']:
            raise ValueError('Failed to forward mail to slack, got %r', body)


if __name__ == '__main__':
    handler = SlackHandler()
    handler.run()
