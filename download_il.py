"""
Copyright (c) 2024 Jim Maastricht

Scrape the CBS Sports MLB injury report and save to CSV.

The report groups injured players by team and includes a comment such as "Expected to be out until at least Feb 1".
That expected date is used as the simulated return date. Comments without a usable date fall back to estimates
based on the comment text.

Usage:
    uv run download_il.py
    uv run download_il.py --season 2026
    uv run download_il.py --output my_il_report.csv
"""

import argparse
import csv
import random
import re
import sys
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

CBS_URL = "https://www.cbssports.com/mlb/injuries/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# CBS team codes that differ from the abbreviations used in the sim data
CBS_TEAM_CODES = {"KC": "KCR", "SD": "SDP", "SF": "SFG", "TB": "TBR", "WAS": "WSN"}

CSV_COLUMNS = [
    "Player",
    "Team",
    "Position",
    "Injury",
    "Date",
    "Latest Update",
    "Sim Return Date",
    "Sim Return Reason",
]

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}  # fmt: skip

# "Feb 1", "Feb. 1", "February 1, 2028"
EXPECTED_DATE_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:,\s*(\d{4}))?", re.I)
UPDATED_DATE_RE = re.compile(r"^(?:(\w{3}),\s*)?(\w{3})\w*\.?\s+(\d{1,2})$")  # "Mon, Oct 5"


