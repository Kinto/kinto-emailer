from kinto.core.events import AfterResourceChanged
from pyramid.settings import asbool
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message


def send_notification(event):
    payload = event.payload
    storage = event.request.registry.storage

    collection_record = _get_collection_record(storage,
                                               payload['bucket_id'],
                                               payload['collection_id'])
    messages = get_messages(collection_record, payload)
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


def get_messages(collection_record, payload):
    hooks = collection_record.get('kinto-emailer', {}).get('hooks', [])
    messages = []
    for hook in hooks:
        conditions_met = all([hook.get(field, payload[field]) == payload[field]
                              for field in ('action', 'resource_name')])
        if not conditions_met:
            continue

        msg = hook['template'].format(**payload)
        subject = hook.get('subject', 'New message').format(**payload)

        messages.append(Message(subject=subject,
                                sender=hook.get('sender'),
                                recipients=hook['recipients'],
                                body=msg))
    return messages


def includeme(config):
    # Include the mailer
    settings = config.get_settings()
    debug = asbool(settings.get('mail.debug', 'false'))
    config.include('pyramid_mailer' + ('.debug' if debug else ''))

    # Expose the capabilities in the root endpoint.
    message = "Provide emailing capabilities to the server."
    docs = "https://github.com/Kinto/kinto-emailer/"
    config.add_api_capability("emailer", message, docs)

    # Listen to collection and record change events.
    config.add_subscriber(send_notification, AfterResourceChanged,
                          for_resources=('record', 'collection'))
