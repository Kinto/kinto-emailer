import smtplib
from email.mime.text import MIMEText

from cliquet.events import ResourceChanged
from pyramid.settings import asbool


class Mailer():

    def __init__(self, server, tls, username, password, sender):
        self.server = server
        self.tls = tls
        self.username = username
        self.password = password
        self.sender = sender

    def send_email(self, sender, recipients, subject, body):
        sender = sender or self.sender

        message = MIMEText(body)
        message['Subject'] = subject
        message['From'] = sender
        message['To'] = ", ".join(recipients)

        server = smtplib.SMTP(self.server)
        if self.tls:
            server.starttls()
        if self.username and self.password:
            server.login(self.username, self.password)
        server.sendmail(sender, recipients, message.as_string())
        server.quit()


def get_collection_record(storage, payload):
    parent_id = '/buckets/%s' % payload['bucket_id']
    collection_id = 'collection'

    return storage.get(
        parent_id=parent_id,
        collection_id=collection_id,
        object_id=payload['collection_id'])


def get_emailer_info(collection_record, payload):
    emailer_config = collection_record.get('kinto-emailer', {})
    current_action = '.'.join((
        payload['resource_name'],
        payload['action']
    ))
    if current_action not in emailer_config.keys():
        return
    selected_config = emailer_config[current_action]

    return {
        'template': selected_config['template'],
        'recipients': selected_config['recipients'],
        'sender': selected_config.get('sender')
    }


def includeme(config):
    settings = config.get_settings()
    mailer = Mailer(
        server=settings.get('emailer.server', 'localhost'),
        tls=asbool(settings.get('emailer.server', False)),
        username=settings.get('emailer.username'),
        password=settings.get('emailer.password'),
        sender=settings['emailer.sender'])

    # Expose the capabilities in the root endpoint.
    message = "Provide emailing capabilities to the server."
    docs = "https://github.com/Kinto/kinto-emailer"
    config.add_api_capability("emailer", message, docs)

    # Listen to resource change events, to check if a new signature is
    # requested.
    def send_notification(event):
        payload = event.payload
        storage = event.request.registry.storage
        if payload['resource_name'] != 'record':
            return
        collection_record = get_collection_record(storage, payload)
        info = get_emailer_info(collection_record, payload)
        if info:
            msg = info['template'].format(**payload)
            subject = info.get('subject', 'New message').format(**payload)
            mailer.send_email(
                sender=info['sender'],
                recipients=info['recipients'],
                subject=subject,
                body=msg)

    config.add_subscriber(
        send_notification,
        ResourceChanged,
        for_actions=('create', 'update', 'delete'),
        for_resources=('record'))
