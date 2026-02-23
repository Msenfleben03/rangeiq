"""Tests for Barttorvik T-Rank scraper pipeline.

Tests cover:
- HTML parsing (parse_trank_html) with realistic fixture
- Cell value extraction (rank subscript removal)
- Team name extraction (from td id, href, raw text)
- Cache append logic (idempotent, no date duplicates)
- Fallback chain (API empty → curl → browser)
- Edge cases (empty HTML, no table, missing columns)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from pipelines.barttorvik_scraper import (
    _date_already_cached,
    _safe_float,
    _safe_int,
    append_to_cache,
    parse_trank_html,
    scrape_and_cache,
)


# ---------------------------------------------------------------------------
# HTML Fixture — matches real barttorvik.com trank.php structure
# ---------------------------------------------------------------------------

SAMPLE_TRANK_HTML = """<!DOCTYPE html>
<html><head><title>T-Rank</title></head>
<body>
<table>
<thead>
<tr><th>Rk</th><th>Team</th><th>Conf</th><th>G</th><th>Rec</th>
<th>AdjOE</th><th>AdjDE</th><th>Barthag</th>
<th>EFG%</th><th>EFGD%</th><th>TOR</th><th>TORD</th>
<th>ORB</th><th>DRB</th><th>FTR</th><th>FTRD</th>
<th>2P%</th><th>2P%D</th><th>3P%</th><th>3P%D</th>
<th>3PR</th><th>3PRD</th><th>Adj T.</th><th>WAB</th></tr>
</thead>
<tbody>
<tr>
<td class="lowrowclick" style="text-align:center">1</td>
<td class="teamname" id="Houston"><a href="team.php?team=Houston&amp;year=2026">Houston</a></td>
<td style="text-align:center"><a href="conf.php?conf=B12&amp;year=2026">B12</a></td>
<td>26</td><td>23-3</td>
<td class="1" style="background-color:#A8DAB6">127.1<br/><span class="lowrow" style="font-size:8px;">5</span></td>
<td class="2" style="background-color:#A7DAB6">92.1<br/><span class="lowrow" style="font-size:8px;">4</span></td>
<td class="3">.9761<br/><span class="lowrow" style="font-size:8px;">2</span></td>
<td>52.4</td><td>46.4</td><td>12.6</td><td>22.0</td>
<td>36.8</td><td>31.1</td><td>26.2</td><td>39.4</td>
<td>53.2</td><td>45.8</td><td>34.1</td><td>31.5</td>
<td>41.9</td><td>42.8</td>
<td class="26" style="background-color:#F9A8AA">63.0<br/><span class="lowrow" style="font-size:8px;">355</span></td>
<td class="34" style="background-color:#ABDCB9">+7.1<br/><span class="lowrow" style="font-size:8px;">5</span></td>
</tr>
<tr>
<td class="lowrowclick" style="text-align:center">2</td>
<td class="teamname" id="Duke"><a href="team.php?team=Duke&amp;year=2026">Duke</a></td>
<td style="text-align:center">ACC</td>
<td>26</td><td>24-2</td>
<td class="1">125.8<br/><span class="lowrow">9</span></td>
<td class="2">92.3<br/><span class="lowrow">5</span></td>
<td class="3">.9724<br/><span class="lowrow">5</span></td>
<td>57.8</td><td>46.2</td><td>15.9</td><td>19.0</td>
<td>36.8</td><td>25.4</td><td>38.0</td><td>22.2</td>
<td>62.0</td><td>45.9</td><td>34.9</td><td>31.0</td>
<td>43.8</td><td>44.8</td>
<td class="26">66.1<br/><span class="lowrow">250</span></td>
<td class="34">+8.8<br/><span class="lowrow">2</span></td>
</tr>
<tr>
<td class="lowrowclick" style="text-align:center">3</td>
<td class="teamname" id="Iowa St."><a href="team.php?team=Iowa+St.&amp;year=2026">Iowa St.</a></td>
<td style="text-align:center">B12</td>
<td>26</td><td>22-4</td>
<td class="1">118.5<br/><span class="lowrow">30</span></td>
<td class="2">86.2<br/><span class="lowrow">1</span></td>
<td class="3">.9710<br/><span class="lowrow">6</span></td>
<td>51.2</td><td>41.8</td><td>16.3</td><td>21.5</td>
<td>34.2</td><td>27.8</td><td>35.5</td><td>30.2</td>
<td>54.1</td><td>40.5</td><td>31.2</td><td>28.8</td>
<td>39.1</td><td>40.2</td>
<td class="26">64.5<br/><span class="lowrow">310</span></td>
<td class="34">+6.2<br/><span class="lowrow">8</span></td>
</tr>
</tbody>
</table>
</body></html>"""

# HTML with embedded game info in team names (teams playing today)
SAMPLE_TRANK_HTML_GAMEDAY = """<!DOCTYPE html>
<html><head><title>T-Rank</title></head>
<body>
<table>
<thead>
<tr><th>Rk</th><th>Team</th><th>Conf</th><th>G</th><th>Rec</th>
<th>AdjOE</th><th>AdjDE</th><th>Barthag</th>
<th>EFG%</th><th>EFGD%</th><th>TOR</th><th>TORD</th>
<th>ORB</th><th>DRB</th><th>FTR</th><th>FTRD</th>
<th>2P%</th><th>2P%D</th><th>3P%</th><th>3P%D</th>
<th>3PR</th><th>3PRD</th><th>Adj T.</th><th>WAB</th></tr>
</thead>
<tbody>
<tr>
<td>1</td>
<td class="teamname" id="Michigan"><a href="team.php?team=Michigan&amp;year=2026">Michigan(A) 8 Purdue (won)</a></td>
<td>B10</td>
<td>26</td><td>25-1</td>
<td>129.0</td><td>90.3</td><td>.9837</td>
<td>59.0</td><td>43.2</td><td>16.7</td><td>16.4</td>
<td>36.9</td><td>28.3</td><td>39.9</td><td>27.1</td>
<td>62.6</td><td>42.8</td><td>36.1</td><td>29.2</td>
<td>42.2</td><td>41.7</td>
<td>72.2</td>
<td>+10.4</td>
</tr>
</tbody>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Tests: HTML Parsing
# ---------------------------------------------------------------------------