def fetch_injury_data() -> list[dict]:
    """Fetch and parse the CBS Sports injury report.

    The page is server rendered HTML with one table per team. No browser automation needed.

    Returns:
        List of injury record dicts (see parse_injury_html).
    """
    resp = requests.get(CBS_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return parse_injury_html(resp.text)


def parse_injury_html(html: str) -> list[dict]:
    """Parse the CBS injury report page into one record per injured player.

    Args:
        html: Page HTML.

    Returns:
        List of dicts with keys: player, team, position, updated, injury, comment.
        Team is the sim abbreviation (e.g. KCR, not CBS's KC).
    """
    soup = BeautifulSoup(html, "html.parser")
    team_blocks = soup.select("div.TableBaseWrapper")
    if not team_blocks:
        print("ERROR: Could not find any team injury tables in page, has the CBS layout changed?", file=sys.stderr)
        sys.exit(1)

    injuries = []
    for block in team_blocks:
        team_link = block.select_one("h4 a[href*='/mlb/teams/']")
        if team_link is None:
            continue
        cbs_code = team_link["href"].split("/")[3]
        team = CBS_TEAM_CODES.get(cbs_code, cbs_code)

        for row in block.select("tbody tr.TableBase-bodyTr"):
            cells = row.select("td")
            if len(cells) < 5:
                continue
            name_tag = cells[0].select_one(".CellPlayerName--long") or cells[0]
            injuries.append(
                {
                    "player": name_tag.get_text(strip=True),
                    "team": team,
                    "position": cells[1].get_text(strip=True),
                    "updated": cells[2].get_text(strip=True),
                    "injury": cells[3].get_text(strip=True),
                    "comment": cells[4].get_text(strip=True),
                }
            )
    return injuries


def parse_updated_date(updated: str, today: Optional[datetime] = None) -> Optional[datetime]:
    """Parse the report's year-less "Mon, Oct 5" date, using the weekday to work out the year.

    Args:
        updated: Updated text from the report.
        today: Reference date, defaults to now.

    Returns:
        The date, or None if it can't be parsed.
    """
    today = today or datetime.now()
    match = UPDATED_DATE_RE.match(updated.strip())
    if not match or match.group(2).lower() not in MONTHS:
        return None
    weekday, month, day = match.group(1), MONTHS[match.group(2).lower()], int(match.group(3))

    candidates = []
    for year in (today.year, today.year - 1, today.year + 1):
        try:
            candidates.append(datetime(year, month, day))
        except ValueError:  # e.g. Feb 29 in a non leap year
            continue
    if weekday:
        for candidate in candidates:
            if candidate.strftime("%a").lower() == weekday.lower():
                return candidate
    past = [c for c in candidates if c <= today]
    return max(past) if past else None


def parse_expected_return(comment: str, updated_date: Optional[datetime], today: Optional[datetime] = None):
    """Pull the expected return date out of a comment like "Expected to be out until at least Feb 1".

    A year in the comment is used as is. Otherwise it's the first occurrence of that month and day on or after the
    date the report was updated (or today if the update date is unknown).

    Returns:
        Tuple of (date, date text as written), or (None, None) if the comment has no date.
    """
    match = EXPECTED_DATE_RE.search(comment)
    if not match:
        return None, None
    month, day, year = MONTHS[match.group(1).lower()], int(match.group(2)), match.group(3)
    text = match.group(0).strip()

    try:
        if year:
            return datetime(int(year), month, day), text
        anchor = updated_date or today or datetime.now()
        expected = datetime(anchor.year, month, day)
        if expected < anchor:
            expected = datetime(anchor.year + 1, month, day)
        return expected, text
    except ValueError:  # invalid day for the month
        return None, None


def calculate_sim_return_date(
    record: dict, season: int = 2026, today: Optional[datetime] = None
) -> tuple[str, str]:
    """Calculate the simulated return date for an injured player.

    Logic:
    - Comment has an expected return date in the future → use it
    - Comment has an expected return date that has already passed → random 1-14 days
    - No date in the comment → estimate from the text:
      - "out for season" → start of next season
      - weeks / months mentioned → that long, with some randomness
      - "shut down" → 4-6 weeks
      - "day-to-day" / "no timetable" → random 1-14 days
      - a month named in full → end of that month
      - anything else → random 1-14 days

    Args:
        record: Injury record dict from parse_injury_html.
        season: Season year.
        today: Reference date, defaults to now.

    Returns:
        Tuple of (sim_return_date, sim_return_reason) as MM/DD/YY strings.
    """
    today = today or datetime.now()
    comment = record.get("comment") or ""
    latest_update = comment.lower()

    updated_date = parse_updated_date(record.get("updated", ""), today)
    expected_date, expected_text = parse_expected_return(comment, updated_date, today)
    if expected_date:
        if expected_date > today:
            return (expected_date.strftime("%m/%d/%y"), f"CBS expected return ({expected_text})")
        days = random.randint(1, 14)
        return ((today + timedelta(days=days)).strftime("%m/%d/%y"), f"Expected return passed, sim {days} days")

    # Season-ending injuries (e.g. surgery) shouldn't make a player available again for the postseason or as soon
    # as the following offseason simulation begins, so they return when next season starts.
    if any(phrase in latest_update for phrase in ["out for season", "out for the season", f"out for {season}"]):
        next_season_start = datetime(season + 1, 1, 1)
        return (next_season_start.strftime("%m/%d/%y"), "Out for season")

    # Check for specific timeline mentions (weeks/months)
    weeks_match = re.search(r"(\d+)-?(\d*)\s*weeks?", latest_update)
    months_match = re.search(r"(\d+)-?(\d*)\s*months?", latest_update)

    if weeks_match:
        # Use the higher number if range, or the single number
        weeks = int(weeks_match.group(2) or weeks_match.group(1))
        # Add some randomness: +/- 25%
        weeks = max(1, int(weeks * random.uniform(0.75, 1.25)))
        return_date = today + timedelta(weeks=weeks)
        return (return_date.strftime("%m/%d/%y"), f"~{weeks} weeks (from update)")

    if months_match:
        months = int(months_match.group(2) or months_match.group(1))
        # Add some randomness: +/- 1 month
        months = max(1, months + random.randint(-1, 1))
        return_date = today + timedelta(days=months * 30)
        return (return_date.strftime("%m/%d/%y"), f"~{months} months (from update)")

    # Check for "shut down" — assume 4-6 weeks
    if "shut down" in latest_update:
        weeks = random.randint(4, 6)
        return_date = today + timedelta(weeks=weeks)
        return (return_date.strftime("%m/%d/%y"), f"Shut down ~{weeks} weeks")

    # Check for "no timetable" or similar — assign 1-14 days (random)
    if any(phrase in latest_update for phrase in ["no timetable", "no timeline", "day-to-day", "tbd"]):
        days = random.randint(1, 14)
        return_date = today + timedelta(days=days)
        return (return_date.strftime("%m/%d/%y"), f"No timetable, sim {days} days")

    # Check for "out until" with a month named in full
    for month_name, month_num in MONTH_NAMES.items():
        if month_name in latest_update:
            # Assume end of that month
            return_date = datetime(season, month_num, 28)
            if return_date < today:
                return_date = today + timedelta(days=random.randint(1, 14))
            return (return_date.strftime("%m/%d/%y"), f"Out until {month_name}")

    # Default: random 1-14 days (conservative estimate for unspecified returns)
    days = random.randint(1, 14)
    return_date = today + timedelta(days=days)
    return (return_date.strftime("%m/%d/%y"), f"Default sim {days} days")


def format_rows(injuries: list[dict], season: int = 2026, today: Optional[datetime] = None) -> list[dict]:
    """Format injury records into clean CSV rows.

    Args:
        injuries: Injury records from parse_injury_html.
        season: Season year for date calculations.
        today: Reference date, defaults to now.

    Returns:
        List of dicts ready for CSV writer.
    """
    today = today or datetime.now()
    rows = []
    for r in injuries:
        sim_return_date, sim_return_reason = calculate_sim_return_date(r, season, today)
        updated_date = parse_updated_date(r.get("updated", ""), today)
        rows.append(
            {
                "Player": r["player"],
                "Team": r["team"],
                "Position": r["position"],
                "Injury": r["injury"],
                "Date": updated_date.strftime("%m/%d/%y") if updated_date else r.get("updated", ""),
                "Latest Update": r["comment"],
                "Sim Return Date": sim_return_date,
                "Sim Return Reason": sim_return_reason,
            }
        )
    # Sort by team, then position, then player name
    rows.sort(key=lambda r: (r["Team"], r["Position"], r["Player"]))
    return rows


def write_csv(rows: list[dict], output_path: str):
    """Write formatted rows to CSV.

    Args:
        rows: Formatted row dicts.
        output_path: Output file path.
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Scrape the CBS Sports MLB injury report to CSV")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path (default: il_report_YYYY.csv)")
    args = parser.parse_args()

    output_path = args.output or f"il_report_{args.season}.csv"

    print(f"Fetching CBS Sports injury report for {args.season}...")
    injuries = fetch_injury_data()
    print(f"  Found {len(injuries)} injured players")

    rows = format_rows(injuries, args.season)
    write_csv(rows, output_path)
    print(f"  Saved to {output_path}")


if __name__ == "__main__":
    main()
