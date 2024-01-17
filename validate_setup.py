import logging
import sys
import time

import requests
from kinto_http import cli_utils


logger = logging.getLogger(__name__)

DEFAULT_SERVER = "https://remote-settings.allizom.org/v1"
BUCKET = "staging"
COLLECTION = "qa"
MAILBOX = "kintoemailer"
RECIPIENT = MAILBOX + "@restmail.net"
SUBJECT_EMAIL_CREATION = "Record created!"
RETRY_TIMEOUT = 60


def clear_inbox(mailbox):
    requests.delete("https://restmail.net/mail/%s/" % mailbox)


def fetch_emails(mailbox):
    resp = requests.get("https://restmail.net/mail/%s/" % mailbox)
    emails = resp.json()
    return emails


def setup_notifs_signing(client, recipient):
    setup = {
        "kinto-emailer": {
            "hooks": [
                {
                    "event": "kinto_remote_settings.signer.events.ReviewRequested",
                    "subject": "{user_id} requested review on {bucket_id}/{collection_id}.",
                    "template": "Review changes at {root_url}admin/#/buckets/{bucket_id}/collections/{collection_id}/records",
                    "recipients": [recipient],
                },
                {
                    "resource_name": "record",
                    "action": "create",
                    "subject": SUBJECT_EMAIL_CREATION,
                    "template": "For QA purposes :)",
                    "recipients": [recipient],
                },
            ]
        }
    }
    client.patch_collection(data=setup)


def main(args=None):
    parser = cli_utils.add_parser_options(
        description="Validate kinto-emailer setup",
        default_server=DEFAULT_SERVER,
        default_bucket=BUCKET,
        default_collection=COLLECTION,
    )

    args = parser.parse_args(args)

    cli_utils.setup_logger(logger, args)

    client = cli_utils.create_client_from_args(args)

    # 1. Check capabilities
    capabilities = client.server_info()["capabilities"]
    if "emailer" not in capabilities:
        print("Server doesn't have support for email notifications: \x1b[1;31m KO \x1b[0m")
        return 2

    print("Clear inbox")
    clear_inbox(MAILBOX)

    # 2. Configure collection metadata.
    print("Configure emailing in %r collection" % args.collection)
    setup_notifs_signing(client, RECIPIENT)

    # 3. Create a record.
    print("Create a dummy record")
    client.create_record(data={"script": "validate kinto-emailer setup"})

    # 4. If signing is enabled for this collection, then also check email for ReviewRequested.
    signed_resources = capabilities.get("signer", {"resources": []})["resources"]
    ids = [(r["source"]["bucket"], r["source"]["collection"]) for r in signed_resources]
    signing_enabled = (args.bucket, args.collection) in ids

    if signing_enabled:
        # 4. Request a review.
        client.patch_collection(data={"status": "to-review"})

    # 5. Check that emails were received.
    print("Scan inbox...")
    first_try = time.time()
    while True:
        emails = fetch_emails(MAILBOX)
        subjects = [e["subject"] for e in emails]

        if SUBJECT_EMAIL_CREATION not in subjects:
            if time.time() - first_try < RETRY_TIMEOUT:
                time.sleep(3)
                sys.stdout.write(".")
                sys.stdout.flush()
                continue
        break

    if SUBJECT_EMAIL_CREATION in subjects:
        print("Email received:\x1b[1;32m OK \x1b[0m")

        if signing_enabled:
            if "requested review" in subjects:
                print("Review notification received:\x1b[1;32m OK \x1b[0m")
            else:
                print("Review notification not received:\x1b[1;31m KO \x1b[0m")
    else:
        print("Email not received:\x1b[1;31m KO \x1b[0m")

    return 0


if __name__ == "__main__":
    sys.exit(main())
