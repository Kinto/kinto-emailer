import re

from kinto.core.events import AfterResourceChanged
from pyramid.settings import asbool
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message


EMAIL_REGEXP = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
GROUP_REGEXP = re.compile(r"^/buckets/[^/]+/groups/[^/]+$")


def qualname(obj):
    """
    >>> str(msg.__class__)
    "<class 'pyramid_mailer.message.Message'>"
    >>> str(msg.__class__).split("'")
    ['<class ', 'pyramid_mailer.message.Message', '>']
    """
    return str(obj.__class__).split("'")[1]


def send_notification(event):
    payload = dict(event=qualname(event), **event.payload)
    storage = event.request.registry.storage

    messages = get_messages(storage, payload)
    mailer = get_mailer(event.request)
    for message in messages:
        mailer.send(message)


def _get_collection_record(storage, bucket_id, collection_id):
    parent_id = '/buckets/%s' % bucket_id
    record_type = 'collection'

    return storage.get(
        parent_id=parent_id,
        collection_id=record_type,
        object_id=collection_id)


def _expand_recipients(storage, recipients):
    emails = [r for r in recipients if EMAIL_REGEXP.match(r)]
    groups = [r for r in recipients if GROUP_REGEXP.match(r)]
    for group_uri in groups:
        bucket_uri, group_id = group_uri.split('/groups/')
        group = storage.get(parent_id=bucket_uri,
                            collection_id='group',
                            object_id=group_id)
        # Take out prefix from user ids (e.g. "ldap:mathieu@mozilla.com")
        unprefixed_members = [m.split(':', 1)[-1] for m in group['members']]
        # Keep only group members that are email addresses.
        emails.extend([m for m in unprefixed_members if EMAIL_REGEXP.match(m)])

    return emails


def get_messages(storage, payload):
    collection_record = _get_collection_record(storage,
                                               payload['bucket_id'],
                                               payload['collection_id'])
    filters = ('event', 'action', 'resource_name', 'id')
    hooks = collection_record.get('kinto-emailer', {}).get('hooks', [])
    messages = []
    for hook in hooks:
        # Filter out hook if it doesn't meet current event attributes, and keep
        # if nothing is specified.
        conditions_met = all([field not in hook or field not in payload or
                              hook[field] == payload[field]
                              for field in filters])
        if not conditions_met:
            continue

        msg = hook['template'].format(**payload)
        subject = hook.get('subject', 'New message').format(**payload)
        recipients = _expand_recipients(storage, hook['recipients'])

        messages.append(Message(subject=subject,
                                sender=hook.get('sender'),
                                recipients=recipients,
                                body=msg))
    return messages


def includeme(config):
    # Include the mailer
    settings = config.get_settings()
    debug = asbool(settings.get('mail.debug_mailer', 'false'))
    config.include('pyramid_mailer' + ('.debug' if debug else ''))

    # Expose the capabilities in the root endpoint.
    message = "Provide emailing capabilities to the server."
    docs = "https://github.com/Kinto/kinto-emailer/"
    config.add_api_capability("emailer", message, docs)

    # Listen to collection and record change events.
    config.add_subscriber(send_notification, AfterResourceChanged,
                          for_resources=('record', 'collection'))
    # In case kinto-signer is installed, plug events.
    try:
        from kinto_signer.events import ReviewRequested, ReviewApproved, ReviewRejected

        config.add_subscriber(send_notification, ReviewRequested)
        config.add_subscriber(send_notification, ReviewApproved)
        config.add_subscriber(send_notification, ReviewRejected)
    except ImportError:  # pragma: no cover
        pass
