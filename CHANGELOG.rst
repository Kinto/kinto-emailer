Changelog
=========

This document describes changes between each past release.

1.1.0 (2019-02-20)
------------------

**New features**

- Allow regexp in filters values when selecting events (#88)


1.0.2 (2018-04-17)
------------------

**Internal changes**

- Get rid of ``six``


1.0.1 (2017-11-21)
------------------

**Bug fixes**

- Don't block on Pyramid 1.8 anymore. (#46)


1.0.0 (2017-06-28)
------------------

**Bug fixes**

- Fix crash when creating bucket with ``POST /buckets`` (fixes #43)


0.4.0 (2017-04-14)
------------------

**New features**

- Add a ``validate_setup.py`` script to check that server can actually send emails
- Add a ``kinto-send-email`` command to test the configuration (fixes #35)

**Bug fixes**

- Fix sending notifications by decoupling it from transactions (fixes #38)

0.3.0 (2017-01-30)
------------------

**New features**

- Support configuration from bucket metadata (fixes #27)
- Send mail to local Maildir queue if ``mail.queue_path`` setting is defined (ref #3)

**Bug fixes**

- Fix support of batch requests (fixes #24)


0.2.0 (2017-01-27)
------------------

**New features**

- List of recipients can now contain groups URIs. The principals from the specified
  group that look like email addresses will be used as recipients (fixes #6)
- Support new variables like server root url or client IP address in email template (fixes #22)
- Add some validation when defining kinto-emailer settings in collections metadata (fixes #21)


0.1.0 (2017-01-25)
------------------

**Initial version**

- Use a list of hooks to configure emails bound to notifications (fixes #11)
- Support *kinto-signer* events (fixes #14)
