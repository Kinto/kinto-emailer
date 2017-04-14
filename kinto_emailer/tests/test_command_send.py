import mock
import unittest

from kinto_emailer import command_send


class CommandTest(unittest.TestCase):
    def test_uses_sys_args_by_default(self):
        assert command_send.main() > 0  # will fail

    def test_returns_non_zero_if_not_enough_args(self):
        assert command_send.main([]) > 0

    def test_calls_send_immmediately_with_parameters(self):
        with mock.patch('kinto_emailer.command_send.bootstrap'):
            with mock.patch('kinto_emailer.command_send.get_mailer') as get_mailer:
                command_send.main(["config.ini", "me@restmail.net"])

                args, kwargs = get_mailer().send_immediately.call_args_list[0]
                assert "kinto-emailer" in args[0].subject
                assert not kwargs["fail_silently"]
