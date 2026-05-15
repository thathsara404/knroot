"""Unit tests for backend.core.template_filters.pub_date()."""
from datetime import datetime, timedelta, timezone


def _pub_date(published):
    from backend.core.template_filters import pub_date
    return pub_date(published)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


NOW = datetime.now(timezone.utc)


class TestPubDateMissingInput:
    def test_empty_string_returns_dash(self):
        assert _pub_date("") == "–"

    def test_none_returns_dash(self):
        assert _pub_date(None) == "–"


class TestPubDateRelative:
    def test_30_minutes_ago_shows_m_ago(self):
        dt = NOW - timedelta(minutes=30)
        result = _pub_date(_iso(dt))
        assert "m ago" in result

    def test_1_minute_ago_shows_1m(self):
        dt = NOW - timedelta(seconds=30)
        result = _pub_date(_iso(dt))
        assert "1m ago" in result

    def test_5_hours_ago_shows_h_ago(self):
        dt = NOW - timedelta(hours=5)
        result = _pub_date(_iso(dt))
        assert "h ago" in result

    def test_yesterday_shows_yesterday(self):
        dt = NOW - timedelta(hours=25)
        result = _pub_date(_iso(dt))
        assert "Yesterday" in result

    def test_3_days_ago_shows_d_ago(self):
        dt = NOW - timedelta(days=3)
        result = _pub_date(_iso(dt))
        assert "d ago" in result

    def test_more_than_7_days_returns_date_only(self):
        dt = NOW - timedelta(days=10)
        result = _pub_date(_iso(dt))
        assert "ago" not in result
        assert "·" not in result


class TestPubDatePriorYear:
    def test_prior_year_includes_year_in_label(self):
        dt = datetime(2025, 1, 15, tzinfo=timezone.utc)
        result = _pub_date(_iso(dt))
        assert "2025" in result

    def test_current_year_omits_year(self):
        dt = NOW - timedelta(days=10)
        result = _pub_date(_iso(dt))
        assert str(NOW.year) not in result


class TestPubDateZSuffix:
    def test_z_suffix_parsed_correctly(self):
        dt = NOW - timedelta(hours=2)
        iso_z = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = _pub_date(iso_z)
        assert "h ago" in result


class TestPubDateInvalidInput:
    def test_unparseable_date_returns_first_ten_chars(self):
        result = _pub_date("not-a-date-string")
        assert result == "not-a-date"

    def test_partial_iso_string_does_not_raise(self):
        result = _pub_date("2026-05-15T")
        assert result  # some output, not crash
