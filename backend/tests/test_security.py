from __future__ import annotations

import time

import pytest

from app.core.errors import AuthenticationError
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    new_session_id,
    token_fingerprint,
    verify_password,
)

SECRET = "test-secret-key-with-enough-entropy-for-hs256"


class TestPasswords:
    def test_hash_and_verify_round_trip(self):
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
        assert verify_password("correct horse battery staple", hashed)

    def test_wrong_password_rejected(self):
        hashed = hash_password("right")
        assert not verify_password("wrong", hashed)

    def test_malformed_hash_returns_false_not_raise(self):
        assert not verify_password("anything", "not-a-bcrypt-hash")


class TestTokens:
    def test_access_token_round_trip(self):
        token, jti = create_access_token("user-1", SECRET, role="student", minutes=30)
        payload = decode_token(token, SECRET, expected_type="access")
        assert payload["sub"] == "user-1"
        assert payload["role"] == "student"
        assert payload["jti"] == jti
        assert payload["iss"] == "nexora"

    def test_type_confusion_rejected(self):
        token, _ = create_access_token("user-1", SECRET, role="student", minutes=30)
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token(token, SECRET, expected_type="refresh")
        assert exc_info.value.code == "token_invalid"

    def test_expired_token_rejected(self):
        # Negative lifetime: minting fails immediately because the jti is
        # recovered by decoding the token we just made.
        with pytest.raises(AuthenticationError) as exc_info:
            create_access_token("user-1", SECRET, role="student", minutes=-1)
        assert exc_info.value.code == "token_expired"

        token, _ = create_access_token("user-1", SECRET, role="student", minutes=30)
        # Force expiry by rewriting the clock: decode a token whose exp passed.
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"], issuer="nexora")
        payload["exp"] = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
        expired = pyjwt.encode(payload, SECRET, algorithm="HS256")
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token(expired, SECRET, expected_type="access")
        assert exc_info.value.code == "token_expired"

    def test_wrong_secret_rejected(self):
        token, _ = create_access_token("user-1", SECRET, role="student", minutes=30)
        with pytest.raises(AuthenticationError):
            decode_token(token, "other-secret", expected_type="access")

    def test_tampered_payload_rejected(self):
        token, _ = create_access_token("user-1", SECRET, role="student", minutes=30)
        header, _, signature = token.partition(".")
        tampered = f"{header}.{signature}.{signature}"
        with pytest.raises(AuthenticationError):
            decode_token(tampered, SECRET, expected_type="access")

    def test_foreign_issuer_rejected(self):
        import jwt as pyjwt

        foreign = pyjwt.encode(
            {"sub": "user-1", "typ": "access", "exp": int(time.time()) + 600},
            SECRET,
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError):
            decode_token(foreign, SECRET, expected_type="access")

    def test_refresh_and_password_reset_types(self):
        refresh, jti = create_refresh_token("user-1", SECRET, days=14)
        payload = decode_token(refresh, SECRET, expected_type="refresh")
        assert payload["jti"] == jti
        reset = create_password_reset_token("user-1", SECRET, minutes=30)
        assert decode_token(reset, SECRET, expected_type="password_reset")["sub"] == "user-1"

    def test_each_token_gets_unique_jti(self):
        t1, j1 = create_access_token("u", SECRET, role="student", minutes=5)
        t2, j2 = create_access_token("u", SECRET, role="student", minutes=5)
        assert j1 != j2 and t1 != t2


class TestServerSideTokenStorage:
    def test_fingerprint_is_stable_and_not_raw_token(self):
        token, _ = create_access_token("u", SECRET, role="student", minutes=5)
        fp = token_fingerprint(token)
        assert fp == token_fingerprint(token)
        assert fp != token
        assert len(fp) == 64  # sha256 hex

    def test_session_ids_are_unique(self):
        assert new_session_id() != new_session_id()
