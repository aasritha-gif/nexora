from __future__ import annotations

import datetime as dt

import pytest

from app.databases.monetdb import (
    _EVENT_TYPES,
    sql_lit,
    validate_code,
    validate_event_type,
    validate_id,
)


class TestSqlLit:
    def test_none_is_null(self):
        assert sql_lit(None) == "NULL"

    def test_bools(self):
        assert sql_lit(True) == "TRUE"
        assert sql_lit(False) == "FALSE"

    def test_ints_and_floats(self):
        assert sql_lit(42) == "42"
        assert sql_lit(-7) == "-7"
        assert sql_lit(1.5) == repr(1.5)

    def test_datetimes(self):
        stamp = dt.datetime(2026, 10, 10, 9, 30, 5)
        assert sql_lit(stamp) == "TIMESTAMP '2026-10-10 09:30:05'"
        assert sql_lit(dt.date(2026, 10, 10)) == "DATE '2026-10-10'"

    def test_strings_single_quoted(self):
        assert sql_lit("plain") == "'plain'"

    def test_quote_escaping(self):
        rendered = sql_lit("O'Brien")
        assert rendered == "'O''Brien'"
        assert "'; DROP TABLE" not in rendered.replace("''", "x")

    def test_control_characters_stripped(self):
        # Everything below space is dropped except tab; newlines never reach SQL.
        rendered = sql_lit("line1\tline2\nline3\x00\x07end")
        assert "\t" in rendered
        assert "\n" not in rendered
        assert "\x00" not in rendered
        assert "\x07" not in rendered

    def test_long_strings_capped(self):
        rendered = sql_lit("a" * 5000)
        assert len(rendered) <= 1024 + 2

    def test_unsupported_type_rejected(self):
        with pytest.raises(TypeError):
            sql_lit(["not", "a", "literal"])


class TestValidators:
    def test_ids_accept_resource_and_user_shapes(self):
        for ok in ("RES-abc123", "user_1", "nexora-demo:sorting", "SESS.abc:xyz-1", "a" * 64):
            assert validate_id(ok) == ok

    @pytest.mark.parametrize("bad", [
        "", "has space", "'; DROP TABLE events;--", "a" * 65, 'quote"', "semi;colon",
    ])
    def test_ids_reject_injection_shapes(self, bad):
        with pytest.raises(ValueError):
            validate_id(bad)

    def test_codes_accept_upper_taxonomy_shapes(self):
        for ok in ("CSE", "CS-OS", "MATH-LA", "topic_9"):
            assert validate_code(ok) == ok

    @pytest.mark.parametrize("bad", ["CS OS", "CSE;DROP", "x,y", ""]) 
    def test_codes_reject_injection_shapes(self, bad):
        with pytest.raises(ValueError):
            validate_code(bad)

    def test_none_passes_through(self):
        assert validate_id(None) is None
        assert validate_code(None) is None

    def test_event_type_allowlist(self):
        for ok in _EVENT_TYPES:
            assert validate_event_type(ok) == ok

    @pytest.mark.parametrize("bad", ["view; DELETE FROM events", "VIEWS", "", "search'"])
    def test_event_type_rejects_unknown(self, bad):
        with pytest.raises(ValueError):
            validate_event_type(bad)
