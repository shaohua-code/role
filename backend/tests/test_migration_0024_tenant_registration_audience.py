"""确认新租户分类默认关闭 ToC 注册资格，并以数据库约束限制枚举值。"""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "0024_tenant_registration_audience.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("tenant_registration_audience_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载租户注册受众 migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TenantRegistrationAudienceMigrationTests(unittest.TestCase):
    def test_revision_defaults_existing_tenants_to_organization(self) -> None:
        migration = load_migration()
        self.assertEqual(migration.revision, "0024_tenant_registration_audience")
        self.assertEqual(migration.down_revision, "0023_user_membership_lifecycle")
        columns = []
        constraints = []
        dropped_columns = []

        with (
            patch.object(migration.op, "add_column", side_effect=lambda *args: columns.append(args)),
            patch.object(migration.op, "create_check_constraint", side_effect=lambda *args: constraints.append(args)),
            patch.object(migration.op, "execute"),
            patch.object(migration.op, "drop_column", side_effect=lambda *args: dropped_columns.append(args)),
        ):
            migration.upgrade()

        self.assertEqual(len(columns), 1)
        kind_column = columns[0][1]
        self.assertEqual(kind_column.name, "kind")
        self.assertEqual(kind_column.server_default.arg, "organization")
        self.assertIn("consumer", constraints[0][2])
        self.assertIn("organization", constraints[0][2])
        self.assertEqual(dropped_columns, [("public_registration_challenges", "password_hash")])


if __name__ == "__main__":
    unittest.main()
