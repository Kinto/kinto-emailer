import logging
import re

from kinto.core.errors import raise_invalid
from kinto.core.events import AfterResourceChanged, ResourceChanged
from kinto.core.storage import exceptions as storage_exceptions
from pyramid.settings import asbool
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message


logger = logging.getLogger(__name__)


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
    context = dict(
        event=qualname(event),
        root_url=root_url,
        client_address=event.request.client_addr,
        user_agent=event.request.user_agent,
        impacted_objects=event.impacted_objects,
        **event.payload,
    )

    context["settings"] = event.request.registry.settings

    # The following payload attributes are not always present.
    # See Kinto/kinto#945
    context.setdefault("record_id", "{record_id}")
    context.setdefault("collection_id", "{collection_id}")
    return context


def build_notification(event):
    resource_name = event.payload["resource_name"]
    storage = event.request.registry.storage
    context = context_from_event(event)

    # Build every email for every impacted objects.
    messages = []
    for impacted in event.impacted_objects:
        # Maybe context reliable on batch requests.
        # See Kinto/kinto#945
        _context = context.copy()
        object_id = impacted.get("new", impacted.get("old"))["id"]
        _context[resource_name + "_id"] = _context["id"] = object_id
        messages += get_messages(storage, _context)

    # Store the list in the current request, they will be sent from a
    # post commit hook (we don't send them if DB transaction is rolledback).
    setattr(event.request, "_kinto_emailer_messages", messages)


def send_notification(event):
    # At this point, we can't use `storage` because the transaction was committed.
    messages = event.request._kinto_emailer_messages
    settings = event.request.registry.settings
    mailer = get_mailer(event.request)
    try:
        for message in messages:
            if settings.get("mail.queue_path") is None:
                mailer.send_immediately(message, fail_silently=False)
            else:
                mailer.send_to_queue(message)
    except Exception:
        logger.exception("Could not send notifications")


def _get_emailer_hooks(storage, context):
    bucket_id = context["bucket_id"]
    collection_id = context["collection_id"]
    bucket_uri = "/buckets/%s" % bucket_id
    # Look-up collection metadata.
    # If the event is on the collection, do not rely on storage, use the event payload.
    if context["resource_name"] == "collection":
        metadata = next(
            impacted["old"] if context["action"] == "delete" else impacted["new"]
            for impacted in context["impacted_objects"]
        )
    else:
        # For records, look up storage.
        metadata = storage.get(
            parent_id=bucket_uri, resource_name="collection", object_id=collection_id
        )

    if "kinto-emailer" not in metadata:
        # Try in bucket metadata.
        metadata = storage.get(parent_id="", resource_name="bucket", object_id=bucket_id)
    # Returns empty list of hooks.
    return metadata.get("kinto-emailer", {}).get("hooks", [])


def _expand_recipients(storage, recipients, context):
    emails = [r for r in recipients if not GROUP_REGEXP.match(r)]
    # Group name using context (eg. /buckets/staging/{collection_id}-reviewers).
    groups = [r.format(**context) for r in recipients if GROUP_REGEXP.match(r.format(**context))]
    # Obtain group members from storage.
    for group_uri in groups:
        bucket_uri, group_id = group_uri.split("/groups/")
        try:
            group = storage.get(parent_id=bucket_uri, resource_name="group", object_id=group_id)
        except storage_exceptions.RecordNotFoundError:
            continue
        # Take out prefix from user ids (e.g. "ldap:mathieu@mozilla.com")
        unprefixed_members = [m.split(":", 1)[-1] for m in group["members"]]
        # Keep only group members that are email addresses.
        emails.extend([m for m in unprefixed_members if EMAIL_REGEXP.match(m)])

    return emails


def _match(hook, context):
    # Allow support of regexps in fields, if they start with ^
    if hook.startswith("^"):
        return re.match(hook, context)
    return hook == context


def get_messages(storage, context):
    hooks = _get_emailer_hooks(storage, context)
    filters = ("event", "action", "resource_name", "id", "record_id", "collection_id")
    messages = []
    for hook in hooks:
        # Filter out hook if it doesn't meet current event attributes, and keep
        # if nothing is specified.
        conditions_met = all(
            [
                field not in hook or field not in context or _match(hook[field], context[field])
                for field in filters
            ]
        )
        if not conditions_met:
            continue

        msg = hook["template"].format(**context)
        subject = hook.get("subject", "New message").format(**context)
        recipients = _expand_recipients(storage, hook["recipients"], context)

        if not recipients:
            continue

        messages.append(
            Message(subject=subject, sender=hook.get("sender"), recipients=recipients, body=msg)
        )
    return messages


def _validate_emailer_settings(event):
    request = event.request
    resource_name = event.payload["resource_name"]

    for impacted in event.impacted_objects:
        # See Kinto/kinto#945
        bid = impacted["new"]["id"] if resource_name == "bucket" else event.payload["bucket_id"]
        bucket_uri = "/buckets/{}".format(bid)

        metadata = impacted["new"]
        if "kinto-emailer" not in metadata:
            continue
        try:
            hooks = metadata["kinto-emailer"]["hooks"]
        except KeyError:
            raise_invalid(request, description='Missing "hooks".')

        for hook in hooks:
            try:
                hook["template"]
            except KeyError:
                raise_invalid(request, description='Missing "template".')

            recipients = hook.get("recipients", [])
            if not recipients:
                raise_invalid(request, description="Empty list of recipients.")

            invalids = [
                r for r in recipients if not (EMAIL_REGEXP.match(r) or GROUP_REGEXP.match(r))
            ]
            if invalids:
                error_msg = "Invalid recipients %s" % ", ".join(invalids)
                raise_invalid(request, description=error_msg)

            invalid_groups = [
                r for r in recipients if GROUP_REGEXP.match(r) and not r.startswith(bucket_uri)
            ]
            if invalid_groups:
                error_msg = "Invalid bucket for groups %s" % ", ".join(invalid_groups)
                raise_invalid(request, description=error_msg)


def includeme(config):
    # Include the mailer
    settings = config.get_settings()
    debug = asbool(settings.get("mail.debug_mailer", "false"))
    config.include("pyramid_mailer" + (".debug" if debug else ""))

    # Expose the capabilities in the root endpoint.
    message = "Provide emailing capabilities to the server."
    docs = "https://github.com/Kinto/kinto-emailer/"
    config.add_api_capability("emailer", message, docs)

    # Listen to collection modification before commit for validation.
    config.add_subscriber(
        _validate_emailer_settings,
        ResourceChanged,
        for_resources=(
            "bucket",
            "collection",
        ),
        for_actions=("create", "update"),
    )

    # Listen to collection and record change events.
    config.add_subscriber(
        build_notification, ResourceChanged, for_resources=("record", "collection")
    )
    config.add_subscriber(
        send_notification, AfterResourceChanged, for_resources=("record", "collection")
    )
