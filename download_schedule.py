"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

--- File Context and Purpose ---
DESCRIPTION: Downloads MLB schedule from Baseball Reference and saves as CSV.
The schedule includes game dates, teams, and final scores for each game.
This can be used to replace randomly generated schedules in the simulation
with actual MLB schedules for realism.

DEPENDENCIES: requests, pandas, beautifulsoup4
Contact: JimMaastricht5@gmail.com
"""

import requests
import pandas as pd
import re
from datetime import datetime
from bs4 import BeautifulSoup
from bblogger import logger


class ScheduleDownloader:
    """Downloads and parses MLB schedule from Baseball Reference.

    Attributes:
        season: Year of the schedule to download
        schedule_url: URL for the MLB schedule page
        output_file: Filename for the saved CSV
    """

    def __init__(self, season: int = 2026):
        """Initialize the schedule downloader.

        Args:
            season: Year to download schedule for (default 2026)
        """
        self.season = season
        self.schedule_url = f"https://www.baseball-reference.com/leagues/MLB-schedule.shtml"
        self.output_file = f"{season} MLB Schedule.csv"

    def download(self) -> str:
        """Download the schedule HTML from Baseball Reference.

        Returns:
            HTML content as string, or None if download failed
        """
        try:
            logger.info(f"Downloading {self.season} MLB schedule...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(self.schedule_url, headers=headers, timeout=30)
            response.raise_for_status()
            logger.info(f"Downloaded {len(response.text)} bytes")
            return response.text
        except Exception as e:
            logger.error(f"Failed to download schedule: {e}")
            return None

    def parse(self, html: str) -> pd.DataFrame:
        """Parse schedule HTML into a DataFrame with game data.

        Args:
            html: HTML content from Baseball Reference schedule page

        Returns:
            DataFrame with columns: Date, Time, Away_Team, Home_Team, Away_Score, Home_Score

        Note:
            Completed games have no time data in the HTML. Only future games
            (shown as "Preview") include start times.
        """
        soup = BeautifulSoup(html, "html.parser")
        games = []
        current_date = None

        for element in soup.find_all(["h3", "p"]):
            text = element.get_text(strip=True)

            if element.name == "h3":
                if "Today's Games" in text:
                    current_date = datetime.now().strftime("%Y-%m-%d")
                else:
                    try:
                        current_date = datetime.strptime(text, "%A, %B %d, %Y").strftime("%Y-%m-%d")
                    except ValueError:
                        try:
                            current_date = datetime.strptime(text, "%B %d, %Y").strftime("%Y-%m-%d")
                        except ValueError:
                            continue

            elif element.name == "p" and element.get("class") == ["game"]:
                if current_date:
                    # Check if it's a preview (future) or completed game
                    if "Preview" in text:
                        # Preview format: "HH:MM am/pm Team @ Team Preview"
                        time_match = re.search(r"^(\d{1,2}:\d{2}\s*[ap]\.?m\.?)", text, re.IGNORECASE)
                        game_time = self._normalize_time(time_match.group(1)) if time_match else ""

                        remaining = text[len(time_match.group(1)) :].lstrip() if time_match else text
                        parts = remaining.split("@")
                        if len(parts) >= 2:
                            away_team = parts[0].strip()
                            home_team = parts[1].replace("Preview", "").strip()

                            games.append(
                                {
                                    "Date": current_date,
                                    "Time": game_time,
                                    "Away_Team": self._normalize_team(away_team),
                                    "Home_Team": self._normalize_team(home_team),
                                    "Away_Score": 0,
                                    "Home_Score": 0,
                                }
                            )
                    else:
                        # Completed game format: "Team(7)@Team(0)Boxscore"
                        game_match = re.match(r"(.+?)\((\d+)\)\s*@\s*(.+?)\((\d+)\)", text)
                        if game_match:
                            games.append(
                                {
                                    "Date": current_date,
                                    "Time": "",
                                    "Away_Team": self._normalize_team(game_match.group(1).strip()),
                                    "Home_Team": self._normalize_team(game_match.group(3).strip()),
                                    "Away_Score": int(game_match.group(2)),
                                    "Home_Score": int(game_match.group(4)),
                                }
                            )

        df = pd.DataFrame(games)
        logger.info(f"Parsed {len(df)} games from schedule")
        return df

    def _normalize_time(self, time_str: str) -> str:
        """Convert time string to 24-hour format (e.g., "6:40 PM").

        Args:
            time_str: Time string like "6:40 pm" or "3:05 p.m."

        Returns:
            Time in 24-hour format
        """
        time_str = time_str.lower().replace(".", "").replace(" ", "")
        try:
            dt = datetime.strptime(time_str, "%I:%M%p")
            return dt.strftime("%H:%M")
        except ValueError:
            return time_str

    def _normalize_team(self, team_name: str) -> str:
        """Convert full team names to three-letter abbreviations.

        Args:
            team_name: Full team name from Baseball Reference

        Returns:
            Three-letter team abbreviation
        """
        team_map = {
            "Arizona Diamondbacks": "ARI",
            "Arizona D'Backs": "ARI",
            "D'Backs": "ARI",
            "Dbacks": "ARI",
            "Atlanta Braves": "ATL",
            "Baltimore Orioles": "BAL",
            "Boston Red Sox": "BOS",
            "Chicago Cubs": "CHC",
            "Chicago White Sox": "CHW",
            "Cincinnati Reds": "CIN",
            "Cleveland Guardians": "CLE",
            "Colorado Rockies": "COL",
            "Detroit Tigers": "DET",
            "Houston Astros": "HOU",
            "Kansas City Royals": "KCR",
            "Los Angeles Angels": "LAA",
            "Los Angeles Dodgers": "LAD",
            "Miami Marlins": "MIA",
            "Milwaukee Brewers": "MIL",
            "Minnesota Twins": "MIN",
            "New York Mets": "NYM",
            "New York Yankees": "NYY",
            "Oakland Athletics": "ATH",
            "Athletics": "ATH",
            "Philadelphia Phillies": "PHI",
            "Pittsburgh Pirates": "PIT",
            "San Diego Padres": "SDP",
            "San Francisco Giants": "SFG",
            "Seattle Mariners": "SEA",
            "St. Louis Cardinals": "STL",
            "Tampa Bay Rays": "TBR",
            "Texas Rangers": "TEX",
            "Toronto Blue Jays": "TOR",
            "Washington Nationals": "WSN",
        }
        return team_map.get(team_name, team_name[:3].upper())

    def save(self, df: pd.DataFrame) -> bool:
        """Save schedule DataFrame to CSV file.

        Args:
            df: DataFrame with schedule data

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            df.to_csv(self.output_file, index=False)
            logger.info(f"Saved schedule to {self.output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save schedule: {e}")
            return False


def main():
    """Download and save the MLB schedule for 2026."""
    downloader = ScheduleDownloader(season=2026)
    html = downloader.download()
    if html:
        df = downloader.parse(html)
        if not df.empty:
            downloader.save(df)
            print(f"\nDownloaded {len(df)} games to {downloader.output_file}")
            print("\nFirst 10 games:")
            print(df.head(10).to_string())
        else:
            print("No games found in schedule")
    else:
        print("Failed to download schedule")


if __name__ == "__main__":
    main()
