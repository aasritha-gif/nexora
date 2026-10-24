from __future__ import annotations

from app.ingestion.dedup import (
    fingerprint,
    first_author_key,
    identifier_kinds,
    merge_metadata,
    normalize_title,
)
from app.models.resource import ResourceIdentifiers
from tests.conftest import make_item, make_resource


class TestNormalizeTitle:
    def test_punctuation_and_case_removed(self):
        assert normalize_title("The Quick Brown-Fox!") == "brown fox quick the"

    def test_parentheticals_removed(self):
        # "(Quick)" is stripped with the parenthetical group by design.
        assert normalize_title("The (Quick) Brown-Fox!") == "brown fox the"

    def test_word_order_normalized_for_set_equality(self):
        assert normalize_title("Machine Learning Basics") == normalize_title(
            "basics machine learning"
        )

    def test_parenthetical_editions_stripped(self):
        a = normalize_title("Operating Systems (3rd Edition)")
        b = normalize_title("Operating Systems")
        assert a == b


class TestFirstAuthorKey:
    def test_picks_first_real_author(self):
        assert first_author_key(["Unknown", "Grace Hopper"]) == "gracehopper"

    def test_strips_non_letters_and_caps_length(self):
        key = first_author_key(["Dr. Very-Long Name With Many Parts X"])
        assert len(key) <= 24
        assert key.isalpha()

    def test_empty_when_no_usable_author(self):
        assert first_author_key([]) == ""
        assert first_author_key(["anonymous", "editor"]) == ""


class TestFingerprint:
    def test_stable_for_same_title_and_author(self):
        item = make_item()
        assert fingerprint(item) == fingerprint(item.model_copy())

    def test_changes_with_author(self):
        base = make_item()
        other = make_item(authors=["Different Person"])
        assert fingerprint(base) != fingerprint(other)

    def test_changes_with_title(self):
        base = make_item()
        other = make_item(title="A Study of Graph Algorithms")
        assert fingerprint(base) != fingerprint(other)


class TestIdentifierKinds:
    def test_priority_order_doi_first(self):
        item = make_item(identifiers=ResourceIdentifiers(
            doi="10.1/abc", isbn="978-1", arxiv_id="2601.0001",
            source_id="id-1", url="https://example.org/paper/",
        ))
        kinds = [k for k, _ in identifier_kinds(item)]
        assert kinds == ["doi", "isbn", "arxiv_id", "source_id", "url"]

    def test_only_present_identifiers_returned(self):
        item = make_item(identifiers=ResourceIdentifiers(url="https://x.test"))
        assert identifier_kinds(item) == [("url", "https://x.test")]

    def test_source_id_namespaced_by_source(self):
        item = make_item(identifiers=ResourceIdentifiers(source_id="abc"))
        assert identifier_kinds(item) == [("source_id", "test-source:abc")]

    def test_url_trailing_slash_trimmed(self):
        item = make_item(identifiers=ResourceIdentifiers(url="https://x.test/a/"))
        assert identifier_kinds(item) == [("url", "https://x.test/a")]


class TestMergeMetadata:
    def test_existing_values_win(self):
        existing = make_resource(description="kept", year=2001)
        updates = merge_metadata(existing, make_item(description="new", year=2024))
        assert "description" not in updates
        assert "year" not in updates

    def test_gaps_get_filled(self):
        existing = make_resource(description="kept", year=2001)
        item = make_item(publisher="MIT Press", citation_count=12)
        updates = merge_metadata(existing, item)
        assert updates["publisher"] == "MIT Press"
        assert updates["citation_count"] == 12

    def test_citations_take_the_max(self):
        existing = make_resource(citation_count=30)
        updates = merge_metadata(existing, make_item(citation_count=10))
        assert "citation_count" not in updates

    def test_keywords_union_lowercased_and_capped(self):
        existing = make_resource(keywords=["Sorting"])
        item = make_item(keywords=["sorting", "algorithms"] + [f"kw{i}" for i in range(20)])
        updates = merge_metadata(existing, item)
        merged = set(updates["keywords"])
        assert "sorting" in merged and "algorithms" in merged
        assert len(updates["keywords"]) <= 24

    def test_empty_update_when_nothing_improves(self):
        existing = make_resource(
            description="d", year=2020, publisher="p", citation_count=99,
            keywords=["a", "b"], fingerprint="fp",
        )
        existing.identifiers.doi = "10.1/x"
        item = make_item(keywords=["A"])  # lowercase union adds nothing new
        assert merge_metadata(existing, item) == {}
