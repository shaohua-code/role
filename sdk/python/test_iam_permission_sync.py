"""Standard-library tests for the permission-catalog sync tool."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from iam_permission_sync import IamAdminClient, IamAdminError, sync_permission_manifest

MANIFEST = [
    {"code": "demo.document.read", "resource_type": "document", "scope": "read", "description": "读取文档"},
    {"code": "demo.document.create", "resource_type": "document", "scope": "write"},
]


class _Response:
    def __init__(self, payload) -> None:
        self.payload = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.payload.read()


def _http_error(code: int) -> HTTPError:
    return HTTPError("https://iam.example", code, "rejected", {}, None)


class IamAdminClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = IamAdminClient("https://iam.example/")

    @patch("iam_permission_sync.urlopen")
    def test_list_permissions_sends_management_token_and_normalizes_slash(self, open_url) -> None:
        open_url.return_value = _Response([{"id": "p1", "code": "demo.document.read"}])
        items = self.client.list_permissions("mgmt-token")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://iam.example/api/v1/admin/permissions")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer mgmt-token")
        self.assertEqual([item["code"] for item in items], ["demo.document.read"])

    @patch("iam_permission_sync.urlopen")
    def test_list_permissions_unwraps_paged_wrapper(self, open_url) -> None:
        open_url.return_value = _Response({
            "items": [{"id": "p1", "code": "demo.document.read"}],
            "total": 1, "limit": 1000, "offset": 0,
        })
        items = self.client.list_permissions("mgmt-token")
        self.assertEqual([item["code"] for item in items], ["demo.document.read"])

    @patch("iam_permission_sync.urlopen")
    def test_create_permission_posts_full_payload(self, open_url) -> None:
        open_url.return_value = _Response({"id": "p2", "code": "demo.document.create"})
        self.client.create_permission(
            "mgmt-token", code="demo.document.create",
            resource_type="document", scope="write", description="创建文档",
        )
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        # SDK 会按 code 前缀自动推导 catalog_namespace 并随 payload 提交。
        self.assertEqual(json.loads(request.data), {
            "code": "demo.document.create", "catalog_namespace": "demo",
            "resource_type": "document",
            "scope": "write",
            "surface": "business",
            "requires_data_scope": True,
            "description": "创建文档",
        })

    @patch("iam_permission_sync.urlopen", side_effect=HTTPError(
        "https://iam.example", 409, "conflict", {}, None))
    def test_http_rejection_keeps_status_code(self, _open_url) -> None:
        with self.assertRaises(IamAdminError) as error:
            self.client.create_permission(
                "mgmt-token", code="demo.x", resource_type="doc", scope="read")
        self.assertEqual(error.exception.status_code, 409)

    @patch("iam_permission_sync.urlopen", side_effect=URLError("offline"))
    def test_network_failure_maps_to_503(self, _open_url) -> None:
        with self.assertRaises(IamAdminError) as error:
            self.client.list_permissions("mgmt-token")
        self.assertEqual(error.exception.status_code, 503)

    @patch("iam_permission_sync.urlopen")
    def test_non_list_catalog_is_contract_error(self, open_url) -> None:
        open_url.return_value = _Response({"permissions": []})
        with self.assertRaises(IamAdminError) as error:
            self.client.list_permissions("mgmt-token")
        self.assertEqual(error.exception.status_code, 502)


    @patch("iam_permission_sync.urlopen")
    def test_application_scoped_endpoint(self, open_url) -> None:
        """L2 path: /admin/applications/{id}/permissions."""
        client = IamAdminClient("https://iam.example/", application_id="app-uuid-1")
        open_url.return_value = _Response([])
        client.list_permissions("mgmt-token")
        request = open_url.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://iam.example/api/v1/admin/applications/app-uuid-1/permissions",
        )

    @patch("iam_permission_sync.urlopen")
    def test_tenant_admin_surface_endpoint(self, open_url) -> None:
        client = IamAdminClient(
            "https://iam.example",
            application_id="app-2",
            api_surface="tenant-admin",
        )
        open_url.return_value = _Response([])
        client.list_permissions("mgmt-token")
        request = open_url.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://iam.example/api/v1/tenant-admin/applications/app-2/permissions",
        )



class SyncManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = IamAdminClient("https://iam.example")

    @patch("iam_permission_sync.urlopen")
    def test_empty_catalog_creates_every_entry(self, open_url) -> None:
        open_url.side_effect = [_Response([]), _Response({"id": "p1"}), _Response({"id": "p2"})]
        report = sync_permission_manifest(MANIFEST, client=self.client, management_token="mgmt-token")
        self.assertEqual(report.created, ("demo.document.read", "demo.document.create"))
        self.assertEqual(report.skipped, ())
        self.assertEqual(report.failed, ())
        self.assertEqual(open_url.call_count, 3)

    @patch("iam_permission_sync.urlopen")
    def test_existing_codes_are_skipped_without_create(self, open_url) -> None:
        open_url.return_value = _Response([
            {"id": "p1", "code": "demo.document.read"},
            {"id": "p2", "code": "demo.document.create"},
        ])
        report = sync_permission_manifest(MANIFEST, client=self.client, management_token="mgmt-token")
        self.assertEqual(report.skipped, ("demo.document.read", "demo.document.create"))
        self.assertEqual(report.created, ())
        # 只发生了一次目录读取，零次创建——重跑完全幂等。
        self.assertEqual(open_url.call_count, 1)

    @patch("iam_permission_sync.urlopen")
    def test_partial_catalog_creates_only_missing(self, open_url) -> None:
        open_url.side_effect = [
            _Response([{"id": "p1", "code": "demo.document.read"}]),
            _Response({"id": "p2"}),
        ]
        report = sync_permission_manifest(MANIFEST, client=self.client, management_token="mgmt-token")
        self.assertEqual(report.created, ("demo.document.create",))
        self.assertEqual(report.skipped, ("demo.document.read",))
        create_request = open_url.call_args_list[1].args[0]
        self.assertEqual(json.loads(create_request.data)["code"], "demo.document.create")

    @patch("iam_permission_sync.urlopen")
    def test_conflict_recheck_confirms_existing_as_skipped(self, open_url) -> None:
        # 首次目录为空 → 创建遇 409 → 重拉目录发现同码已被并发登记。
        open_url.side_effect = [
            _Response([]),
            _http_error(409),
            _Response([{"id": "p1", "code": "demo.document.read"}]),
            _Response({"id": "p2"}),
        ]
        report = sync_permission_manifest(MANIFEST, client=self.client, management_token="mgmt-token")
        self.assertEqual(report.skipped, ("demo.document.read",))
        self.assertEqual(report.created, ("demo.document.create",))
        self.assertEqual(report.failed, ())

    @patch("iam_permission_sync.urlopen")
    def test_conflict_with_missing_code_fails_closed(self, open_url) -> None:
        # 409 后重拉目录仍无该码：状态无法解释，保守记为 failed 而非静默当作成功。
        open_url.side_effect = [
            _Response([]),
            _http_error(409),
            _Response([]),
            _Response({"id": "p1"}),
        ]
        report = sync_permission_manifest(MANIFEST, client=self.client, management_token="mgmt-token")
        self.assertEqual(report.failed, (("demo.document.read", "conflict but code missing from catalog"),))
        self.assertEqual(report.created, ("demo.document.create",))

    @patch("iam_permission_sync.urlopen")
    def test_single_entry_failure_does_not_abort_batch(self, open_url) -> None:
        # 第一条创建被拒（如 403/422），第二条照常处理；报告逐条记录原因。
        open_url.side_effect = [
            _Response([]),
            _http_error(403),
            _Response({"id": "p2"}),
        ]
        report = sync_permission_manifest(MANIFEST, client=self.client, management_token="mgmt-token")
        self.assertEqual(report.failed, (("demo.document.read", "iam error 403"),))
        self.assertEqual(report.created, ("demo.document.create",))

    @patch("iam_permission_sync.urlopen", side_effect=URLError("offline"))
    def test_catalog_unreachable_aborts_before_any_create(self, open_url) -> None:
        with self.assertRaises(IamAdminError) as error:
            sync_permission_manifest(MANIFEST, client=self.client, management_token="mgmt-token")
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(open_url.call_count, 1)

    @patch("iam_permission_sync.urlopen")
    def test_invalid_manifest_rejected_before_any_network_call(self, open_url) -> None:
        invalid_manifests = [
            [],
            [{"code": "ab", "resource_type": "doc", "scope": "read"}],
            [{"code": "demo.ok", "resource_type": "", "scope": "read"}],
            [{"code": "demo.ok", "resource_type": "doc"}],
            [
                {"code": "demo.dup", "resource_type": "doc", "scope": "read"},
                {"code": "demo.dup", "resource_type": "doc", "scope": "read"},
            ],
            "not-a-list",
        ]
        for manifest in invalid_manifests:
            with self.assertRaises(ValueError):
                sync_permission_manifest(manifest, client=self.client, management_token="mgmt-token")
        open_url.assert_not_called()

    def test_missing_management_token_rejected_locally(self) -> None:
        with self.assertRaises(ValueError):
            self.client.list_permissions("")




if __name__ == "__main__":
    unittest.main()
