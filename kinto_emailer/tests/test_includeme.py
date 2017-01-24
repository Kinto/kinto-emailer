import mock
import os
import unittest

import configparser


from kinto import main as kinto_main
from kinto.core.events import AfterResourceChanged
from kinto.core.testing import BaseWebTest
from kinto_emailer import get_messages, send_notification


HERE = os.path.dirname(os.path.abspath(__file__))

COLLECTION_RECORD = {
    'kinto-emailer': {
        'hooks': [{
            'resource_name': 'record',
            'action': 'update',
            'sender': 'kinto@restmail.net',
            'subject': 'Record update',
            'template': 'Bonjour les amis.',
            'recipients': ['kinto-emailer@restmail.net'],
        }, {
            'resource_name': 'collection',
            'action': 'update',
            'sender': 'kinto@restmail.net',
            'subject': 'Collection update',
            'template': 'Bonjour les amis on collection update.',
            'recipients': ['kinto-emailer@restmail.net'],
        }]
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


class GetMessagesTest(unittest.TestCase):
    def test_get_messages_returns_configured_messages_for_records(self):
        payload = {'resource_name': 'record', 'action': 'update'}
        message, = get_messages(COLLECTION_RECORD, payload)

        assert message.subject == 'Record update'
        assert message.sender == 'kinto@restmail.net'
        assert message.recipients == ['kinto-emailer@restmail.net']
        assert message.body == 'Bonjour les amis.'

    def test_get_messages_returns_a_configured_message_for_collection_update(self):
        payload = {'resource_name': 'collection', 'action': 'update'}
        message, = get_messages(COLLECTION_RECORD, payload)

        assert message.subject == 'Collection update'
        assert message.sender == 'kinto@restmail.net'
        assert message.recipients == ['kinto-emailer@restmail.net']
        assert message.body == 'Bonjour les amis on collection update.'

    def test_get_emailer_info_returns_empty_list_if_emailer_not_configured(self):
        payload = {'resource_name': 'record', 'action': 'update'}
        messages = get_messages({}, payload)
        assert len(messages) == 0

    def test_get_messages_returns_default_subject_to_new_message(self):
        collection_record = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Bonjour les amis.',
                    'recipients': ['kinto-emailer@restmail.net'],
                }]
            }
        }
        payload = {'resource_name': 'record', 'action': 'update'}
        message, = get_messages(collection_record, payload)

        assert message.subject == 'New message'

    def test_get_messages_returns_several_messages_if_hooks_match(self):
        collection_record = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Bonjour les amis.',
                    'recipients': ['me@you.com'],
                }, {
                    'template': 'Bonjour les amies.',
                    'recipients': ['you@me.com'],
                }]
            }
        }
        payload = {'resource_name': 'record', 'action': 'update'}
        messages = get_messages(collection_record, payload)

        assert len(messages) == 2

    def test_get_messages_can_filter_by_id(self):
        collection_record = {
            'kinto-emailer': {
                'hooks': [{
                    'id': 'poll',
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }
        payload = {'resource_name': 'record', 'action': 'update', 'id': 'abc'}
        messages = get_messages(collection_record, payload)

        assert len(messages) == 0

    def test_get_messages_ignores_resource_if_not_specified(self):
        collection_record = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }

        payload = {'resource_name': 'record', 'action': 'update'}
        messages = get_messages(collection_record, payload)
        assert len(messages) == 1

        payload = {'resource_name': 'collection', 'action': 'update'}
        messages = get_messages(collection_record, payload)
        assert len(messages) == 1

    def test_get_messages_ignores_action_if_not_specified(self):
        collection_record = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }

        payload = {'resource_name': 'record', 'action': 'create'}
        messages = get_messages(collection_record, payload)
        assert len(messages) == 1

        payload = {'resource_name': 'record', 'action': 'update'}
        messages = get_messages(collection_record, payload)
        assert len(messages) == 1

    def test_get_messages_can_filter_by_event_class(self):
        collection_record = {
            'kinto-emailer': {
                'hooks': [{
                    'event': 'kinto_signer.events.ReviewRequested',
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }

        payload = {
            'event': 'kinto.core.events.AfterResourceChanged',
            'resource_name': 'record',
            'action': 'create'
        }
        messages = get_messages(collection_record, payload)
        assert len(messages) == 0


class SendNotificationTest(unittest.TestCase):
    def test_send_notification_does_not_call_the_mailer_if_no_message(self):
        event = mock.MagicMock()
        event.payload = {
            'resource_name': 'record',
            'action': 'update',
            'bucket_id': 'default',
            'collection_id': 'foobar'
        }
        event.request.registry.storage.get.return_value = {}

        with mock.patch('kinto_emailer.get_mailer') as get_mailer:
            send_notification(event)
            assert not get_mailer().send.called

    def test_send_notification_calls_the_mailer_if_match_event(self):
        event = mock.MagicMock()
        event.payload = {
            'resource_name': 'record',
            'action': 'update',
            'bucket_id': 'default',
            'collection_id': 'foobar'
        }
        event.request.registry.storage.get.return_value = COLLECTION_RECORD

        with mock.patch('kinto_emailer.get_mailer') as get_mailer:
            send_notification(event)
            assert get_mailer().send.called
