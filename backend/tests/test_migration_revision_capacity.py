"""验证长 revision ID 落库前，0017 会扩充 Alembic 版本号列。"""

import importlib.util
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch


MIGRATION_PATH = Path(__file__).parents[1] / "migrations" / "versions" / "0017_tenant_organization_admin_permissions.py"


class RecordingConnection:
    """只记录 seed SQL，确保用例不需要连接 IAM 数据库。"""

    def execute(self, statement: object, parameters: dict[str, object]) -> None:
        return None


def load_migration() -> ModuleType:
    """从源码文件加载首个长 revision 迁移。"""
    spec = importlib.util.spec_from_file_location("tenant_org_permission_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载租户组织权限迁移")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MigrationRevisionCapacityTests(unittest.TestCase):
    """锁定 migration version 表扩列行为，防止 0018 的长 revision 无法写入。"""

    def test_0017_expands_alembic_version_column_before_seed_writes(self) -> None:
        migration = load_migration()
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        with patch.object(migration.op, "alter_column", side_effect=lambda *args, **kwargs: calls.append((args, kwargs))), \
             patch.object(migration.op, "get_bind", return_value=RecordingConnection()):
            migration.upgrade()

        self.assertGreater(len("0018_tenant_application_admin_permissions"), 32)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ("alembic_version", "version_num"))
        self.assertEqual(calls[0][1]["existing_type"].length, 32)
        self.assertEqual(calls[0][1]["type_"].length, 128)


if __name__ == "__main__":
    unittest.main()