class TestParseTrankHtml:
    """Test parse_trank_html with fixtures."""

    def test_basic_parsing(self):
        """Parse standard HTML returns correct team count."""
        df = parse_trank_html(SAMPLE_TRANK_HTML, 2026)
        assert len(df) == 3
        assert set(df["team"]) == {"Houston", "Duke", "Iowa St."}

    def test_correct_columns(self):
        """Output has all expected columns."""
        df = parse_trank_html(SAMPLE_TRANK_HTML, 2026)
        expected_cols = {
            "rank",
            "team",
            "conf",
            "barthag",
            "adj_o",
            "adj_d",
            "adj_tempo",
            "wab",
            "year",
            "date",
        }
        assert set(df.columns) == expected_cols

    def test_numeric_values_no_rank_subscripts(self):
        """AdjOE/AdjDE/etc. don't include rank subscript numbers."""
        df = parse_trank_html(SAMPLE_TRANK_HTML, 2026)
        houston = df[df["team"] == "Houston"].iloc[0]
        assert houston["adj_o"] == pytest.approx(127.1, abs=0.1)
        assert houston["adj_d"] == pytest.approx(92.1, abs=0.1)
        assert houston["barthag"] == pytest.approx(0.9761, abs=0.001)
        assert houston["adj_tempo"] == pytest.approx(63.0, abs=0.1)
        assert houston["wab"] == pytest.approx(7.1, abs=0.1)

    def test_rank_is_integer(self):
        """Rank column is integer type."""
        df = parse_trank_html(SAMPLE_TRANK_HTML, 2026)
        assert df["rank"].dtype.name == "Int64"
        assert df[df["team"] == "Houston"]["rank"].iloc[0] == 1

    def test_year_column(self):
        """Year column matches input."""
        df = parse_trank_html(SAMPLE_TRANK_HTML, 2026)
        assert (df["year"] == 2026).all()

    def test_date_is_today(self):
        """Date column is today's date."""
        df = parse_trank_html(SAMPLE_TRANK_HTML, 2026)
        today = pd.Timestamp(date.today())
        assert (df["date"].dt.date == today.date()).all()

    def test_conference_parsing(self):
        """Conference names are correctly parsed."""
        df = parse_trank_html(SAMPLE_TRANK_HTML, 2026)
        houston = df[df["team"] == "Houston"].iloc[0]
        assert houston["conf"] == "B12"
        duke = df[df["team"] == "Duke"].iloc[0]
        assert duke["conf"] == "ACC"

    def test_gameday_team_names_cleaned(self):
        """Teams with game info embedded still get clean names."""
        df = parse_trank_html(SAMPLE_TRANK_HTML_GAMEDAY, 2026)
        assert len(df) == 1
        assert df.iloc[0]["team"] == "Michigan"

    def test_empty_html_returns_empty_df(self):
        """Empty HTML input returns empty DataFrame."""
        df = parse_trank_html("", 2026)
        assert df.empty

    def test_no_table_returns_empty_df(self):
        """HTML without a table returns empty DataFrame."""
        df = parse_trank_html("<html><body>No table here</body></html>", 2026)
        assert df.empty

    def test_no_tbody_returns_empty_df(self):
        """Table without tbody returns empty DataFrame."""
        html = "<html><body><table><thead><tr><th>X</th></tr></thead></table></body></html>"
        df = parse_trank_html(html, 2026)
        assert df.empty


