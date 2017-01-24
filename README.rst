Kinto Emailer
#############

`Kinto <https://kinto.readthedocs.io>`_ is a minimalist storage for your web
applications. Sometimes, it might be useful to send emails when some events
arise (e.g. new records have been created). That's where this project can help!

Here is how kinto-emailer works
===============================

Attach a template string to your parent collection.
---------------------------------------------------

An email template needs to be added under the `email.templates.{action}` key,
where `{action}` is one of the values defined below.

You can attach these templates to the buckets or the collections, depending on
your use cases.

The following examples are defined on buckets:

.. code-block:: js

  {
    "kinto-emailer": {
      "hooks": [{
        "resource_name": "record",
        "action": "create",
        "template": "Hi, a new record '{uri}' has just been created in the collection '{bucket_id}/{collection_id}'",
        "recipients": ['Security reviewers <security-reviews@mozilla.com>'],
        "sender": "Kinto team <developers@kinto-storage.org>"
      }]
    }
  }

2. Check if templates are defined on new notifications
------------------------------------------------------

When a new notification is sent by Kinto, *kinto-emailer* checks if
templates are defined for the action and resource. If one template exists,
it uses it to send the email to the recipients.
