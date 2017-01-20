import mock
import os
import unittest

import configparser


from kinto import main as kinto_main
from kinto.core.events import AfterResourceChanged
from kinto.core.testing import BaseWebTest
from kinto_emailer import get_message, get_collection_record, send_notification


HERE = os.path.dirname(os.path.abspath(__file__))

COLLECTION_RECORD = {
    'kinto-emailer': {
        'record.update': {
            'sender': 'kinto@restmail.net',
            'subject': 'Configured subject',
            'template': 'Bonjour les amis.',
            'recipients': ['kinto-emailer@restmail.net'],
        }
    }
}


class PluginSetupTest(BaseWebTest, unittest.TestCase):
    entry_point = kinto_main
    api_prefix = "v1"
    config = 'config/kinto.ini'

    def get_app_settings(self, extras=None):
        ini_path = os.path.join(HERE, self.config)
        config = configparser.ConfigParser()
        config.read(ini_path)
        settings = dict(config.items('app:main'))
        if extras:
            settings.update(extras)
        return settings

    def test_capability_is_exposed(self):
        resp = self.app.get('/')
        capabilities = resp.json['capabilities']
        self.assertIn('emailer', capabilities)
        expected = {
            "description": "Provide emailing capabilities to the server.",
            "url": "https://github.com/Kinto/kinto-emailer/",
        }
        self.assertEqual(expected, capabilities['emailer'])

    def test_get_collection_record(self):
        storage = mock.MagicMock()

        get_collection_record(
            storage,
            bucket_id="default",
            collection_id="foobar")

        storage.get.assert_called_with(
            collection_id='collection',
            parent_id='/buckets/default',
            object_id='foobar')

    def test_send_notification_is_called_on_new_record(self):
        with mock.patch('kinto_emailer.send_notification') as mocked:
            app = self.make_app()
            app.post_json('/buckets/default/collections/foobar/records',
                          headers={'Authorization': 'Basic bmF0aW06'})
            event = mocked.call_args[0][0]
            assert isinstance(event, AfterResourceChanged)

    def test_send_notification_is_called_on_collection_update(self):
        with mock.patch('kinto_emailer.send_notification') as mocked:
            app = self.make_app()
            app.put_json('/buckets/default/collections/foobar',
                         {"data": {"status": "update"}},
                         headers={'Authorization': 'Basic bmF0aW06'})
            event = mocked.call_args[0][0]
            assert isinstance(event, AfterResourceChanged)


class PluginTest(unittest.TestCase):
    def test_get_message_returns_a_configured_message_for_records(self):
        message = get_message(COLLECTION_RECORD,
                              {'resource_name': 'record',
                               'action': 'update'})

        assert message.subject == 'Configured subject'
        assert message.sender == 'kinto@restmail.net'
        assert message.recipients == ['kinto-emailer@restmail.net']
        assert message.body == 'Bonjour les amis.'

    def test_get_message_returns_a_configured_message_for_collection_update(self):
        collection_record = {
            'kinto-emailer': {
                'collection.update': {
                    'sender': 'kinto@restmail.net',
                    'subject': 'Configured subject',
                    'template': 'Bonjour les amis on collection update.',
                    'recipients': ['kinto-emailer@restmail.net'],
                }
            }
        }

        message = get_message(collection_record,
                              {'resource_name': 'collection',
                               'action': 'update'})

        assert message.subject == 'Configured subject'
        assert message.sender == 'kinto@restmail.net'
        assert message.recipients == ['kinto-emailer@restmail.net']
        assert message.body == 'Bonjour les amis on collection update.'

    def test_get_emailer_info_return_none_if_emailer_not_configured(self):
        message = get_message({}, {'resource_name': 'record',
                                   'action': 'update'})
        assert message is None

    def test_get_message_returns_default_subject_to_new_message(self):
        collection_record = {
            'kinto-emailer': {
                'record.update': {
                    'sender': 'kinto@restmail.net',
                    'template': 'Bonjour les amis.',
                    'recipients': ['kinto-emailer@restmail.net'],
                }
            }
        }

        message = get_message(collection_record,
                              {'resource_name': 'record',
                               'action': 'update'})

        assert message.subject == 'New message'

    def test_get_collection_record(self):
        storage = mock.MagicMock()

        get_collection_record(
            storage,
            bucket_id="default",
            collection_id="foobar")

        storage.get.assert_called_with(
            collection_id='collection',
            parent_id='/buckets/default',
            object_id='foobar')

    def test_send_notification_ignore_non_record_events(self):
        event = mock.MagicMock()
        event.payload = {'resource_name': 'bucket'}

        with mock.patch('kinto_emailer.get_collection_record') as mocked:
            send_notification(event)
            assert not mocked.called

    def test_send_notification_does_not_call_the_mailer_if_no_message(self):
        event = mock.MagicMock()
        event.payload = {
            'resource_name': 'record',
            'action': 'update',
            'bucket_id': 'default',
            'collection_id': 'foobar'
        }

        with mock.patch(
                'kinto_emailer.get_collection_record',
                return_value=COLLECTION_RECORD) as get_collection_record:
            with mock.patch('kinto_emailer.get_mailer') as get_mailer:
                send_notification(event)
                assert get_collection_record.called
                assert get_mailer().send.called
