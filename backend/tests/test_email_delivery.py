"""邮件投递只向已配置的 SMTP 发出短时 fragment 链接，不记录明文令牌。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.email import EmailDeliveryNotConfigured, send_password_reset_email


class PasswordResetEmailTests(unittest.TestCase):
    def test_smtp_message_uses_tls_and_keeps_token_out_of_query_string(self) -> None:
        settings = SimpleNamespace(
            smtp_host="smtp.example.test", smtp_port=587, smtp_username="iam", smtp_password="secret",
            smtp_from="iam@example.test", smtp_starttls=True, smtp_ssl=False,
            smtp_timeout_seconds=10, password_reset_token_minutes=30,
            console_public_url="https://iam.example.test",
        )
        with patch("app.services.email.get_settings", return_value=settings), \
                patch("app.services.email.SMTP") as smtp_factory:
            client = smtp_factory.return_value.__enter__.return_value
            send_password_reset_email("person@example.test", "opaque-reset-token")

        client.starttls.assert_called_once()
        client.login.assert_called_once_with("iam", "secret")
        message = client.send_message.call_args.args[0]
        content = message.get_content()
        self.assertIn("https://iam.example.test/#password-reset=opaque-reset-token", content)
        self.assertNotIn("?password-reset=", content)
        self.assertEqual(message["To"], "person@example.test")

    def test_missing_smtp_settings_fail_closed(self) -> None:
        settings = SimpleNamespace(smtp_host=None, smtp_from=None)
        with patch("app.services.email.get_settings", return_value=settings):
            with self.assertRaises(EmailDeliveryNotConfigured):
                send_password_reset_email("person@example.test", "opaque-reset-token")


if __name__ == "__main__":
    unittest.main()
