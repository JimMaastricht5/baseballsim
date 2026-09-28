"""
Copyright (c) 2024 Jim Maastricht

Scrape FanGraphs injury report and save to CSV.

Usage:
    uv run download_il.py
    uv run download_il.py --season 2026
    uv run download_il.py --output my_il_report.csv
"""

import argparse
import csv
import json
import random
import re
import sys
from datetime import datetime, timedelta

import requests

FANGRAPHS_URL = "https://www.fangraphs.com/roster-resource/injury-report"

CSV_COLUMNS = [
    "Player",
    "Team",
    "Position",
    "Status",
    "Injury",
    "Date",
    "Eligible",
    "Return",
    "Latest Update",
    "Sim Return Date",
    "Sim Return Reason",
    "FG ID",
    "MLBAM ID",
]


def fetch_injury_data(season: int = 2026) -> list[dict]:
    """Fetch injury report data from FanGraphs.

    The page embeds all data as JSON inside a <script id="__NEXT_DATA__"> tag
    (Next.js server-side rendering). No browser automation needed.

    Args:
        season: MLB season year to fetch.

    Returns:
        List of injury record dicts.
    """
    params = {"groupby": "all", "timeframe": "current", "season": season}
    resp = requests.get(FANGRAPHS_URL, params=params, timeout=30)
    resp.raise_for_status()

    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text)
    if not match:
        print("ERROR: Could not find __NEXT_DATA__ JSON in page.", file=sys.stderr)
        sys.exit(1)

    page_data = json.loads(match.group(1))
    queries = page_data["props"]["pageProps"]["dehydratedState"]["queries"]

    # First query is injury data
    injuries = queries[0]["state"]["data"]
    return injuries


def filter_active_il(injuries: list[dict]) -> list[dict]:
    """Filter to only players currently on the IL (exclude activated).

    Args:
        injuries: Raw injury records from FanGraphs.

    Returns:
        Filtered list of active IL players.
    """
    return [r for r in injuries if r.get("status") != "Activated"]


def calculate_sim_return_date(record: dict, season: int = 2026) -> tuple[str, str]:
    """Calculate the simulated return date for a player on the IL.

    Logic:
    - If Return date exists → player already activated (should be filtered out)
    - If eligible date is in the future → use eligible date
    - If eligible date is in the past AND no return date → determine from Latest Update:
      - "Out for season" / "Out for 2026 season" → end of season
      - If there's a rehab/timeline → random 1-14 days
      - "No timetable for return" / similar → random 1-14 days

    Args:
        record: FanGraphs injury record dict.
        season: Season year.

    Returns:
        Tuple of (sim_return_date, sim_return_reason) as MM/DD/YY strings.
    """
    today = datetime.now()
    eligible_str = record.get("eligibledate", "")
    return_str = record.get("returndate", "")
    latest_update = (record.get("latestUpdate") or "").lower()

    # If already returned, shouldn't reach here (filtered out)
    if return_str:
        return (return_str, "Already returned")

    # Parse eligible date
    eligible_date = None
    if eligible_str:
        try:
            eligible_date = datetime.strptime(eligible_str, "%m/%d/%y")
        except ValueError:
            pass

    # If eligible date is in the future, use it
    if eligible_date and eligible_date > today:
        return (eligible_str, "Eligible date (future)")

    # Eligible date is in the past or missing — determine from latest update
    # Check for "out for season" type updates. These players won't return until
    # next season starts, not just the end of this year's regular season - a
    # season-ending injury (e.g. surgery) shouldn't make a player available again
    # for the postseason or as soon as the following offseason simulation begins.
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

    # Check for "out until" with a month mentioned
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for month_name, month_num in month_map.items():
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


def format_rows(injuries: list[dict], season: int = 2026) -> list[dict]:
    """Format injury records into clean CSV rows.

    Uses playerNameRoute for display (avoids encoding issues with accents).

    Args:
        injuries: Filtered injury records.
        season: Season year for date calculations.

    Returns:
        List of dicts ready for CSV writer.
    """
    rows = []
    for r in injuries:
        sim_return_date, sim_return_reason = calculate_sim_return_date(r, season)
        rows.append(
            {
                "Player": r.get("playerNameRoute") or r.get("playerName", ""),
                "Team": r.get("team", ""),
                "Position": r.get("position", ""),
                "Status": r.get("status", ""),
                "Injury": r.get("injurySurgery", ""),
                "Date": r.get("date", ""),
                "Eligible": r.get("eligibledate", ""),
                "Return": r.get("returndate", "") or "",
                "Latest Update": r.get("latestUpdate", ""),
                "Sim Return Date": sim_return_date,
                "Sim Return Reason": sim_return_reason,
                "FG ID": r.get("playerId", ""),
                "MLBAM ID": r.get("mlbamid", ""),
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
    parser = argparse.ArgumentParser(description="Scrape FanGraphs injury report to CSV")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path (default: il_report_YYYY.csv)")
    parser.add_argument("--all", action="store_true", help="Include activated players (default: active IL only)")
    args = parser.parse_args()

    output_path = args.output or f"il_report_{args.season}.csv"

    print(f"Fetching FanGraphs injury report for {args.season}...")
    injuries = fetch_injury_data(args.season)
    print(f"  Found {len(injuries)} total records")

    if not args.all:
        injuries = filter_active_il(injuries)
        print(f"  Active IL: {len(injuries)} players")

    rows = format_rows(injuries, args.season)
    write_csv(rows, output_path)
    print(f"  Saved to {output_path}")


if __name__ == "__main__":
    main()
