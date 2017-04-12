import sys

from pyramid.paster import bootstrap
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message


subject = "[kinto-emailer] Test"
body = "If you received this email, the server is well configured."


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    try:
        config_file, recipient = args
    except ValueError:
        print("Usage: %s CONFIG RECIPIENT" % sys.argv[0])
        return 1

    print("Load config...")
    env = bootstrap(config_file)

    print("Send email to %r" % recipient)
    registry = env['registry']
    mailer = get_mailer(registry)

    message = Message(subject=subject,
                      recipients=[recipient],
                      body=body)
    mailer.send_immediately(message, fail_silently=False)
    print("Done.")
    return 0