# ---------------------------------------------------------------------------
# Tests: Cell Value Extraction Helpers
# ---------------------------------------------------------------------------


class TestCellExtraction:
    """Test _extract_cell_value and _extract_team_name."""

    def test_safe_float_normal(self):
        assert _safe_float("127.1") == pytest.approx(127.1)

    def test_safe_float_positive(self):
        assert _safe_float("+7.1") == pytest.approx(7.1)

    def test_safe_float_negative(self):
        assert _safe_float("-3.5") == pytest.approx(-3.5)

    def test_safe_float_empty(self):
        assert _safe_float("") is None

    def test_safe_float_with_junk(self):
        """String with trailing non-numeric characters."""
        assert _safe_float("127.1abc") == pytest.approx(127.1)

    def test_safe_int_normal(self):
        assert _safe_int("42") == 42

    def test_safe_int_empty(self):
        assert _safe_int("") is None

    def test_safe_int_with_junk(self):
        assert _safe_int("42abc") == 42


# ---------------------------------------------------------------------------
# Tests: Cache Logic
# ---------------------------------------------------------------------------


class TestCacheLogic:
    """Test append_to_cache and _date_already_cached."""

    def test_append_creates_new_file(self, tmp_path):
        """Appending to non-existent cache creates new file."""
        df = pd.DataFrame(
            {
                "rank": [1, 2],
                "team": ["Houston", "Duke"],
                "conf": ["B12", "ACC"],
                "barthag": [0.97, 0.96],
                "adj_o": [127.0, 125.0],
                "adj_d": [92.0, 93.0],
                "adj_tempo": [63.0, 66.0],
                "wab": [7.0, 8.0],
                "year": [2026, 2026],
                "date": ["2026-02-17", "2026-02-17"],
            }
        )
        df["date"] = pd.to_datetime(df["date"])

        path = append_to_cache(df, 2026, tmp_path)
        assert path.exists()
        result = pd.read_parquet(path)
        assert len(result) == 2

    def test_append_is_idempotent(self, tmp_path):
        """Appending same date twice doesn't create duplicates."""
        df = pd.DataFrame(
            {
                "rank": [1],
                "team": ["Houston"],
                "conf": ["B12"],
                "barthag": [0.97],
                "adj_o": [127.0],
                "adj_d": [92.0],
                "adj_tempo": [63.0],
                "wab": [7.0],
                "year": [2026],
                "date": ["2026-02-17"],
            }
        )
        df["date"] = pd.to_datetime(df["date"])

        append_to_cache(df, 2026, tmp_path)
        append_to_cache(df, 2026, tmp_path)

        result = pd.read_parquet(tmp_path / "barttorvik_ratings_2026.parquet")
        assert len(result) == 1  # No duplicate

    def test_append_adds_new_dates(self, tmp_path):
        """Appending different dates grows the cache."""
        df1 = pd.DataFrame(
            {
                "rank": [1],
                "team": ["Houston"],
                "conf": ["B12"],
                "barthag": [0.97],
                "adj_o": [127.0],
                "adj_d": [92.0],
                "adj_tempo": [63.0],
                "wab": [7.0],
                "year": [2026],
                "date": ["2026-02-17"],
            }
        )
        df2 = pd.DataFrame(
            {
                "rank": [1],
                "team": ["Houston"],
                "conf": ["B12"],
                "barthag": [0.975],
                "adj_o": [127.5],
                "adj_d": [91.5],
                "adj_tempo": [63.2],
                "wab": [7.5],
                "year": [2026],
                "date": ["2026-02-18"],
            }
        )
        df1["date"] = pd.to_datetime(df1["date"])
        df2["date"] = pd.to_datetime(df2["date"])

        append_to_cache(df1, 2026, tmp_path)
        append_to_cache(df2, 2026, tmp_path)

        result = pd.read_parquet(tmp_path / "barttorvik_ratings_2026.parquet")
        assert len(result) == 2  # Both dates present

    def test_date_already_cached_true(self, tmp_path):
        """Returns True when date is in cache."""
        df = pd.DataFrame(
            {
                "rank": [1],
                "team": ["Houston"],
                "conf": ["B12"],
                "barthag": [0.97],
                "adj_o": [127.0],
                "adj_d": [92.0],
                "adj_tempo": [63.0],
                "wab": [7.0],
                "year": [2026],
                "date": pd.to_datetime(["2026-02-17"]),
            }
        )
        path = tmp_path / "barttorvik_ratings_2026.parquet"
        df.to_parquet(path, index=False)

        assert _date_already_cached(2026, date(2026, 2, 17), tmp_path)

    def test_date_already_cached_false(self, tmp_path):
        """Returns False when date is not in cache."""
        df = pd.DataFrame(
            {
                "rank": [1],
                "team": ["Houston"],
                "conf": ["B12"],
                "barthag": [0.97],
                "adj_o": [127.0],
                "adj_d": [92.0],
                "adj_tempo": [63.0],
                "wab": [7.0],
                "year": [2026],
                "date": pd.to_datetime(["2026-02-17"]),
            }
        )
        path = tmp_path / "barttorvik_ratings_2026.parquet"
        df.to_parquet(path, index=False)

        assert not _date_already_cached(2026, date(2026, 2, 18), tmp_path)

    def test_date_already_cached_no_file(self, tmp_path):
        """Returns False when cache file doesn't exist."""
        assert not _date_already_cached(2026, date(2026, 2, 17), tmp_path)


