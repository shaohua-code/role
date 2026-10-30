"""require_roles dependency smoke."""
from dataclasses import dataclass
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from iam_fastapi import IAMFastAPI, IAMUserContext


class RequireRolesTests(unittest.TestCase):
    def test_require_roles_allows_matching_key(self) -> None:
        client = MagicMock()
        iam = IAMFastAPI(client=client, session_dependency=lambda: None, permission_map={})
        dep = iam.require_roles("app.member", "app.admin")
        user = IAMUserContext(
            access_token="t", tenant_id="tid", subject_id="sub", role_keys=("app.member",),
        )
        self.assertIs(dep(user), user)

    def test_require_roles_denies_missing(self) -> None:
        client = MagicMock()
        iam = IAMFastAPI(client=client, session_dependency=lambda: None, permission_map={})
        dep = iam.require_roles("app.admin")
        user = IAMUserContext(
            access_token="t", tenant_id="tid", subject_id="sub", role_keys=("app.member",),
        )
        with self.assertRaises(HTTPException) as ctx:
            dep(user)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
