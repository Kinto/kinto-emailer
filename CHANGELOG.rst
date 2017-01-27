Changelog
=========

This document describes changes between each past release.

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