# ---------------------------------------------------------------------------
# Tests: Fallback Chain
# ---------------------------------------------------------------------------


class TestFallbackChain:
    """Test scrape_and_cache fallback logic."""

    @patch("pipelines.barttorvik_scraper._try_cbbdata_api")
    @patch("pipelines.barttorvik_scraper.scrape_with_curl_cffi")
    def test_curl_cffi_used_when_api_fails(self, mock_curl, mock_api, tmp_path):
        """When API returns None, curl_cffi is tried."""
        mock_api.return_value = None
        mock_curl.return_value = SAMPLE_TRANK_HTML

        df = scrape_and_cache(2026, cache_dir=tmp_path, force=True)
        mock_curl.assert_called_once_with(2026)
        assert len(df) == 3

    @patch("pipelines.barttorvik_scraper.time.sleep")
    @patch("pipelines.barttorvik_scraper._try_cbbdata_api")
    @patch("pipelines.barttorvik_scraper.scrape_with_curl_cffi")
    @patch("pipelines.barttorvik_scraper.scrape_with_seleniumbase")
    def test_seleniumbase_used_when_curl_fails(
        self, mock_browser, mock_curl, mock_api, mock_sleep, tmp_path
    ):
        """When both API and curl_cffi fail, SeleniumBase is tried."""
        mock_api.return_value = None
        mock_curl.return_value = None
        mock_browser.return_value = SAMPLE_TRANK_HTML

        df = scrape_and_cache(2026, cache_dir=tmp_path, force=True)
        mock_browser.assert_called_once_with(2026)
        assert len(df) == 3

    @patch("pipelines.barttorvik_scraper.time.sleep")
    @patch("pipelines.barttorvik_scraper._try_cbbdata_api")
    @patch("pipelines.barttorvik_scraper.scrape_with_curl_cffi")
    @patch("pipelines.barttorvik_scraper.scrape_with_seleniumbase")
    def test_all_methods_fail_returns_empty(
        self, mock_browser, mock_curl, mock_api, mock_sleep, tmp_path
    ):
        """When all methods fail, returns empty DataFrame."""
        mock_api.return_value = None
        mock_curl.return_value = None
        mock_browser.return_value = None

        df = scrape_and_cache(2026, cache_dir=tmp_path, force=True)
        assert df.empty

    @patch("pipelines.barttorvik_scraper._try_cbbdata_api")
    def test_api_success_skips_scraping(self, mock_api, tmp_path):
        """When API succeeds, scraping methods are not called."""
        fake_df = pd.DataFrame({"team": ["Houston"], "year": [2026]})
        mock_api.return_value = fake_df

        df = scrape_and_cache(2026, cache_dir=tmp_path, force=True)
        assert len(df) == 1

    @patch("pipelines.barttorvik_scraper._try_cbbdata_api")
    @patch("pipelines.barttorvik_scraper.scrape_with_curl_cffi")
    def test_method_override_curl_only(self, mock_curl, mock_api, tmp_path):
        """method='curl' skips API and doesn't try browser."""
        mock_curl.return_value = SAMPLE_TRANK_HTML

        df = scrape_and_cache(2026, cache_dir=tmp_path, force=True, method="curl")
        mock_api.assert_not_called()
        mock_curl.assert_called_once()
        assert len(df) == 3

    @patch("pipelines.barttorvik_scraper._date_already_cached")
    @patch("pipelines.barttorvik_scraper._try_cbbdata_api")
    @patch("pipelines.barttorvik_scraper.scrape_with_curl_cffi")
    def test_skips_when_cached(self, mock_curl, mock_api, mock_cached, tmp_path):
        """When today is already cached, returns cached data without scraping."""
        mock_cached.return_value = True

        # Create a fake cached file
        df = pd.DataFrame(
            {
                "rank": [1],
                "team": ["Houston"],
                "conf": ["B12"],
                "barthag": [0.97],
                "adj_o": [127.0],
                "adj_d": [92.0],
                "adj_tempo": [63.0],
                "wab": [7.0],
                "year": [2026],
                "date": pd.to_datetime(["2026-02-17"]),
            }
        )
        path = tmp_path / "barttorvik_ratings_2026.parquet"
        df.to_parquet(path, index=False)

        result = scrape_and_cache(2026, cache_dir=tmp_path)
        mock_api.assert_not_called()
        mock_curl.assert_not_called()
        assert len(result) == 1
