from kinto.core.events import AfterResourceChanged
from pyramid.settings import asbool
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message


def send_notification(event):
    payload = event.payload
    storage = event.request.registry.storage

    resource_name = payload['resource_name']
    action = payload.get('action')
    is_record = resource_name == 'record'
    is_collection_update = resource_name == 'collection' and action == 'update'
    if not is_record and not is_collection_update:
        return

    collection_record = get_collection_record(storage,
                                              payload['bucket_id'],
                                              payload['collection_id'])
    message = get_message(collection_record, payload)

    if message:
        mailer = get_mailer(event.request)
        mailer.send(message)


def get_collection_record(storage, bucket_id, collection_id):
    parent_id = '/buckets/%s' % bucket_id
    record_type = 'collection'

    return storage.get(
        parent_id=parent_id,
        collection_id=record_type,
        object_id=collection_id)


def get_message(collection_record, payload):
    emailer_config = collection_record.get('kinto-emailer', {})
    current_action = '.'.join((
        payload['resource_name'],
        payload['action']
    ))
    if current_action not in emailer_config.keys():
        return
    selected_config = emailer_config[current_action]

    msg = selected_config['template'].format(**payload)
    subject = selected_config.get('subject', 'New message').format(**payload)

    return Message(subject=subject,
                   sender=selected_config.get('sender'),
                   recipients=selected_config['recipients'],
                   body=msg)


def includeme(config):
    # Include the mailer
    settings = config.get_settings()
    debug = asbool(settings.get('mail.debug', 'false'))
    config.include('pyramid_mailer' + ('.debug' if debug else ''))

    # Expose the capabilities in the root endpoint.
    message = "Provide emailing capabilities to the server."
    docs = "https://github.com/Kinto/kinto-emailer/"
    config.add_api_capability("emailer", message, docs)

    # Listen to resource change events, to check if a new signature is
    # requested.
    config.add_subscriber(
        send_notification,
        AfterResourceChanged,
        for_actions=('create', 'update', 'delete'),
        for_resources=('record', 'collection'))
