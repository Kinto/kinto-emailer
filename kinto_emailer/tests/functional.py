import os.path
import shutil
from glob import glob
from six.moves.urllib.parse import urljoin

import unittest
import requests
from six.moves import configparser

from kinto_client import Client

__HERE__ = os.path.abspath(os.path.dirname(__file__))

SERVER_URL = "http://localhost:8888/v1"
DEFAULT_AUTH = ('user', 'p4ssw0rd')


class FunctionalTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(FunctionalTest, self).__init__(*args, **kwargs)

        self.emailer_config = configparser.RawConfigParser()
        self.emailer_config.read(os.path.join(__HERE__, 'config/emailer.ini'))

        # Setup the kinto clients for the source and destination.
        self._auth = DEFAULT_AUTH
        self._server_url = SERVER_URL
        self._bucket = "emailer"
        self._collection = "collection1"

        self.client = Client(
            server_url=self._server_url,
            auth=self._auth,
            bucket=self._bucket,
            collection=self._collection)

    def tearDown(self):
        # Delete all the created objects.
        self._flush_server(self._server_url)
        shutil.rmtree('mail/', ignore_errors=True)

    def _flush_server(self, server_url):
        flush_url = urljoin(server_url, '/__flush__')
        resp = requests.post(flush_url)
        resp.raise_for_status()

    def test_new_record_send_email(self):
        self.client.create_bucket()
        self.client.create_collection(data={
            "kinto-emailer": {
                'record.create': {
                    "subject": "New email",
                    "template": "New {bucket_id}/{collection_id}/{record_id}.",
                    "recipients": ['kinto-emailer@restmail.net'],
                }
            }
        })

        record = self.client.create_record({'foo': 'bar'})['data']

        filename = sorted(glob('mail/*.msg'))[0]
        with open(filename, 'r') as f:
            body = f.read()

        assert 'kinto-emailer@restmail.net' in body
        assert "New email" in body
        assert "emailer/collection1/{}".format(record['id']) in body


if __name__ == '__main__':
    unittest.main()