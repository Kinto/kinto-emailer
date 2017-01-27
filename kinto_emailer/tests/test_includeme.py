import mock
import os
import unittest

import configparser


from kinto import main as kinto_main
from kinto.core.events import AfterResourceChanged
from kinto.core.testing import BaseWebTest, get_user_headers, FormattedErrorMixin
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


class EmailerTest(BaseWebTest, unittest.TestCase):
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


class PluginSetupTest(EmailerTest):
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
    def setUp(self):
        self.storage = mock.MagicMock()
        self.storage.get.return_value = COLLECTION_RECORD
        self.payload = {
            'bucket_id': 'b',
            'collection_id': 'c',
            'resource_name': 'record',
            'action': 'update'
        }

    def test_get_messages_returns_configured_messages_for_records(self):
        message, = get_messages(self.storage, self.payload)

        assert message.subject == 'Record update'
        assert message.sender == 'kinto@restmail.net'
        assert message.recipients == ['kinto-emailer@restmail.net']
        assert message.body == 'Bonjour les amis.'

    def test_get_messages_returns_a_configured_message_for_collection_update(self):
        self.payload.update({'resource_name': 'collection'})
        message, = get_messages(self.storage, self.payload)

        assert message.subject == 'Collection update'
        assert message.sender == 'kinto@restmail.net'
        assert message.recipients == ['kinto-emailer@restmail.net']
        assert message.body == 'Bonjour les amis on collection update.'

    def test_get_emailer_info_returns_empty_list_if_emailer_not_configured(self):
        self.storage.get.return_value = {}
        messages = get_messages(self.storage, self.payload)
        assert len(messages) == 0

    def test_get_messages_returns_default_subject_to_new_message(self):
        self.storage.get.return_value = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Bonjour les amis.',
                    'recipients': ['kinto-emailer@restmail.net'],
                }]
            }
        }
        message, = get_messages(self.storage, self.payload)

        assert message.subject == 'New message'

    def test_get_messages_returns_several_messages_if_hooks_match(self):
        self.storage.get.return_value = {
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
        messages = get_messages(self.storage, self.payload)

        assert len(messages) == 2

    def test_get_messages_can_filter_by_id(self):
        self.storage.get.return_value = {
            'kinto-emailer': {
                'hooks': [{
                    'id': 'poll',
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }
        self.payload.update({'id': 'abc'})
        messages = get_messages(self.storage, self.payload)

        assert len(messages) == 0

    def test_get_messages_ignores_resource_if_not_specified(self):
        self.storage.get.return_value = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }

        messages = get_messages(self.storage, self.payload)
        assert len(messages) == 1

        self.payload.update({'resource_name': 'collection'})
        messages = get_messages(self.storage, self.payload)
        assert len(messages) == 1

    def test_get_messages_ignores_action_if_not_specified(self):
        self.storage.get.return_value = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }

        self.payload.update({'action': 'create'})
        messages = get_messages(self.storage, self.payload)
        assert len(messages) == 1

        self.payload.update({'action': 'update'})
        messages = get_messages(self.storage, self.payload)
        assert len(messages) == 1

    def test_get_messages_can_filter_by_event_class(self):
        self.storage.get.return_value = {
            'kinto-emailer': {
                'hooks': [{
                    'event': 'kinto_signer.events.ReviewRequested',
                    'template': 'Poll changed.',
                    'recipients': ['me@you.com'],
                }]
            }
        }
        self.payload.update({'event': 'kinto.core.events.AfterResourceChanged'})
        messages = get_messages(self.storage, self.payload)
        assert len(messages) == 0

        self.payload.update({'event': 'kinto_signer.events.ReviewRequested'})
        messages = get_messages(self.storage, self.payload)
        assert len(messages) == 1


class GroupExpansionTest(unittest.TestCase):

    def test_recipients_are_expanded_from_group_members(self):
        storage = mock.MagicMock()
        collection_record = {
            'kinto-emailer': {
                'hooks': [{
                    'template': 'Poll changed.',
                    'recipients': ['/buckets/b/groups/g'],
                }]
            }
        }
        group_record = {
            'members': ['fxa:225689876', 'portier:devnull@localhost.com']
        }
        storage.get.side_effect = [collection_record, group_record]
        payload = {'bucket_id': 'b', 'collection_id': 'c'}
        message, = get_messages(storage, payload)
        assert message.recipients == ['devnull@localhost.com']


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


class SignerEventsTest(EmailerTest):
    def get_app_settings(self, extras=None):
        settings = super(SignerEventsTest, self).get_app_settings(extras)
        settings['kinto.includes'] += ' kinto_signer'
        settings['kinto.signer.resources'] = (
            '/buckets/staging/collections/addons;'
            '/buckets/blocklists/collections/addons')
        settings['kinto.signer.group_check_enabled'] = 'false'
        settings['kinto.signer.to_review_enabled'] = 'true'
        settings['kinto.signer.signer_backend'] = 'kinto_signer.signer.autograph'
        settings['kinto.signer.autograph.server_url'] = 'http://localhost:8000'
        settings['kinto.signer.autograph.hawk_id'] = 'not-used-because-mocked'
        settings['kinto.signer.autograph.hawk_secret'] = 'not-used-because-mocked'
        return settings

    def setUp(self):
        collection = {
            'kinto-emailer': {
                'hooks': [{
                    'event': 'kinto_signer.events.ReviewRequested',
                    'template': '{user_id} requested review on {uri}.',
                    'recipients': ['me@you.com'],
                }]
            }
        }
        self.headers = dict(self.headers, **get_user_headers('nous'))
        self.app.put('/buckets/staging', headers=self.headers)
        self.app.put_json('/buckets/staging/collections/addons',
                          {'data': collection},
                          headers=self.headers)
        self.app.post_json('/buckets/staging/collections/addons/records',
                           {'data': {'age': 42}},
                           headers=self.headers)
        self._patch_autograph()

    def _patch_autograph(self):
        # Patch calls to Autograph.
        patch = mock.patch('kinto_signer.signer.autograph.requests')
        mocked = patch.start()
        mocked.post.return_value.json.return_value = [{
            "signature": "",
            "hash_algorithm": "",
            "signature_encoding": "",
            "content-signature": "",
            "x5u": ""}]
        return patch

    def test_email_is_when_review_is_requested(self):
        with mock.patch('kinto_emailer.get_mailer') as get_mailer:
            self.app.patch_json('/buckets/staging/collections/addons',
                                {'data': {'status': 'to-review'}},
                                headers=self.headers)
            assert get_mailer().send.called


class HookValidationTest(FormattedErrorMixin, EmailerTest):
    def setUp(self):
        self.valid_collection = {
            'kinto-emailer': {
                'hooks': [{
                    'template': '{user_id} requested review on {uri}.',
                    'recipients': [
                        'me@you.com',
                        'My friend alice <alice@wonderland.com>',
                        '<t.h.i.s+that@some.crazy.moderndomainnameyouknow>'
                    ]
                }]
            }
        }
        self.headers = dict(self.headers, **get_user_headers('nous'))
        self.app.put('/buckets/b', headers=self.headers)

    def test_supports_simple_recipients_list(self):
        self.app.put_json('/buckets/b/collections/c',
                          {'data': self.valid_collection},
                          headers=self.headers)

    def test_supports_groups_url(self):
        self.valid_collection['kinto-emailer']['hooks'][0]['recipients'] += [
            '/buckets/b/groups/g'
        ]
        self.app.put_json('/buckets/b/collections/c',
                          {'data': self.valid_collection},
                          headers=self.headers)

    def test_supports_empty_list_of_hooks(self):
        self.valid_collection['kinto-emailer']['hooks'] = []
        self.app.put_json('/buckets/b/collections/c',
                          {'data': self.valid_collection},
                          headers=self.headers)

    def test_supports_empty_template(self):
        self.valid_collection['kinto-emailer']['hooks'][0]['template'] = ''
        self.app.put_json('/buckets/b/collections/c',
                          {'data': self.valid_collection},
                          headers=self.headers)

    def test_fails_with_missing_hooks(self):
        self.valid_collection['kinto-emailer'].pop('hooks')
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        assert 'Missing "hooks"' in r.json['message']

    def test_validation_errors_are_well_formatted(self):
        self.valid_collection['kinto-emailer'].pop('hooks')
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        self.assertFormattedError(r, 400, errno=107, error='Invalid parameters',
                                  message='Missing "hooks"', info=None)

    def test_fails_if_missing_template(self):
        self.valid_collection['kinto-emailer']['hooks'][0].pop('template')
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        assert 'Missing "template"' in r.json['message']

    def test_fails_with_empty_list_of_recipients(self):
        self.valid_collection['kinto-emailer']['hooks'][0]['recipients'] = []
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        assert 'Empty list of recipients' in r.json['message']

    def test_fails_with_invalid_email_recipients(self):
        self.valid_collection['kinto-emailer']['hooks'][0]['recipients'].extend([
            '<fe@gmail.com',
            'haha@haha@com'
        ])
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        assert 'Invalid recipients <fe@gmail.com, haha@haha@com' in r.json['message']

    def test_fails_if_group_is_from_other_bucket(self):
        self.valid_collection['kinto-emailer']['hooks'][0]['recipients'] += [
            '/buckets/plop/groups/g'
        ]
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        assert 'Invalid bucket for groups /buckets/plop/groups/g' in r.json['message']

    def test_fails_if_group_uri_is_invalid(self):
        self.valid_collection['kinto-emailer']['hooks'][0]['recipients'] += [
            '/buckets/b/group/g'   # /groups/g!
        ]
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        assert 'Invalid recipients /buckets/b/group/g' in r.json['message']

    def test_fails_if_template_contains_bad_placeholders(self):
        tpl = 'The current temperature is {degres}C.'
        self.valid_collection['kinto-emailer']['hooks'][0]['template'] = tpl
        r = self.app.put_json('/buckets/b/collections/c',
                              {'data': self.valid_collection},
                              headers=self.headers,
                              status=400)
        assert 'degres' in r.json['message']
