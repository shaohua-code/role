"""AES-GCM token-vault tests; no database, filesystem, or network access."""

import unittest
from uuid import uuid4

from iam_token_vault import IamTokenVaultCipher, TokenVaultError


class IamTokenVaultCipherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cipher = IamTokenVaultCipher(bytes(range(32)))
        self.context = {
            "issuer": "https://iam.example.test",
            "subject": str(uuid4()),
            "tenant_id": str(uuid4()),
            "token_type": "access_token",
        }

    def test_round_trip_keeps_plaintext_out_of_envelope_and_repr(self) -> None:
        token = "eyJhbGciOiJSUzI1NiJ9.example.signature"
        envelope = self.cipher.encrypt(token, **self.context)

        self.assertTrue(envelope.startswith("v1."))
        self.assertNotIn(token, envelope)
        self.assertEqual(self.cipher.decrypt(envelope, **self.context), token)
        self.assertEqual(repr(self.cipher), "IamTokenVaultCipher(<redacted>)")
        self.assertNotIn(token, repr(self.cipher))

    def test_random_nonce_produces_different_envelopes(self) -> None:
        token = "opaque-refresh-token"
        first = self.cipher.encrypt(token, **self.context)
        second = self.cipher.encrypt(token, **self.context)

        self.assertNotEqual(first, second)
        self.assertEqual(self.cipher.decrypt(first, **self.context), token)
        self.assertEqual(self.cipher.decrypt(second, **self.context), token)

    def test_envelope_is_bound_to_issuer_subject_tenant_and_token_type(self) -> None:
        token = "opaque-refresh-token"
        envelope = self.cipher.encrypt(token, **self.context)
        for key, replacement in (
            ("issuer", "https://other.example.test"),
            ("subject", str(uuid4())),
            ("tenant_id", str(uuid4())),
            ("token_type", "refresh_token"),
        ):
            context = {**self.context, key: replacement}
            with self.subTest(context=key), self.assertRaises(TokenVaultError):
                self.cipher.decrypt(envelope, **context)

    def test_rejects_malformed_envelopes_and_invalid_key_sizes(self) -> None:
        with self.assertRaises(ValueError):
            IamTokenVaultCipher(b"short")
        with self.assertRaises(TokenVaultError):
            self.cipher.decrypt("v2.invalid", **self.context)
        with self.assertRaises(TokenVaultError):
            self.cipher.decrypt("v1.%%%", **self.context)
        # The byte limit (not only Python character count) keeps UTF-8 payloads bounded.
        with self.assertRaises(TokenVaultError):
            self.cipher.encrypt("🙂" * 5_000, **self.context)


if __name__ == "__main__":
    unittest.main()
