import os.path
import shutil
import unittest
from glob import glob
from urllib.parse import urljoin

import requests
from kinto_client import Client


__HERE__ = os.path.abspath(os.path.dirname(__file__))

SERVER_URL = "http://localhost:8888/v1"
DEFAULT_AUTH = ("user", "p4ssw0rd")


class FunctionalTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._server_url = SERVER_URL
        self.client = Client(
            server_url=self._server_url,
            auth=DEFAULT_AUTH,
            bucket="emailer",
            collection="collection1",
        )

    def setUp(self):
        super().setUp()
        # Since we use a PG database that can contain objects, start clean.
        self._flush_server(self._server_url)

    def tearDown(self):
        # Delete all the created objects.
        self._flush_server(self._server_url)
        # Delete all files but keep the folder for next runs.
        shutil.rmtree("mail/", ignore_errors=True)
        os.makedirs("mail/")

    def _flush_server(self, server_url):
        flush_url = urljoin(server_url, "/__flush__")
        resp = requests.post(flush_url)
        resp.raise_for_status()

    def test_new_record_send_email(self):
        self.client.create_bucket()
        self.client.create_collection(
            data={
                "kinto-emailer": {
                    "hooks": [
                        {
                            "resource_name": "record",
                            "action": "create",
                            "subject": "Action on {root_url}",
                            "template": (
                                "{client_address} edited:\n "
                                "{bucket_id}/{collection_id}/{record_id}."
                            ),
                            "recipients": ["kinto-emailer@restmail.net"],
                        }
                    ]
                }
            }
        )

        record = self.client.create_record({"foo": "bar"})["data"]

        filename = glob("mail/*.eml")[0]
        with open(filename, "r") as f:
            body = f.read()

        assert "kinto-emailer@restmail.net" in body
        assert "Action on http://localhost:8888/v1/" in body
        assert "127.0.0.1=20edited" in body
        assert "emailer/collection1/{}".format(record["id"]) in body

    def test_delete_collection_sends_email(self):
        self.client.create_bucket()
        self.client.create_collection(
            data={
                "kinto-emailer": {
                    "hooks": [
                        {
                            "resource_name": "collection",
                            "action": "delete",
                            "subject": "Collection {bucket_id}/{collection_id} was deleted",
                            "template": "(no body)",
                            "recipients": ["whatever@filesystem.local"],
                        }
                    ]
                }
            }
        )

        self.client.delete_collection()

        filename = glob("mail/*.eml")[0]
        with open(filename, "r") as f:
            body = f.read()

        assert "Collection emailer/collection1 was deleted" in body


if __name__ == "__main__":
    unittest.main()
