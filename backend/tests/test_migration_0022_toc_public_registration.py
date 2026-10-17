"""确认 `0022` 只建 ToC 注册结构、默认关闭且不自动创建/授权账号。"""

import importlib.util
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "0022_toc_public_registration.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("toc_public_registration_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 ToC 注册 migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicRegistrationMigrationTests(unittest.TestCase):
    def test_revision_follows_wallet_permissions_and_adds_only_registration_schema(self) -> None:
        migration = load_migration()
        self.assertEqual(migration.revision, "0022_toc_public_registration")
        self.assertEqual(migration.down_revision, "0021_resume_wallet_perms")
        calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

        def record(name: str):
            return lambda *args, **kwargs: calls.append((name, args, kwargs))

        methods = (
            "add_column", "create_check_constraint", "create_index", "create_table",
        )
        with (
            patch.object(migration.op, "add_column", side_effect=record("add_column")),
            patch.object(migration.op, "create_check_constraint", side_effect=record("create_check_constraint")),
            patch.object(migration.op, "create_index", side_effect=record("create_index")),
            patch.object(migration.op, "create_table", side_effect=record("create_table")),
        ):
            migration.upgrade()

        self.assertEqual({name for name, _, _ in calls}, set(methods))
        columns = [args[1].name for name, args, _ in calls if name == "add_column"]
        self.assertIn("registration_policy", columns)
        self.assertIn("registration_role_id", columns)
        self.assertIn("registration_terms_version", columns)
        self.assertIn("registration_privacy_version", columns)
        policy = next(args[1] for name, args, _ in calls
                      if name == "add_column" and args[1].name == "registration_policy")
        self.assertEqual(policy.server_default.arg, "disabled")

        created_tables = [args[0] for name, args, _ in calls if name == "create_table"]
        self.assertEqual(
            set(created_tables),
            {
                "public_registration_throttles",
                "public_registration_challenges",
                "public_registration_email_outbox",
                "public_registration_consents",
            },
        )
        challenges = next(args for name, args, _ in calls
                          if name == "create_table" and args[0] == "public_registration_challenges")
        challenge_columns = {item.name for item in challenges[1:] if hasattr(item, "name")}
        self.assertIn("terms_url", challenge_columns)
        self.assertIn("privacy_url", challenge_columns)
        self.assertIn("password_hash", challenge_columns)
        consents = next(args for name, args, _ in calls
                        if name == "create_table" and args[0] == "public_registration_consents")
        consent_columns = {item.name for item in consents[1:] if hasattr(item, "name")}
        self.assertIn("terms_url", consent_columns)
        self.assertIn("privacy_url", consent_columns)

    def test_downgrade_removes_only_registration_tables_and_application_columns(self) -> None:
        migration = load_migration()
        calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

        def record(name: str):
            return lambda *args, **kwargs: calls.append((name, args, kwargs))

        with (
            patch.object(migration.op, "drop_index", side_effect=record("drop_index")),
            patch.object(migration.op, "drop_table", side_effect=record("drop_table")),
            patch.object(migration.op, "drop_constraint", side_effect=record("drop_constraint")),
            patch.object(migration.op, "drop_column", side_effect=record("drop_column")),
        ):
            migration.downgrade()

        dropped_tables = {args[0] for name, args, _ in calls if name == "drop_table"}
        self.assertEqual(
            dropped_tables,
            {
                "public_registration_consents",
                "public_registration_email_outbox",
                "public_registration_challenges",
                "public_registration_throttles",
            },
        )
        dropped_columns = {args[1] for name, args, _ in calls if name == "drop_column"}
        self.assertEqual(
            dropped_columns,
            {
                "registration_privacy_version",
                "registration_terms_version",
                "registration_role_id",
                "registration_policy",
            },
        )


if __name__ == "__main__":
    unittest.main()
