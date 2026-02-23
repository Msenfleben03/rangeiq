"""Barttorvik T-Rank Scraper Pipeline.

Scrapes live T-Rank ratings from barttorvik.com when the cbbdata.com API
is unavailable (e.g., no 2026 data). Implements a tiered fallback:

1. Try cbbdata API (existing barttorvik_fetcher.py)
2. Try curl_cffi (fast HTTP with Chrome TLS fingerprinting)
3. Fall back to SeleniumBase UC Mode (real browser, if installed)

Output matches the existing cache format (parquet) so all downstream code
(lookup_team_ratings, compute_barttorvik_differentials) works unchanged.

Usage:
    from pipelines.barttorvik_scraper import scrape_and_cache
    df = scrape_and_cache(2026)  # Returns DataFrame of today's ratings
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRANK_URL = "https://barttorvik.com/trank.php"
DEFAULT_CACHE_DIR = Path("data/external/barttorvik")

# Rate limiting — respect the site
MIN_REQUEST_DELAY = 5.0  # seconds between requests

# Column mapping from HTML table indices to our standard columns
# Header row: Rk(0), Team(1), Conf(2), G(3), Rec(4), AdjOE(5), AdjDE(6),
#   Barthag(7), ... Adj T.(22), WAB(23)
COLUMN_INDICES = {
    "rank": 0,
    "team": 1,
    "conf": 2,
    "adj_o": 5,
    "adj_d": 6,
    "barthag": 7,
    "adj_tempo": 22,
    "wab": 23,
}

# Standard output columns matching barttorvik_fetcher.py format
OUTPUT_COLUMNS = [
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
]


# ---------------------------------------------------------------------------
# HTML Parsing
# ---------------------------------------------------------------------------


def _extract_cell_value(td: Any) -> str:
    """Extract clean value from a table cell, removing rank subscripts.

    Barttorvik embeds rank indicators as <span class="lowrow"> after a <br/>.
    For example: ``127.1<br/><span class="lowrow">5</span>`` shows "127.1"
    as the value and "5" as the rank. We remove the rank spans first.

    Args:
        td: BeautifulSoup Tag for a <td> element.

    Returns:
        Clean text content of the cell.
    """
    # Work on a copy to avoid mutating the original soup
    from copy import copy

    td_copy = copy(td)
    for span in td_copy.find_all("span", class_="lowrow"):
        span.decompose()
    for br in td_copy.find_all("br"):
        br.decompose()
    return td_copy.get_text(strip=True)


def _extract_team_name(td: Any) -> str:
    """Extract clean team name from the Team column.

    Prefers the ``href`` parameter (``team.php?team=Name&year=YYYY``)
    because it uses proper names with spaces and dots (e.g., "Iowa St.").
    The ``td id`` attribute uses underscores ("Iowa_St_") which don't
    match our existing cache format.

    Args:
        td: BeautifulSoup Tag for the Team column <td>.

    Returns:
        Clean team name string.
    """
    # Prefer href parameter — uses canonical names with spaces/dots
    a_tag = td.find("a")
    if a_tag and a_tag.get("href"):
        params = parse_qs(urlparse(a_tag["href"]).query)
        team_list = params.get("team", [])
        if team_list:
            return team_list[0]

    # Fallback: td id attribute (may use underscores)
    td_id = td.get("id")
    if td_id and isinstance(td_id, str) and td_id.strip():
        return td_id.strip()

    # Last resort: raw text (may contain game info)
    return td.get_text(strip=True)


def parse_trank_html(html: str, year: int) -> pd.DataFrame:
    """Parse barttorvik.com trank.php HTML into a ratings DataFrame.

    Args:
        html: Raw HTML string from trank.php.
        year: Season year (e.g., 2026).

    Returns:
        DataFrame with columns matching OUTPUT_COLUMNS.
        Empty DataFrame if parsing fails.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 not installed: pip install beautifulsoup4")
        return pd.DataFrame()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        logger.warning("No table found in HTML")
        return pd.DataFrame()

    tbody = table.find("tbody")
    if tbody is None:
        logger.warning("No tbody found in table")
        return pd.DataFrame()

    rows = tbody.find_all("tr")
    if not rows:
        logger.warning("No data rows found in table body")
        return pd.DataFrame()

    records: list[dict[str, Any]] = []
    today_str = date.today().isoformat()

    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 24:
            continue

        try:
            team_name = _extract_team_name(tds[COLUMN_INDICES["team"]])
            rank_str = _extract_cell_value(tds[COLUMN_INDICES["rank"]])
            conf = _extract_cell_value(tds[COLUMN_INDICES["conf"]])
            adj_o_str = _extract_cell_value(tds[COLUMN_INDICES["adj_o"]])
            adj_d_str = _extract_cell_value(tds[COLUMN_INDICES["adj_d"]])
            barthag_str = _extract_cell_value(tds[COLUMN_INDICES["barthag"]])
            adj_tempo_str = _extract_cell_value(tds[COLUMN_INDICES["adj_tempo"]])
            wab_str = _extract_cell_value(tds[COLUMN_INDICES["wab"]])

            records.append(
                {
                    "rank": _safe_int(rank_str),
                    "team": team_name,
                    "conf": conf,
                    "barthag": _safe_float(barthag_str),
                    "adj_o": _safe_float(adj_o_str),
                    "adj_d": _safe_float(adj_d_str),
                    "adj_tempo": _safe_float(adj_tempo_str),
                    "wab": _safe_float(wab_str),
                    "year": year,
                    "date": today_str,
                }
            )
        except (IndexError, ValueError) as exc:
            logger.debug("Skipping row: %s", exc)
            continue

    if not records:
        logger.warning("No valid rows parsed from HTML")
        return pd.DataFrame()

    df = pd.DataFrame(records, columns=OUTPUT_COLUMNS)

    # Coerce types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")
    for col in ("adj_o", "adj_d", "adj_tempo", "barthag", "wab"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values(["rank", "team"]).reset_index(drop=True)

    logger.info("Parsed %d teams from trank.php for season %d", len(df), year)
    return df


def _safe_float(s: str) -> float | None:
    """Convert string to float, handling leading +/- and empty strings."""
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        # Try stripping non-numeric suffixes (e.g., rank numbers concatenated)
        match = re.match(r"([+-]?\d*\.?\d+)", s)
        if match:
            return float(match.group(1))
        return None


def _safe_int(s: str) -> int | None:
    """Convert string to int, returning None on failure."""
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        match = re.match(r"(\d+)", s)
        if match:
            return int(match.group(1))
        return None


# ---------------------------------------------------------------------------
# Scraping Methods
# ---------------------------------------------------------------------------


def scrape_with_curl_cffi(year: int) -> str | None:
    """Fetch trank.php HTML using curl_cffi with Chrome TLS impersonation.

    Barttorvik uses a simple JS verification (form POST) rather than full
    Cloudflare Turnstile. curl_cffi can handle this by:
    1. GET to establish session
    2. POST with js_test_submitted=1 to pass verification

    Args:
        year: Season year.

    Returns:
        HTML string or None if request fails.
    """
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        logger.warning("curl_cffi not installed: pip install curl-cffi")
        return None

    url = f"{TRANK_URL}?year={year}"

    try:
        session = curl_requests.Session(impersonate="chrome131")

        # Step 1: GET to establish cookies and get JS verification page
        session.get(url, timeout=15)

        # Step 2: POST to pass JS verification
        response = session.post(url, data={"js_test_submitted": "1"}, timeout=30)

        if response.status_code != 200:
            logger.warning("curl_cffi got status %d for %s", response.status_code, url)
            return None

        html = response.text
        if len(html) < 10000:
            # Likely still a challenge page
            logger.warning("Response too small (%d bytes), likely blocked", len(html))
            return None

        logger.info("curl_cffi fetched %d bytes from %s", len(html), url)
        return html

    except Exception as exc:
        logger.warning("curl_cffi request failed: %s", exc)
        return None


def scrape_with_seleniumbase(year: int) -> str | None:
    """Fetch trank.php HTML using SeleniumBase UC Mode (real browser).

    This is the fallback when curl_cffi is blocked. SeleniumBase UC Mode
    uses undetected-chromedriver to bypass Cloudflare.

    Args:
        year: Season year.

    Returns:
        HTML string or None if browser automation fails.

    Note:
        Requires seleniumbase and Chrome/Chromium installed.
    """
    try:
        from seleniumbase import SB
    except ImportError:
        logger.warning("seleniumbase not installed: pip install seleniumbase")
        return None

    url = f"{TRANK_URL}?year={year}"

    try:
        with SB(uc=True, headless=True) as sb:
            sb.open(url)
            sb.sleep(3)  # Wait for page to load / JS verification
            # Wait for the table to appear
            sb.wait_for_element("table", timeout=15)
            html = sb.get_page_source()

            if len(html) < 10000:
                logger.warning("SeleniumBase page too small (%d bytes)", len(html))
                return None

            logger.info("SeleniumBase fetched %d bytes from %s", len(html), url)
            return html

    except Exception as exc:
        logger.warning("SeleniumBase failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Cache Integration
# ---------------------------------------------------------------------------


def _cache_path(season: int, cache_dir: Path) -> Path:
    """Return the parquet cache file path for a season."""
    return cache_dir / f"barttorvik_ratings_{season}.parquet"


def _date_already_cached(season: int, target_date: date, cache_dir: Path) -> bool:
    """Check if ratings for a specific date are already cached.

    Args:
        season: Season year.
        target_date: Date to check.
        cache_dir: Cache directory.

    Returns:
        True if the date is already in the cache.
    """
    path = _cache_path(season, cache_dir)
    if not path.exists():
        return False

    try:
        existing = pd.read_parquet(path)
        if "date" not in existing.columns:
            return False
        existing["date"] = pd.to_datetime(existing["date"])
        target_dt = pd.Timestamp(target_date)
        return (existing["date"].dt.date == target_dt.date()).any()
    except Exception:
        return False


def append_to_cache(
    new_df: pd.DataFrame,
    season: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Append today's scraped ratings to the existing season cache.

    Deduplicates by (team, date) to ensure idempotent appends.

    Args:
        new_df: New ratings DataFrame to append.
        season: Season year.
        cache_dir: Cache directory.

    Returns:
        Path to the updated cache file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(season, cache_dir)

    if path.exists():
        existing = pd.read_parquet(path)
        existing["date"] = pd.to_datetime(existing["date"])
        new_df["date"] = pd.to_datetime(new_df["date"])
        combined = pd.concat([existing, new_df], ignore_index=True)
        # Deduplicate: keep latest entry per (team, date)
        combined = combined.drop_duplicates(subset=["team", "date"], keep="last")
        combined = combined.sort_values(["date", "team"]).reset_index(drop=True)
    else:
        combined = new_df.copy()

    combined.to_parquet(path, index=False)
    logger.info(
        "Cache updated: %d total ratings for season %d at %s",
        len(combined),
        season,
        path,
    )
    return path


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


def scrape_and_cache(
    year: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
    method: str | None = None,
) -> pd.DataFrame:
    """Scrape Barttorvik ratings and append to cache.

    Tiered fallback:
    1. Check if today's data is already cached (skip unless force=True)
    2. Try cbbdata API (existing fetcher, in case it resumes)
    3. Try curl_cffi (fast HTTP with TLS fingerprinting)
    4. Try SeleniumBase UC Mode (real browser fallback)

    Args:
        year: Season year (e.g., 2026).
        cache_dir: Directory for parquet cache files.
        force: If True, scrape even if today is already cached.
        method: Force a specific method: "api", "curl", "browser", or None for auto.

    Returns:
        DataFrame with today's ratings (or empty if all methods fail).
    """
    today = date.today()

    # Check if already cached
    if not force and _date_already_cached(year, today, cache_dir):
        logger.info("Today's ratings already cached for season %d", year)
        path = _cache_path(year, cache_dir)
        return pd.read_parquet(path)

    html: str | None = None

    # Method 1: Try cbbdata API (in case it resumes)
    if method is None or method == "api":
        html_from_api = _try_cbbdata_api(year, cache_dir)
        if html_from_api is not None:
            return html_from_api

    # Method 2: curl_cffi
    if method is None or method == "curl":
        logger.info("Trying curl_cffi for season %d...", year)
        html = scrape_with_curl_cffi(year)

    # Method 3: SeleniumBase
    if html is None and (method is None or method == "browser"):
        logger.info("Trying SeleniumBase for season %d...", year)
        time.sleep(MIN_REQUEST_DELAY)
        html = scrape_with_seleniumbase(year)

    if html is None:
        logger.error(
            "All scraping methods failed for season %d. "
            "Consider installing seleniumbase or using a proxy.",
            year,
        )
        return pd.DataFrame()

    # Parse HTML
    df = parse_trank_html(html, year)
    if df.empty:
        logger.error("HTML parsing returned no data for season %d", year)
        return pd.DataFrame()

    # Append to cache
    append_to_cache(df, year, cache_dir)
    return df


def _try_cbbdata_api(year: int, cache_dir: Path) -> pd.DataFrame | None:
    """Try fetching from cbbdata API (returns DataFrame or None)."""
    try:
        from pipelines.barttorvik_fetcher import BarttovikFetcher

        import os

        api_key = os.environ.get("CBBDATA_API_KEY", "")
        if not api_key:
            logger.debug("No CBBDATA_API_KEY set, skipping API attempt")
            return None

        fetcher = BarttovikFetcher(api_key=api_key, cache_dir=cache_dir)
        df = fetcher.fetch_season(year, use_cache=False)

        if df.empty:
            logger.info("cbbdata API returned empty for season %d", year)
            return None

        logger.info("cbbdata API succeeded for season %d (%d ratings)", year, len(df))
        return df

    except Exception as exc:
        logger.debug("cbbdata API failed: %s", exc)
        return None
