"""访问日志不得泄露 URL 查询参数。"""

import logging
import unittest

import app.main as main_module
from app.services.access_log_redaction import (
    UvicornAccessLogRedactionFilter,
    redact_request_target,
)


class AccessLogRedactionTests(unittest.TestCase):
    def test_redacts_the_entire_query_but_keeps_path(self) -> None:
        target = "/api/v1/oidc/logout?id_token_hint=signed-secret&state=opaque"
        self.assertEqual(redact_request_target(target), "/api/v1/oidc/logout?[QUERY_REDACTED]")

    def test_keeps_path_when_there_is_no_query(self) -> None:
        self.assertEqual(redact_request_target("/api/v1/ready"), "/api/v1/ready")

    def test_uvicorn_access_record_never_formats_query_values(self) -> None:
        record = logging.LogRecord(
            "uvicorn.access", logging.INFO, "", 1, '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1:1234", "GET", "/logout?id_token_hint=signed-secret", "1.1", 302), None,
        )
        self.assertTrue(UvicornAccessLogRedactionFilter().filter(record))
        rendered = record.getMessage()
        self.assertIn("/logout?[QUERY_REDACTED]", rendered)
        self.assertNotIn("signed-secret", rendered)

    def test_application_startup_registers_the_access_filter(self) -> None:
        self.assertIsNotNone(main_module.app)
        access_logger = logging.getLogger("uvicorn.access")
        self.assertTrue(any(
            isinstance(item, UvicornAccessLogRedactionFilter)
            for item in access_logger.filters
        ))


if __name__ == "__main__":
    unittest.main()
