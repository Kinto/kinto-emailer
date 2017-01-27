import re

from kinto.core.events import AfterResourceChanged, ResourceChanged
from kinto.core.errors import raise_invalid
from kinto.core.storage import exceptions as storage_exceptions
from pyramid.settings import asbool
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message


EMAIL_REGEXP = re.compile(r"^(.*<[^@<>\s]+@[^@<>\s]+>)|([^@<>\s]+@[^@<>\s]+)$")
GROUP_REGEXP = re.compile(r"^/buckets/[^/]+/groups/[^/]+$")


def qualname(obj):
    """
    >>> str(msg.__class__)
    "<class 'pyramid_mailer.message.Message'>"
    >>> str(msg.__class__).split("'")
    ['<class ', 'pyramid_mailer.message.Message', '>']
    """
    return str(obj.__class__).split("'")[1]


def context_from_event(event):
    root_url = event.request.route_url("hello")
    context = dict(event=qualname(event),
                   root_url=root_url,
                   client_address=event.request.client_addr,
                   user_agent=event.request.user_agent,
                   **event.payload)
    # The following payload attributes are not always present.
    # See Kinto/kinto#945
    context.setdefault('record_id', '{record_id}')
    context.setdefault('collection_id', '{collection_id}')
    return context


def send_notification(event):
    storage = event.request.registry.storage
    messages = get_messages(storage, context_from_event(event))
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
    emails = [r for r in recipients if not GROUP_REGEXP.match(r)]
    groups = [r for r in recipients if GROUP_REGEXP.match(r)]
    for group_uri in groups:
        bucket_uri, group_id = group_uri.split('/groups/')
        try:
            group = storage.get(parent_id=bucket_uri,
                                collection_id='group',
                                object_id=group_id)
        except storage_exceptions.RecordNotFoundError:
            continue
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


def _validate_emailer_settings(event):
    request = event.request
    bucket_uri = '/buckets/{bucket_id}'.format(**event.payload)

    for impacted in event.impacted_records:
        collection_record = impacted['new']
        if 'kinto-emailer' not in collection_record:
            continue
        try:
            hooks = collection_record['kinto-emailer']['hooks']
        except KeyError:
            raise_invalid(request, description='Missing "hooks".')

        for hook in hooks:
            try:
                template = hook['template']
            except KeyError:
                raise_invalid(request, description='Missing "template".')

            try:
                context = context_from_event(event)
                template.format(**context)
            except KeyError as e:
                error_msg = 'Invalid template variable: %s' % e
                raise_invalid(request, description=error_msg)

            recipients = hook.get('recipients', [])
            if not recipients:
                raise_invalid(request, description='Empty list of recipients.')

            invalids = [r for r in recipients
                        if not (EMAIL_REGEXP.match(r) or GROUP_REGEXP.match(r))]
            if invalids:
                error_msg = 'Invalid recipients %s' % ', '.join(invalids)
                raise_invalid(request, description=error_msg)

            invalid_groups = [r for r in recipients
                              if GROUP_REGEXP.match(r) and
                              not r.startswith(bucket_uri)]
            if invalid_groups:
                error_msg = 'Invalid bucket for groups %s' % ', '.join(invalid_groups)
                raise_invalid(request, description=error_msg)


def includeme(config):
    # Include the mailer
    settings = config.get_settings()
    debug = asbool(settings.get('mail.debug_mailer', 'false'))
    config.include('pyramid_mailer' + ('.debug' if debug else ''))

    # Expose the capabilities in the root endpoint.
    message = "Provide emailing capabilities to the server."
    docs = "https://github.com/Kinto/kinto-emailer/"
    config.add_api_capability("emailer", message, docs)

    # Listen to collection modification before commit for validation.
    config.add_subscriber(_validate_emailer_settings, ResourceChanged,
                          for_resources=('collection',),
                          for_actions=('create', 'update'))

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
