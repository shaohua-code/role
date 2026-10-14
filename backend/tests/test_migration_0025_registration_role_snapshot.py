"""Verify 0025 binds pending registration challenges to their default role."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "0025_registration_role_snapshot.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("registration_role_snapshot_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载注册角色快照 migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RegistrationRoleSnapshotMigrationTests(unittest.TestCase):
    def test_revision_invalidates_pending_challenges_and_adds_role_constraint(self) -> None:
        migration = load_migration()
        self.assertEqual(migration.revision, "0025_registration_role_snapshot")
        self.assertEqual(migration.down_revision, "0024_tenant_registration_audience")
        statements = []
        columns = []
        foreign_keys = []
        constraints = []
        indexes = []

        with (
            patch.object(migration.op, "execute", side_effect=lambda statement: statements.append(statement)),
            patch.object(migration.op, "add_column", side_effect=lambda *args: columns.append(args)),
            patch.object(
                migration.op, "create_foreign_key",
                side_effect=lambda *args, **kwargs: foreign_keys.append((args, kwargs)),
            ),
            patch.object(
                migration.op, "create_index",
                side_effect=lambda *args, **kwargs: indexes.append((args, kwargs)),
            ),
            patch.object(migration.op, "create_check_constraint", side_effect=lambda *args: constraints.append(args)),
        ):
            migration.upgrade()

        self.assertIn("SET consumed_at = now() WHERE consumed_at IS NULL", str(statements[0]))
        self.assertEqual([column[1].name for column in columns], ["registration_role_id", "registration_role_fingerprint"])
        self.assertEqual(foreign_keys[0][1]["ondelete"], "CASCADE")
        self.assertEqual(indexes[0][0][0], "ix_public_registration_challenges_registration_role_id")
        self.assertIn("registration_role_id IS NOT NULL", constraints[0][2])

    def test_downgrade_keeps_old_challenges_consumed(self) -> None:
        migration = load_migration()
        dropped_constraints = []
        dropped_columns = []
        dropped_indexes = []
        with (
            patch.object(
                migration.op, "drop_constraint",
                side_effect=lambda *args, **kwargs: dropped_constraints.append((args, kwargs)),
            ),
            patch.object(migration.op, "drop_column", side_effect=lambda *args: dropped_columns.append(args)),
            patch.object(
                migration.op, "drop_index",
                side_effect=lambda *args, **kwargs: dropped_indexes.append((args, kwargs)),
            ),
        ):
            migration.downgrade()

        self.assertEqual(len(dropped_constraints), 2)
        self.assertEqual(dropped_indexes[0][0][0], "ix_public_registration_challenges_registration_role_id")
        self.assertEqual(
            dropped_columns,
            [
                ("public_registration_challenges", "registration_role_fingerprint"),
                ("public_registration_challenges", "registration_role_id"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
