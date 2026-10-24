from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.security import hash_password
from app.models.resource import AccessType, Resource, ResourceStats
from app.models.user import Role, User, to_public
from tests.conftest import make_resource


def _user(**overrides) -> User:
    params = dict(
        user_id="user-1",
        email="ada@example.edu",
        name="Ada Lovelace",
        password_hash=hash_password("pw"),
    )
    params.update(overrides)
    return User(**params)


class TestUser:
    def test_password_hash_never_serializes(self):
        dumped = _user().model_dump()
        assert "password_hash" not in dumped
        assert "pw" not in repr(dumped)

    def test_model_dump_json_also_excludes_hash(self):
        assert "password_hash" not in _user().model_dump_json()

    def test_public_projection_round_trip(self):
        public = to_public(_user(role=Role.ADMIN))
        assert public.role == Role.ADMIN
        assert not hasattr(public, "password_hash")

    def test_email_normalized(self):
        assert User.normalize_email("  ADA@Example.EDU ") == "ada@example.edu"

    def test_academic_year_bounds_enforced(self):
        with pytest.raises(ValidationError):
            _user(academic_year=9)

    def test_tokens_invalid_before_defaults_none(self):
        assert _user().tokens_invalid_before is None


class TestResource:
    def test_defaults_are_free_and_unseeded(self):
        resource = make_resource()
        assert resource.access == AccessType.FREE
        assert resource.flags.is_seed_data is False
        assert resource.stats.views == 0
        assert resource.content.text_available is False

    def test_rating_average_math(self):
        stats = ResourceStats(rating_sum=9, rating_count=2)
        assert stats.rating_average == 4.5
        assert ResourceStats().rating_average is None

    def test_semester_validation_via_classification(self):
        from app.models.resource import ResourceClassification

        with pytest.raises(ValidationError):
            ResourceClassification(confidence=0.5, semester=11)

    def test_full_dump_contains_no_nested_pydantic_leakage_for_mongo(self):
        # model_dump must produce plain dicts/lists only — Motor cannot encode
        # arbitrary model instances.
        dumped = make_resource().model_dump()
        assert isinstance(dumped["taxonomy"], dict)
        assert isinstance(dumped["stats"], dict)
        assert isinstance(dumped["flags"], dict)
        assert isinstance(dumped["identifiers"], dict)
