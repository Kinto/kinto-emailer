Kinto Emailer
#############

.. image:: https://github.com/Kinto/kinto-emailer/actions/workflows/tests.yml/badge.svg
        :target: https://github.com/Kinto/kinto-emailer/actions

.. image:: https://img.shields.io/pypi/v/kinto-emailer.svg
        :target: https://pypi.python.org/pypi/kinto-emailer

**kinto-emailer**  send emails when some events arise (e.g. new records have
been created). It relies on `Pyramid Mailer <https://github.com/Pylons/pyramid_mailer/>`_
for the sending part.


Install
=======

::

    pip install kinto-emailer

Setup
=====

In the `Kinto <http://kinto.readthedocs.io/>`_ settings:

.. code-block:: ini

    kinto.includes = kinto_emailer

    mail.default_sender = kinto@restmail.net

    # mail.host = localhost
    # mail.port = 25
    # mail.username = None
    # mail.password = None
    # mail.tls = False
    # mail.queue_path = None

If ``mail.queue_path`` is set, the emails are storage in a local Maildir queue.

See `more details about Pyramid Mailer configuration <http://docs.pylonsproject.org/projects/pyramid_mailer/en/latest/#configuration>`_.

Validate configuration
----------------------

The following command will send a dummy email to the specified recipient or will fail if the configuration is not correct:

::

    $ kinto-send-email config/kinto.ini testemailer@restmail.net


Development
-----------

Use a fake emailer that write emails files to disk:

.. code-block:: ini

    mail.debug_mailer = true


How does it work?
=================

Some information — like monitored action or list of recipients — are defined in
the collection or the bucket metadata. When an event occurs, the plugin sends emails if one of
the expected condition is met.


Usage
=====

The metadata on the collection (or the bucket) must look like this:

.. code-block:: js

    {
      "kinto-emailer": {
        "hooks": [{
          "template": "Something happened!",
          "recipients": ['Security reviewers <security-reviews@mozilla.com>']
        }]
      }
    }

In the above example, every action on the collection metadata or any record in that
collection will trigger an email notification.

The metadata of the collection override the bucket metadata, they are not merged.

Optional:

* ``subject`` (e.g. ``"An action was performed"``)
* ``sender`` (e.g. ``"Kinto team <developers@kinto-storage.org>"``)


Recipients
----------

The list of recipients can either contain:

* Email adresses (eg. ``alice@wonderland.com`` or ``"Joe Doe <jon@doe.com>"``)
* Group URI (eg. ``/buckets/staging/groups/reviewers``)

With group URIs, the email recipients will be expanded with the group members
principals look like email addresses (eg. ``ldap:peace@world.org``).


Selection
---------

It is possible to define several *hooks*, and filter on some condition. For example:

.. code-block:: js

  {
    "kinto-emailer": {
      "hooks": [{
        "resource_name": "record",
        "action": "create",
        "template": "Record created!",
        "recipients": ['Security reviewers <security-reviews@mozilla.com>']
      }, {
        "resource_name": "collection",
        "action": "updated",
        "template": "Collection updated!",
        "recipients": ["Security reviewers <security-reviews@mozilla.com>"]
      }]
    }
  }

The possible filters are:

* ``resource_name``: ``record`` or ``collection`` (default: all)
* ``action``: ``create``, ``update``, ``delete`` (default: all)
* ``collection_id`` (default: all)
* ``record_id`` (default: all)
* ``event``: ``kinto.core.events.AfterResourceChanged`` (default), or
  ``kinto_remote_settings.signer.events.ReviewRequested``, ``kinto_remote_settings.signer.events.ReviewApproved``,
  ``kinto_remote_settings.signer.events.ReviewRejected``

If a filter value starts with the special character ``^``, then the matching will consider the filter value to be a regular expression.

For example, in order to exclude a specific ``collection_id``, set the filter value to: ``^(?!normandy-recipes$)``.


Template
--------

The template string can have placeholders:

* ``bucket_id``
* ``id``: record or collection ``id``
* ``user_id``
* ``resource_name``
* ``uri``
* ``action``
* ``timestamp``
* ``root_url``
* ``client_address``
* ``user_agent``
* ``settings[name]``

For example:

``{user_id} has {action}d a {resource_name} in {bucket_id}.``

See `Kinto core notifications <http://kinto.readthedocs.io/en/5.3.0/core/notifications.html#payload>`_.


Running the tests
=================

To run the unit tests::

  $ make tests

Functional Tests
----------------

A PostgreSQL database is required.

Install and run PostgreSQL using your system package manager, or using Docker:

::

  $ docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15

Create the test database:

::

  $ psql -c "CREATE DATABASE testdb ENCODING 'UTF8' TEMPLATE template0;" -U postgres -h localhost -p 5432

Run a Kinto instance in a separate terminal::

  $ make run-kinto

And start the test suite::

  $ make functional

.. note::

    If you need to run PostgreSQL on a different user, password, or port than the default, then specify DB URL when running ``make run-kinto``::

      $ KINTO_STORAGE_URL="postgresql://username:password@host:6666/dbname" make run-kinto

Releasing
=========

1. Create a release on Github on https://github.com/Kinto/kinto-emailer/releases/new
2. Create a new tag `X.Y.Z` (*This tag will be created from the target when you publish this release.*)
3. Generate release notes
4. Publish release
