"""后台任务仅在数据库 migration head 完整时访问当前版本的表。"""

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import _database_ready_for_background_work


class BackgroundDatabaseReadinessTests(unittest.TestCase):
    @patch("app.main.readiness_check")
    def test_current_schema_allows_background_work(self, readiness_check) -> None:
        self.assertTrue(_database_ready_for_background_work())
        readiness_check.assert_called_once_with()

    @patch("app.main.readiness_check", side_effect=HTTPException(status_code=503, detail="database_migration_pending"))
    def test_unready_schema_pauses_background_work(self, _readiness_check) -> None:
        self.assertFalse(_database_ready_for_background_work())

    @patch("app.main.readiness_check", side_effect=HTTPException(status_code=500, detail="unexpected"))
    def test_unexpected_readiness_status_is_not_silenced(self, _readiness_check) -> None:
        with self.assertRaises(HTTPException) as raised:
            _database_ready_for_background_work()
        self.assertEqual(raised.exception.status_code, 500)


if __name__ == "__main__":
    unittest.main()
