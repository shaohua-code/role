"""Contract tests for the DeerFlow IAM AuthorizationProvider adapter."""

from __future__ import annotations

import asyncio
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import iam_deerflow
from iam_authorization import AuthorizationDecision
from iam_deerflow import DeerFlowIamAuthorizationProvider


class FakeAuthorizationClient:
    instances: list["FakeAuthorizationClient"] = []

    def __init__(self, api_base_url: str, application_id: str, timeout_seconds: float) -> None:
        self.application_id = application_id
        self.calls: list[dict[str, object]] = []
        self.decision = AuthorizationDecision(True, "allowed", application_id=application_id)
        self.instances.append(self)

    def check(self, **kwargs: object) -> AuthorizationDecision:
        self.calls.append(kwargs)
        return self.decision


def make_principal(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "user_id": "gateway-user-1",
        "oauth_provider": "iam-dev",
        "oauth_id": "iam-sub-1",
        "is_internal": False,
        "attributes": {
            "iam_access_token": "opaque-test-token",
            "iam_subject": "iam-sub-1",
            "iam_tenant_id": "tenant-1",
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_request(principal: SimpleNamespace, *, resource: str = "route", action: str = "read", target: str = "threads") -> SimpleNamespace:
    return SimpleNamespace(principal=principal, resource=resource, action=action, target=target, context={})


class DeerFlowIamAuthorizationProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAuthorizationClient.instances.clear()
        self.client_patch = patch.object(iam_deerflow, "IamAuthorizationClient", FakeAuthorizationClient)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.provider = DeerFlowIamAuthorizationProvider(
            api_base_url="https://iam.example.test",
            application_id="application-1",
            oidc_provider="iam-dev",
            permission_map={"route:read:threads": "deerflow.thread.read", "route:read": "deerflow.resource.read"},
        )
        self.client = FakeAuthorizationClient.instances[-1]

    def test_authorize_calls_iam_with_server_session_identity_and_no_data_scope(self) -> None:
        decision = self.provider.authorize(make_request(make_principal()))

        self.assertTrue(decision.allow)
        self.assertEqual(self.client.calls, [{
            "access_token": "opaque-test-token",
            "tenant_id": "tenant-1",
            "permission_code": "deerflow.thread.read",
            "include_data_scope": False,
        }])

    def test_authorize_accepts_redacted_server_credential_mapping(self) -> None:
        class RedactedCredentials(dict[str, str]):
            def __repr__(self) -> str:
                return "IamAuthorizationCredentials(<redacted>)"

        credentials = RedactedCredentials({
            "iam_access_token": "opaque-test-token",
            "iam_subject": "iam-sub-1",
            "iam_tenant_id": "tenant-1",
        })
        principal = make_principal(attributes={"iam_credentials": credentials})

        self.assertTrue(self.provider.authorize(make_request(principal)).allow)
        self.assertEqual(self.client.calls[0]["access_token"], "opaque-test-token")
        self.assertNotIn("opaque-test-token", repr(credentials))
        self.assertTrue(self.provider.requires_iam_identity)

    def test_missing_permission_mapping_denies_without_network_call(self) -> None:
        decision = self.provider.authorize(make_request(make_principal(), resource="custom", target="unmapped"))

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reasons[0].code, "iam_permission_unmapped")
        self.assertEqual(self.client.calls, [])

    def test_missing_or_mismatched_iam_context_denies_without_network_call(self) -> None:
        missing_token = make_principal(attributes={"iam_subject": "iam-sub-1", "iam_tenant_id": "tenant-1"})
        mismatched_subject = make_principal(attributes={
            "iam_access_token": "opaque-test-token",
            "iam_subject": "other-subject",
            "iam_tenant_id": "tenant-1",
        })

        self.assertFalse(self.provider.authorize(make_request(missing_token)).allow)
        self.assertFalse(self.provider.authorize(make_request(mismatched_subject)).allow)
        self.assertEqual(self.client.calls, [])

    def test_internal_principal_and_wrong_provider_are_denied(self) -> None:
        internal = make_principal(is_internal=True)
        wrong_provider = make_principal(oauth_provider="other")

        self.assertFalse(self.provider.authorize(make_request(internal)).allow)
        self.assertFalse(self.provider.authorize(make_request(wrong_provider)).allow)
        self.assertEqual(self.client.calls, [])

    def test_iam_denial_and_transport_error_fail_closed(self) -> None:
        self.client.decision = AuthorizationDecision(False, "denied", application_id="application-1")
        denied = self.provider.authorize(make_request(make_principal()))
        self.client.check = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret token must not leak"))
        unavailable = self.provider.authorize(make_request(make_principal()))

        self.assertFalse(denied.allow)
        self.assertEqual(denied.reasons[0].code, "iam_permission_denied")
        self.assertFalse(unavailable.allow)
        self.assertEqual(unavailable.reasons[0].code, "iam_unavailable")
        self.assertNotIn("secret token", unavailable.reasons[0].message)

    def test_wrong_application_context_fails_closed(self) -> None:
        self.client.decision = AuthorizationDecision(True, "allowed", application_id="different-app")

        decision = self.provider.authorize(make_request(make_principal()))

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reasons[0].code, "iam_application_mismatch")

    def test_missing_application_context_fails_closed(self) -> None:
        self.client.decision = AuthorizationDecision(True, "allowed")

        decision = self.provider.authorize(make_request(make_principal()))

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reasons[0].code, "iam_application_mismatch")

    def test_configured_resource_id_is_sent_for_permission_and_scope_checks(self) -> None:
        provider = DeerFlowIamAuthorizationProvider(
            api_base_url="https://iam.example.test",
            application_id="application-1",
            permission_map={"route:read": "deerflow.resource.read"},
            resource_id_resolver=lambda request: request.context["iam_resource_id"],
        )
        client = FakeAuthorizationClient.instances[-1]
        request = make_request(make_principal(), resource="route", action="read", target="threads")
        request.context = {"iam_resource_id": "resource-threads"}

        self.assertTrue(provider.authorize(request).allow)
        self.assertEqual(client.calls[-1]["resource_id"], "resource-threads")

        client.decision = AuthorizationDecision(
            True,
            "allowed",
            data_scope={"mode": "any_of", "constraints": [{"kind": "tenant", "tenant_id": "tenant-1"}]},
            application_id="application-1",
        )
        scope_decision = provider.resolve_data_scope(
            make_principal(),
            resource="route",
            action="read",
            target="threads",
            context={"iam_resource_id": "resource-threads"},
        )
        self.assertTrue(scope_decision.allow)
        self.assertEqual(client.calls[-1]["resource_id"], "resource-threads")

    def test_invalid_configured_resource_id_fails_closed_without_iam_call(self) -> None:
        for resource_id in (" ", "r" * 181):
            with self.subTest(resource_id_length=len(resource_id)):
                provider = DeerFlowIamAuthorizationProvider(
                    api_base_url="https://iam.example.test",
                    application_id="application-1",
                    permission_map={"route:read": "deerflow.resource.read"},
                    resource_id_resolver=lambda _request, value=resource_id: value,
                )
                client = FakeAuthorizationClient.instances[-1]

                decision = provider.authorize(make_request(make_principal()))

                self.assertFalse(decision.allow)
                self.assertEqual(decision.reasons[0].code, "iam_resource_context_invalid")
                self.assertEqual(client.calls, [])

    def test_configured_resource_id_requires_trusted_scope_context(self) -> None:
        provider = DeerFlowIamAuthorizationProvider(
            api_base_url="https://iam.example.test",
            application_id="application-1",
            permission_map={"route:read": "deerflow.resource.read"},
            resource_id_resolver=lambda request: request.context["iam_resource_id"],
        )
        client = FakeAuthorizationClient.instances[-1]

        decision = provider.resolve_data_scope(
            make_principal(), resource="route", action="read", target="threads"
        )

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reasons[0].code, "iam_resource_context_invalid")
        self.assertEqual(client.calls, [])

    def test_resolve_data_scope_uses_verified_subject_and_requires_a_nonempty_scope(self) -> None:
        scope = {
            "mode": "any_of",
            "constraints": [
                {"kind": "owner", "field": "owner_user_id", "user_id": "iam-sub-1", "tenant_id": "tenant-1"},
                {"kind": "tenant", "tenant_id": "tenant-1"},
            ],
        }
        self.client.decision = AuthorizationDecision(True, "allowed", data_scope=scope, application_id="application-1")

        decision = self.provider.resolve_data_scope(
            make_principal(), resource="route", action="read", target="threads"
        )

        self.assertTrue(decision.allow)
        self.assertEqual(decision.metadata["data_scope"], scope)
        self.assertEqual(self.client.calls, [{
            "access_token": "opaque-test-token",
            "tenant_id": "tenant-1",
            "permission_code": "deerflow.thread.read",
            "include_data_scope": True,
            "subject_id": "iam-sub-1",
        }])

    def test_resolve_data_scope_fails_closed_for_missing_subject_or_scope(self) -> None:
        missing_subject = make_principal(attributes={
            "iam_access_token": "opaque-test-token",
            "iam_tenant_id": "tenant-1",
        })
        identity_denied = self.provider.resolve_data_scope(
            missing_subject, resource="route", action="read", target="threads"
        )
        self.assertFalse(identity_denied.allow)
        self.assertEqual(identity_denied.reasons[0].code, "iam_identity_unavailable")
        self.assertEqual(self.client.calls, [])

        self.client.decision = AuthorizationDecision(True, "allowed", application_id="application-1")
        scope_denied = self.provider.resolve_data_scope(
            make_principal(), resource="route", action="read", target="threads"
        )
        self.assertFalse(scope_denied.allow)
        self.assertEqual(scope_denied.reasons[0].code, "iam_data_scope_missing")

    def test_resolve_data_scope_fails_closed_without_exact_application_context(self) -> None:
        scope = {
            "mode": "any_of",
            "constraints": [{"kind": "tenant", "tenant_id": "tenant-1"}],
        }
        for application_id in (None, "different-app"):
            with self.subTest(application_id=application_id):
                self.client.decision = AuthorizationDecision(
                    True, "allowed", data_scope=scope, application_id=application_id
                )

                decision = self.provider.resolve_data_scope(
                    make_principal(), resource="route", action="read", target="threads"
                )

                self.assertFalse(decision.allow)
                self.assertEqual(decision.reasons[0].code, "iam_application_mismatch")

    def test_async_resolve_data_scope_refreshes_run_capability_before_check(self) -> None:
        class RefreshableCredentials(dict[str, str]):
            async def refresh_if_needed(self) -> None:
                self["iam_access_token"] = "refreshed-run-token"

            def __repr__(self) -> str:
                return "IamAuthorizationCredentials(<redacted>)"

        credentials = RefreshableCredentials({
            "iam_access_token": "expired-run-token",
            "iam_subject": "iam-sub-1",
            "iam_tenant_id": "tenant-1",
        })
        self.client.decision = AuthorizationDecision(
            True,
            "allowed",
            data_scope={"mode": "any_of", "constraints": [{"kind": "tenant", "tenant_id": "tenant-1"}]},
            application_id="application-1",
        )

        decision = asyncio.run(self.provider.aresolve_data_scope(
            make_principal(attributes={"iam_credentials": credentials}),
            resource="route",
            action="read",
            target="threads",
        ))

        self.assertTrue(decision.allow)
        self.assertEqual(self.client.calls[0]["access_token"], "refreshed-run-token")
        self.assertEqual(self.client.calls[0]["include_data_scope"], True)
        self.assertEqual(self.client.calls[0]["subject_id"], "iam-sub-1")
        self.assertNotIn("refreshed-run-token", repr(credentials))

    def test_filter_resources_keeps_only_explicitly_mapped_allowed_targets(self) -> None:
        provider = DeerFlowIamAuthorizationProvider(
            api_base_url="https://iam.example.test",
            application_id="application-1",
            permission_map={"tool:use": "deerflow.tool.invoke"},
        )

        visible = provider.filter_resources(make_principal(), "tool", ["visible_tool", "unmapped_tool"])

        self.assertEqual(visible, ["visible_tool", "unmapped_tool"])
        self.assertEqual(FakeAuthorizationClient.instances[-1].calls[0]["permission_code"], "deerflow.tool.invoke")
        self.assertEqual(len(FakeAuthorizationClient.instances[-1].calls), 1)

    def test_filter_resources_does_not_reuse_resource_scoped_allow_for_other_targets(self) -> None:
        provider = DeerFlowIamAuthorizationProvider(
            api_base_url="https://iam.example.test",
            application_id="application-1",
            permission_map={"tool:use": "deerflow.tool.invoke"},
            resource_id_resolver=lambda request: f"resource-{request.target}",
        )
        client = FakeAuthorizationClient.instances[-1]

        def check(**kwargs: object) -> AuthorizationDecision:
            client.calls.append(kwargs)
            allowed = kwargs.get("resource_id") == "resource-visible"
            return AuthorizationDecision(
                allowed,
                "allowed" if allowed else "denied",
                application_id="application-1",
            )

        client.check = check  # type: ignore[method-assign]

        visible = provider.filter_resources(
            make_principal(), "tool", ["visible", "hidden"]
        )

        self.assertEqual(visible, ["visible"])
        self.assertEqual(
            [call.get("resource_id") for call in client.calls],
            ["resource-visible", "resource-hidden"],
        )

    def test_target_specific_mapping_only_exposes_the_granted_target(self) -> None:
        provider = DeerFlowIamAuthorizationProvider(
            api_base_url="https://iam.example.test",
            application_id="application-1",
            permission_map={"tool:use:visible_tool": "deerflow.tool.invoke"},
        )

        visible = provider.filter_resources(make_principal(), "tool", ["visible_tool", "unmapped_tool"])

        self.assertEqual(visible, ["visible_tool"])
        self.assertEqual(len(FakeAuthorizationClient.instances[-1].calls), 1)

    def test_async_authorize_is_exposed_for_gateway_runtime(self) -> None:
        self.assertTrue(inspect.iscoroutinefunction(self.provider.aauthorize))

    def test_async_authorize_refreshes_run_capability_before_check(self) -> None:
        class RefreshableCredentials(dict[str, str]):
            async def refresh_if_needed(self) -> None:
                self["iam_access_token"] = "refreshed-run-token"

            def __repr__(self) -> str:
                return "IamAuthorizationCredentials(<redacted>)"

        credentials = RefreshableCredentials({
            "iam_access_token": "expired-run-token",
            "iam_subject": "iam-sub-1",
            "iam_tenant_id": "tenant-1",
        })
        principal = make_principal(attributes={"iam_credentials": credentials})

        decision = asyncio.run(self.provider.aauthorize(make_request(principal)))

        self.assertTrue(decision.allow)
        self.assertEqual(self.client.calls[0]["access_token"], "refreshed-run-token")
        self.assertNotIn("refreshed-run-token", repr(credentials))

    def test_async_authorize_fails_closed_when_run_session_revalidation_fails(self) -> None:
        class RevokedCredentials(dict[str, str]):
            async def refresh_if_needed(self) -> None:
                raise RuntimeError("secret vault details must not escape")

        principal = make_principal(attributes={
            "iam_credentials": RevokedCredentials({
                "iam_access_token": "stale-token",
                "iam_subject": "iam-sub-1",
                "iam_tenant_id": "tenant-1",
            }),
        })

        decision = asyncio.run(self.provider.aauthorize(make_request(principal)))

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reasons[0].code, "iam_unavailable")
        self.assertNotIn("secret vault details", decision.reasons[0].message)
        self.assertEqual(self.client.calls, [])

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DeerFlowIamAuthorizationProvider(
                api_base_url="https://iam.example.test",
                application_id="application-1",
                permission_map={"route:read": ""},
            )
        with self.assertRaises(ValueError):
            DeerFlowIamAuthorizationProvider(
                api_base_url="https://iam.example.test",
                application_id="application-1",
                permission_map={},
                timeout_seconds=31,
            )
        with self.assertRaises(ValueError):
            DeerFlowIamAuthorizationProvider(
                api_base_url="https://iam.example.test",
                application_id="application-1",
                permission_map={"route:read": "deerflow.resource.read"},
                resource_id_resolver="not-callable",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
