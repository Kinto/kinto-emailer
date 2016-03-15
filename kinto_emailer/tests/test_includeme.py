import mock
from cliquet.events import AfterResourceChanged
from kinto.tests.support import unittest, BaseWebTest
from kinto_emailer import get_message, get_collection_record, send_notification

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
    def __init__(self, *args, **kwargs):
        super(PluginSetupTest, self).__init__(*args, **kwargs)
        self.app = self._get_test_app({
            'includes': ['kinto.plugins.default_bucket', 'kinto_emailer'],
            'emailer.sender': 'kinto.email@restmail.net',
        })

    def test_capability_is_exposed(self):
        resp = self.app.get('/')
        capabilities = resp.json['capabilities']
        self.assertIn('emailer', capabilities)
        expected = {
            "description": "Provide emailing capabilities to the server.",
            "url": "https://github.com/Kinto/kinto-emailer/",
        }
        self.assertEqual(expected, capabilities['emailer'])

    def test_get_message_returns_a_configured_message(self):
        message = get_message(COLLECTION_RECORD,
                              {'resource_name': 'record',
                               'action': 'update'})

        assert message.subject == 'Configured subject'
        assert message.sender == 'kinto@restmail.net'
        assert message.recipients == ['kinto-emailer@restmail.net']
        assert message.body == 'Bonjour les amis.'

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

    def test_send_notification_is_called_on_new_record(self):
        with mock.patch('kinto_emailer.send_notification') as mocked:
            app = self._get_test_app({
                'includes': ['kinto.plugins.default_bucket', 'kinto_emailer'],
                'emailer.sender': 'kinto.email@restmail.net',
            })
            app.post_json('/buckets/default/collections/foobar/records',
                          headers={'Authorization': 'Basic bmF0aW06'})
            event = mocked.call_args[0][0]
            assert isinstance(event, AfterResourceChanged)

    def test_send_notification_ignore_non_record_events(self):
        event = mock.MagicMock()
        event.payload = {'resource_name': 'collection'}

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
