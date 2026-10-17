"""确保钱包权限迁移只登记稳定编码，不隐式创建角色授权。"""

import importlib.util
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch


MIGRATION_PATH = Path(__file__).parents[1] / "migrations" / "versions" / "0021_resume_wallet_permission_catalog.py"


class RecordingConnection:
    """捕获迁移写入参数，避免连接任何 IAM 数据库。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(self, statement: object, parameters: dict[str, object]) -> None:
        self.calls.append(parameters)


def load_migration() -> ModuleType:
    """从源码文件加载迁移，以便验证 revision 链和实际 seed 参数。"""
    spec = importlib.util.spec_from_file_location("wallet_permission_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 AI Resume 钱包权限迁移")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WalletPermissionMigrationTests(unittest.TestCase):
    """仅通过注入记录器检查 migration，不运行 Alembic 或访问数据库。"""

    def test_upgrade_seeds_read_and_recharge_codes_without_role_grants(self) -> None:
        migration = load_migration()
        connection = RecordingConnection()

        with patch.object(migration.op, "get_bind", return_value=connection):
            migration.upgrade()

        self.assertEqual(migration.revision, "0021_resume_wallet_perms")
        self.assertEqual(migration.down_revision, "0020_login_attempt_throttles")
        self.assertEqual(
            [(call["code"], call["resource_type"], call["scope"]) for call in connection.calls],
            [
                ("resume.wallet.read", "wallet", "read"),
                ("resume.wallet.recharge", "wallet", "recharge"),
            ],
        )
        self.assertTrue(all("role_id" not in call for call in connection.calls))


if __name__ == "__main__":
    unittest.main()
