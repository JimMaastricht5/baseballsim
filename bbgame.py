"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

--- File Context and Purpose ---
DESCRIPTION: Core module for simulating a single baseball game between two teams.
Manages game state (score, innings, outs, runners), handles pitcher changes,
resolves at-bats, and updates game statistics for the involved players and teams.

PRIMARY CLASS:
- Game: Manages the details and simulation flow for an individual game, supporting
  both single-threaded (`sim_game`) and multi-threaded (`sim_game_threaded`) execution.

DEPENDENCIES: bbstats, bbteam, at_bat, bbbaserunners, bblogger.

Contact: JimMaastricht5@gmail.com
"""

import datetime
import queue
import random
from typing import List, Tuple, Optional, Dict, ClassVar

import numpy as np
import pandas as pd
from pandas.core.series import Series
from pydantic import BaseModel, Field

import bbat_bat as at_bat
import bbbaserunners
import bbstats
import bbteam
from bblogger import logger
from ui.models.game_data import AWAY, HOME, InningRow, InningScore


class BattingStats(BaseModel):
    """Individual batting statistics for a player."""

    G: float = 0
    AB: float = 0
    R: float = 0
    H: float = 0
    D: float = 0  # 2B
    T: float = 0  # 3B
    HR: float = 0
    RBI: float = 0
    SB: float = 0
    CS: float = 0
    BB: float = 0
    SO: float = 0
    SH: float = 0
    SF: float = 0
    HBP: float = 0

    @property
    def AVG(self) -> float:
        return self.H / self.AB if self.AB > 0 else 0.0

    @property
    def OBP(self) -> float:
        denom = self.AB + self.BB + self.HBP + self.SF
        return (self.H + self.BB + self.HBP) / denom if denom > 0 else 0.0

    @property
    def SLG(self) -> float:
        singles = self.H - self.D - self.T - self.HR
        tb = singles + self.D * 2 + self.T * 3 + self.HR * 4
        return tb / self.AB if self.AB > 0 else 0.0

    @property
    def OPS(self) -> float:
        return self.OBP + self.SLG


class PitchingStats(BaseModel):
    """Individual pitching statistics for a player."""

    G: float = 0
    GS: float = 0
    CG: float = 0
    SHO: float = 0
    IP: float = 0
    H: float = 0
    D: float = 0  # 2B
    T: float = 0  # 3B
    ER: float = 0
    SO: float = 0
    BB: float = 0
    HR: float = 0
    W: float = 0
    L: float = 0
    SV: float = 0
    BS: float = 0
    HLD: float = 0

    @property
    def ERA(self) -> float:
        if self.IP == 0:
            return 0.0
        outs = int(self.IP) * 3 + round((self.IP % 1) * 10) / 3
        return (self.ER / outs) * 27 if outs > 0 else 0.0

    @property
    def WHIP(self) -> float:
        return (self.BB + self.H) / self.IP if self.IP > 0 else 0.0


class PlayerBattingEntry(BaseModel):
    """A player in the batting lineup."""

    hashcode: str
    name: str
    position: str
    age: int
    team: str
    stats: BattingStats = Field(default_factory=BattingStats)


class PlayerPitchingEntry(BaseModel):
    """A pitcher in the game."""

    hashcode: str
    name: str
    age: int
    team: str
    stats: PitchingStats = Field(default_factory=PitchingStats)


class TeamLineup(BaseModel):
    """Complete team lineup (batters and pitcher)."""

    team: str
    league: str = ""
    batters: List[PlayerBattingEntry] = Field(default_factory=list)
    starting_pitcher: Optional[PlayerPitchingEntry] = None
    relief_pitchers: List[PlayerPitchingEntry] = Field(default_factory=list)


class PlayResult(BaseModel):
    """Result of a single at-bat."""

    batter_hash: str
    batter_name: str
    pitcher_hash: str
    pitcher_name: str
    result: str  # Single letter result code
    outs_after: int = 0
    runners_on_base: str = ""  # e.g., "1st", "1st and 2nd", etc.
    runs_scored: List[str] = Field(default_factory=list)  # Names of players who scored
    runners_affected: List[str] = Field(default_factory=list)  # e.g., ["1st", "3rd"]
    play_description: str = ""  # Human-readable description
    is_pitching_change: bool = False
    new_pitcher_hash: Optional[str] = None
    new_pitcher_name: Optional[str] = None
    is_steal_attempt: bool = False
    stolen_base: Optional[str] = None
    caught_stealing: bool = False

    # Valid outcome codes for reference
    OUTCOME_CHOICES: ClassVar[List[str]] = [
        "H",
        "2B",
        "3B",
        "HR",
        "SO",
        "BB",
        "IBB",
        "HBP",
        "SF",
        "SH",
        "GO",
        "AO",
        "FO",
        "LO",
        "PO",
        "DP",
        "TP",
        "SB",
        "CS",
        "PK",
        "E",
        "NR",
        "NP",
    ]


class InningHalf(BaseModel):
    """Half of an inning (top or bottom)."""

    batting_team: str
    pitching_team: str
    plays: List[PlayResult] = Field(default_factory=list)
    runs_scored: int = 0


class TeamBoxScore(BaseModel):
    """Team box score with batters and pitchers."""

    team: str
    batters: List[PlayerBattingEntry] = Field(default_factory=list)
    pitchers: List[PlayerPitchingEntry] = Field(default_factory=list)
    totals_batting: Optional[BattingStats] = None
    totals_pitching: Optional[PitchingStats] = None
    total_hits: int = 0
    total_errors: int = 0


class GameRecap(BaseModel):
    """
    Structured representation of a complete baseball game.

    This model provides a typed, structured representation of all game data
    that can be used by the UI or other consumers. It replaces the monolithic
    string-based game_recap with typed data structures.
    """

    game_id: Optional[str] = None
    away_team: str
    home_team: str
    final_score: Tuple[int, int] = (0, 0)
    final_inning: int = 9
    is_extra_innings: bool = False

    # Lineups
    away_lineup: Optional[TeamLineup] = None
    home_lineup: Optional[TeamLineup] = None

    # Inning-by-inning data
    innings: List[Dict[str, InningHalf]] = Field(default_factory=list)
    inning_scores: List[InningScore] = Field(default_factory=list)

    # Box scores
    away_box_score: Optional[TeamBoxScore] = None
    home_box_score: Optional[TeamBoxScore] = None

    # Win/Loss records
    winning_pitcher: Optional[str] = None
    losing_pitcher: Optional[str] = None
    save_pitcher: Optional[str] = None

    # Metadata
    played_date: Optional[str] = None
    game_number_in_series: int = 1

    def to_legacy_string(self) -> str:
        """
        Generate the legacy string format for backward compatibility.
        This allows gradual migration from string-based to structured data.
        """
        lines = []

        # Header
        lines.append(f"▼ {self.away_team} @ {self.home_team} ▼\n")

        # Lineups
        if self.away_lineup:
            lines.append(
                f"Starting lineup for the {self.away_team} ({self.away_lineup.league}):\n"
            )
            # Add lineup table...

        if self.home_lineup:
            lines.append(
                f"\nStarting lineup for the {self.home_team} ({self.home_lineup.league}):\n"
            )
            # Add lineup table...

        # Play-by-play
        for i, inning_data in enumerate(self.innings):
            inning_num = i + 1
            for half, half_data in inning_data.items():
                if half == "top":
                    lines.append(f"\nStarting the top of inning {inning_num}.")
                else:
                    lines.append(f"\nStarting the bottom of inning {inning_num}.")

                for play in half_data.plays:
                    lines.append(
                        f"\tPitcher: {play.pitcher_name} against {play.batter_name} - {play.result}, {play.outs_after} Out"
                        + ("s" if play.outs_after != 1 else "")
                    )

                    if play.runners_affected:
                        runner_str = ", ".join(
                            [f"Runner on {r}" for r in play.runners_affected]
                        )
                        lines.append(f"\t{runner_str}")

                    if play.runs_scored:
                        scored_str = ", ".join(play.runs_scored)
                        lines.append(
                            f"\tScored {len(play.runs_scored)} run(s)!  ({scored_str})"
                        )

                    if play.is_pitching_change and play.new_pitcher_name:
                        lines.append(
                            f"\tManager has made the call to the bull pen.  Pitching change...."
                        )
                        lines.append(
                            f"\t{play.new_pitcher_name} has entered the game for {half_data.batting_team}"
                        )

                    if play.is_steal_attempt and play.stolen_base:
                        action = (
                            "stole" if not play.caught_stealing else "caught stealing"
                        )
                        lines.append(
                            f"\t{play.batter_name} {action} {play.stolen_base}!"
                        )

                lines.append(
                    f"\nCompleted {'top' if half == 'top' else 'bottom'} half of inning {inning_num}"
                )
                lines.append(
                    f"The score is {self.away_team} {self.final_score[0]} to {self.home_team} {self.final_score[1]}"
                )

        # Box scores
        if self.away_box_score:
            lines.append("\n")
            # Add box score tables...

        if self.home_box_score:
            # Add box score tables...
            pass

        # Final score table
        lines.append(f"\nFinal")
        # Add score table...

        return "\n".join(lines)


class Game:
    def __init__(
            self,
            away_team_name: str = "",
            home_team_name: str = "",
            baseball_data=None,
            game_num: int = 1,
            rotation_len: int = 5,
            print_lineup: bool = False,
            chatty: bool = False,
            print_box_score_b: bool = False,
            team_to_follow: Optional[List[str]] = None,
            load_seasons: List[int] = 2025,
            new_season: int = 2026,
            starting_pitchers: None = None,
            starting_lineups: None = None,
            load_batter_file: str = "player-stats-Batters.csv",
            load_pitcher_file: str = "player-stats-Pitching.csv",
            interactive: bool = False,
            show_bench: bool = False,
            debug: bool = False,
            play_by_play_callback=None,
            obp_adjustment=None,
    ) -> None:
        """
        class manages the details of an individual game
        :param away_team_name: away team name is a 3 character all caps abbreviation
        :param home_team_name: home team
        :param baseball_data: class with all the baseball data for the league. prior and current season
        :param game_num: game number in season
        :param rotation_len: len of rotation for team or series.  typically 5
        :param print_lineup: true will print the lineup prior to the game
        :param chatty: prints more output to console
        :param print_box_score_b: true prints the final box score
        :param team_to_follow: list of team abbreviations to follow in detail (enables print_lineup, chatty, print_box_score_b)
        :param load_seasons: list of integers with years of prior season being used to calc probabilities
        :param new_season: int of new season year
        :param starting_pitchers: optional hashcode for the starting pitchers in a list form [away, home]
        :param starting_lineups: list of dicts with starting lineups in format
            [{647549: 'LF', 239398: 'C', 224423: '1B', 138309: 'DH', 868055: 'CF', 520723: 'SS',
                  299454: '3B', 46074: '2B', 752787: 'RF'}. None] in example none is the home team lineup
        :param load_batter_file: name of files with batter data, will prefix years
        :param load_pitcher_file: name of files with pitcher data, will prefix years
        :param interactive: allows for gaming of the sim, pauses sim at appropriate times for input
        :param show_bench: show the players not in game along with the lineup
        :param debug: prints extra info
        """
        self.game_recap = ""
        if baseball_data is None:
            self.baseball_data = bbstats.BaseballStats(
                load_seasons=load_seasons,
                new_season=new_season,
                load_batter_file=load_batter_file,
                load_pitcher_file=load_pitcher_file,
            )
        else:
            self.baseball_data = baseball_data
        if away_team_name != "" and home_team_name != "":
            self.team_names = [away_team_name, home_team_name]
        else:
            self.team_names = random.sample(
                list(self.baseball_data.batting_data.Team.unique()), 2
            )
        self.game_num = game_num  # number of games into season
        self.rotation_len = rotation_len  # number of starting pitchers to rotate over

        # Check if this game involves a team to follow and control detailed output
        team_to_follow = team_to_follow if team_to_follow is not None else []
        is_followed_game = any(team in team_to_follow for team in self.team_names)

        # If team_to_follow list is not empty, only show details for followed teams' games
        if len(team_to_follow) > 0:
            if not is_followed_game:
                # Not a followed game, suppress detailed output
                print_lineup = False
                chatty = False
                print_box_score_b = False
            # else: is_followed_game - use the passed-in flags from season settings
        # else: use the passed-in flags (season-level defaults)

        self.chatty = chatty
        self.print_box_score_b = print_box_score_b
        self.team_to_follow = team_to_follow
        self.is_followed_game = is_followed_game
        logger.debug(
            f"Initializing Game: {away_team_name} vs {home_team_name}, game #{game_num}"
        )
        if starting_pitchers is None:
            starting_pitchers = [None, None]
        self.starting_pitchers = starting_pitchers  # can use if you want to sim the same two starters repeatedly
        if starting_lineups is None:
            starting_lineups = [None, None]
        self.starting_lineups = starting_lineups  # is a list of two dict, each dict is in batting order with field pos

        self.teams = []  # keep track of away in pos 0 and home team in pos 1
        self.teams.insert(
            AWAY,
            bbteam.Team(
                team_name=self.team_names[AWAY],
                baseball_data=self.baseball_data,
                game_num=self.game_num,
                rotation_len=self.rotation_len,
            ),
        )  # init away team class
        alineup_card = self.teams[AWAY].set_initial_lineup(
            show_lineup=print_lineup,
            show_bench=show_bench,
            current_season_stats=(True if game_num > 1 else False),
            force_starting_pitcher=starting_pitchers[AWAY],
            force_lineup_dict=starting_lineups[AWAY],
        )
        self.teams.insert(
            HOME,
            bbteam.Team(
                team_name=self.team_names[HOME],
                baseball_data=self.baseball_data,
                game_num=self.game_num,
                rotation_len=self.rotation_len,
            ),
        )  # init away team class
        hlineup_card = self.teams[HOME].set_initial_lineup(
            show_lineup=print_lineup,
            show_bench=show_bench,
            current_season_stats=(True if game_num > 1 else False),
            force_starting_pitcher=starting_pitchers[HOME],
            force_lineup_dict=starting_lineups[HOME],
        )
        self.game_recap += alineup_card + hlineup_card
        self.win_loss = []
        self.is_save_sit = [False, False]
        self.total_score = [0, 0]  # total score
        # InningRow: stores (number, away_runs, home_runs) for each inning
        self.inning_score = [
            InningRow(number=1),
            InningRow(number=2),
            InningRow(number=3),
            InningRow(number=4),
            InningRow(number=5),
            InningRow(number=6),
            InningRow(number=7),
            InningRow(number=8),
            InningRow(number=9),
        ]
        self.inning = [1, 1]
        self.batting_num = [1, 1]
        self.prior_batter_out_num = [1, 1]  # used for extra inning runners
        self.prior_batter_out_name = ["", ""]  # used for extra innings
        self.pitching_num = [0, 0]
        self.outs = 0
        self.top_bottom = 0  # zero is top offset, 1 is bottom offset
        self.winning_pitcher = None
        self.losing_pitcher = None

        self.rng = lambda: np.random.default_rng().uniform(
            low=0.0, high=1.001
        )  # random generator between 0 and 1
        self.bases = bbbaserunners.Bases()
        self.outcomes = at_bat.OutCome()
        self.at_bat = at_bat.SimAB(
            self.baseball_data, obp_adjustment=obp_adjustment
        )  # setup class
        self.steal_multiplier = 1.7  # rate of steals per on base is not generating the desired result so increase it
        self.interactive = (
            interactive  # is this game being controlled by a human or straight sim
        )
        self.manager = None
        self.play_by_play_callback = (
            play_by_play_callback  # callback for real-time play-by-play updates
        )

        # Structured game data (Pydantic models)
        self.structured_game = GameRecap(
            away_team=self.team_names[AWAY],
            home_team=self.team_names[HOME],
            away_lineup=None,
            home_lineup=None,
            innings=[],
            inning_scores=[],
            away_box_score=None,
            home_box_score=None,
        )
        # Accumulated plays for each half-inning (cleared each inning)
        self.current_inning_plays: Dict[str, InningHalf] = {
            "top": InningHalf(
                batting_team=self.team_names[AWAY],
                pitching_team=self.team_names[HOME],
                plays=[],
            ),
            "bottom": InningHalf(
                batting_team=self.team_names[HOME],
                pitching_team=self.team_names[AWAY],
                plays=[],
            ),
        }
        self.current_inning_num: int = 1
        return

    def team_pitching(self) -> int:
        """
        which team is pitching
        :return: 0 away, 1, home team
        """
        return (self.top_bottom + 1) % 2

    def team_hitting(self) -> int:
        """
        which team is hitting
        :return: 0 away and 1 home
        """
        return self.top_bottom

    def score_diff(self) -> int:
        """
        looks at the score from the perspective of the team that is currently pitching.  used for save situation
        team pitching with lead will be positive difference, team pitching behind will be neg
        :return: score difference
        """
        return (
                self.total_score[self.team_pitching()]
                - self.total_score[self.team_hitting()]
        )

    def save_sit(self) -> bool:
        """
        is this a save situation?
        can go two innings for a save so start measure in the 8th inning
        if pitching team is leading and runners + ab + on deck is equal to score diff
        :return: true save situation
        """
        return (
                self.score_diff() > 0
                and (self.score_diff() <= self.bases.count_runners() + 2)
                and self.inning[self.team_hitting()] >= 8
        )

    def close_game(self) -> bool:
        """
        is the game close in the late innings?  True if team leading by 0 to 3 runs in 7inning or later
        :return: true for close game
        """
        return 0 <= self.score_diff() <= 3 and self.inning[self.team_hitting()] >= 7

    def update_inning_score(self, number_of_runs: int = 0) -> None:
        """
        update half inning score
        :param number_of_runs: number of run scored so far in this half inning
        :return: None
        """
        # Expand innings list if needed for extra innings
        if len(self.inning_score) <= self.inning[self.team_hitting()]:
            self.inning_score.append(InningRow(number=self.inning[self.team_hitting()]))

        # Update the appropriate team's runs using InningRow
        inning_idx = self.inning[self.team_hitting()]
        if self.team_hitting() == AWAY:
            self.inning_score[inning_idx].away_runs = number_of_runs
        else:
            self.inning_score[inning_idx].home_runs = number_of_runs

        # pitcher of record tracking, look for lead change
        if (
                self.total_score[self.team_hitting()]
                <= self.total_score[self.team_pitching()]
                < (self.total_score[self.team_hitting()] + self.bases.runs_scored)
        ):
            self.winning_pitcher = self.teams[self.team_hitting()].is_pitching_index()
            self.losing_pitcher = self.teams[self.team_pitching()].is_pitching_index()
            if self.is_save_sit[self.team_pitching()]:  # blown save
                cur_pitcher = self.teams[self.team_pitching()].is_pitching_index()
                self.teams[self.team_pitching()].box_score.pitching_blown_save(
                    cur_pitcher
                )

        self.total_score[self.team_hitting()] += number_of_runs  # update total score
        return

    def print_inning_score(self, final: bool = False) -> None:
        """
        print inning by inning score - full format for followed games
        :param final: True if called at end of game (from end_game), False if during game
        :return: None
        """
        if self.is_followed_game and final:
            # Only print full table with "Final" heading when game is complete
            # Add "Final" heading with blank line above
            final_heading = "\nFinal\n"
            self.game_recap += final_heading
            if self.play_by_play_callback:
                self.play_by_play_callback(final_heading)

            # Full inning-by-inning format for followed games
            # Convert InningRow objects to lists for printing
            print_inning_score = [
                [
                    row.number,
                    row.away_runs if row.away_runs else "",
                    row.home_runs if row.home_runs else "",
                ]
                for row in self.inning_score
            ]
            print_inning_score.append(
                ["R", self.total_score[AWAY], self.total_score[HOME]]
            )
            print_inning_score.append(
                [
                    "H",
                    self.teams[AWAY].box_score.total_hits,
                    self.teams[HOME].box_score.total_hits,
                ]
            )
            print_inning_score.append(
                [
                    "E",
                    self.teams[AWAY].box_score.total_errors,
                    self.teams[HOME].box_score.total_errors,
                ]
            )
            row_to_col = list(zip(*print_inning_score))
            for ii in range(0, 3):  # print each row
                print_line = ""
                for jj in range(0, len(row_to_col[ii])):
                    print_line = print_line + f"{str(row_to_col[ii][jj]):>4}"
                print_line += "\n"
                self.game_recap += print_line
                if self.play_by_play_callback:
                    self.play_by_play_callback(print_line)
        # Compact format handled separately in get_compact_summary()
        return

    def get_compact_summary(self) -> dict:
        """
        Returns compact game summary for non-followed games
        :return: dict with team names and RHE stats
        """
        return {
            "away_team": self.team_names[AWAY],
            "home_team": self.team_names[HOME],
            "away_r": self.total_score[AWAY],
            "home_r": self.total_score[HOME],
            "away_h": self.teams[AWAY].box_score.total_hits,
            "home_h": self.teams[HOME].box_score.total_hits,
            "away_e": self.teams[AWAY].box_score.total_errors,
            "home_e": self.teams[HOME].box_score.total_errors,
        }

    @staticmethod
    def format_compact_games(game_summaries: list) -> str:
        """
        Format multiple game summaries side-by-side (5 games per line)
        :param game_summaries: list of dicts from get_compact_summary()
        :return: formatted string with games side-by-side
        """
        if not game_summaries:
            return ""

        games_per_line = 5
        game_separator = "     "  # 5 spaces between games
        output = ""

        for i in range(0, len(game_summaries), games_per_line):
            batch = game_summaries[i: i + games_per_line]

            # Header line with R H E repeated
            header_parts = []
            for _ in batch:
                header_parts.append("     R   H   E")
            output += game_separator.join(header_parts) + "\n"

            # Away teams line
            away_parts = []
            for game in batch:
                away_parts.append(
                    f"{game['away_team']:>3} {game['away_r']:>2}  {game['away_h']:>2}   {game['away_e']:>1}"
                )
            output += game_separator.join(away_parts) + "\n"

            # Home teams line
            home_parts = []
            for game in batch:
                home_parts.append(
                    f"{game['home_team']:>3} {game['home_r']:>2}  {game['home_h']:>2}   {game['home_e']:>1}"
                )
            output += game_separator.join(home_parts) + "\n\n"

        return output

    def pitching_sit(self, pitching: Series, pitch_switch: bool) -> bool:
        """
        switches pitchers based on fatigue or
        close game which is hitting inning >= 7 and, pitching team winning or tied and runners on = save sit
        if switch due to save or close game, don't switch again in same inning
        :param pitching: current pitchers data in a df series
        :param pitch_switch: did we already switch pitchers this inning?  Do not sub too fast
        :return: should we switch pitchers?
        """
        if (
                self.teams[self.team_pitching()].is_pitcher_fatigued(pitching.Condition)
                and self.outs < 3
        ) or (pitch_switch is False and (self.close_game() or self.save_sit())):
            prior_pitcher = self.teams[self.team_pitching()].is_pitching_index()
            self.teams[self.team_pitching()].pitching_change(
                inning=self.inning[self.team_hitting()], score_diff=self.score_diff()
            )
            if (
                    prior_pitcher != self.teams[self.team_pitching()].is_pitching_index()
            ):  # we are switching pitchers
                pitching = self.teams[
                    self.team_pitching()
                ].cur_pitcher_stats()  # data for new pitcher
                pitch_switch = True  # we switched pitcher this inning
                self.is_save_sit[self.team_pitching()] = self.save_sit()
                if self.chatty and pitch_switch:
                    play_text = f"Manager has made the call to the bull pen.  Pitching change....\n"
                    self.game_recap += play_text
                    if self.play_by_play_callback:
                        self.play_by_play_callback(play_text)
                    play_text = f"\t{pitching.Player} has entered the game for {self.team_names[self.team_pitching()]}\n"
                    self.game_recap += play_text
                    if self.play_by_play_callback:
                        self.play_by_play_callback(play_text)
                    # print(f'\tManager has made the call to the bull pen.  Pitching change....')
                    # print(f'\t{pitching.Player} has entered the game for {self.team_names[self.team_pitching()]}')
        return pitch_switch

    def balk_wild_pitch(self) -> None:
        """
        if this a situation where a balk or a wild pitch matters?  did it occur? what was the result?
        :return: None
        """
        # if self.bases.count_runners() > 0:
        #     die_roll = self.rng()
        #     balk_wild_pitch_rate = ((self.teams[self.team_pitching()].cur_pitcher_stats()['BK'] +
        #                             self.teams[self.team_pitching()].cur_pitcher_stats()['WP']) /
        #                             (self.teams[self.team_pitching()].cur_pitcher_stats()['AB'] +
        #                              self.teams[self.team_pitching()].cur_pitcher_stats()['BB']))
        #     balk_rate = (self.teams[self.team_pitching()].cur_pitcher_stats()['BK'] /
        #                             (self.teams[self.team_pitching()].cur_pitcher_stats()['AB'] +
        #                              self.teams[self.team_pitching()].cur_pitcher_stats()['BB']))
        #     if die_roll <= balk_wild_pitch_rate:
        #         if die_roll <= balk_rate:
        #             self.game_recap += f'******* balk '
        #         else:
        #             self.game_recap += f'**** wild pitch'
        return

    def stolen_base_sit(self) -> None:
        """
        is this a stolen base situation?  should we steal? what was the result?
        :return: None
        """
        if self.bases.is_eligible_for_stolen_base():
            runner_key = self.bases.get_runner_key(1)
            runner_stats = self.teams[self.team_hitting()].pos_player_prior_year_stats(
                runner_key
            )
            # scale steal attempts with frequency of stealing when on base
            # runner_stats.SB + runner_stats.CS >= self.min_steal_attempts and \

            # Calculate steal attempt probability, handling division by zero
            times_on_base = runner_stats.H + runner_stats.BB
            steal_attempts = runner_stats.SB + runner_stats.CS

            if times_on_base > 0 and steal_attempts > 0:
                steal_attempt_rate = steal_attempts / times_on_base
                if self.rng() <= steal_attempt_rate * self.steal_multiplier:
                    # Calculate steal success rate, handling division by zero
                    steal_success_rate = (
                        runner_stats.SB / steal_attempts if steal_attempts > 0 else 0.0
                    )
                    if self.rng() <= steal_success_rate:  # successful steal
                        self.bases.push_a_runner(1, 2)  # move runner from 1st to second
                        self.teams[self.team_hitting()].box_score.steal_result(
                            runner_key, True
                        )  # stole the base
                        if self.chatty:
                            play_text = f"\t{runner_stats.Player} stole 2nd base!\n"
                            self.game_recap += play_text
                            if self.play_by_play_callback:
                                self.play_by_play_callback(play_text)
                            play_text = f"\t{self.bases.describe_runners()}\n"
                            self.game_recap += play_text
                            if self.play_by_play_callback:
                                self.play_by_play_callback(play_text)
                    else:
                        self.teams[self.team_hitting()].box_score.steal_result(
                            runner_key, False
                        )  # caught stealing
                        self.bases.remove_runner(
                            1
                        )  # runner was on first and never made it to second on the out
                        if self.chatty:
                            self.outs += 1  # this could result in the third out
                            play_text = f"\t{runner_stats.Player} was caught stealing for out number {self.outs}\n"
                            self.game_recap += play_text
                            if self.play_by_play_callback:
                                self.play_by_play_callback(play_text)
        return

    def is_extra_innings(self) -> bool:
        """
        :return: are we in extra inning?
        """
        return self.inning[self.team_hitting()] > 9

    def extra_innings(self) -> None:
        """
        adds a running to second base for extra innings
        :return: None
        """
        # ignores player name, is already in lookup table if he was the last batter / out
        if self.is_extra_innings():
            self.bases.add_runner_to_base(
                base_num=2,
                batter_num=self.prior_batter_out_num[self.team_hitting()],
                player_name=self.prior_batter_out_name[self.team_hitting()],
            )
            if self.chatty:
                self.game_recap += (
                    f"Extra innings: {self.prior_batter_out_name[self.team_hitting()]} "
                    f"will start at 2nd base.\n"
                )
        return

    def _build_play_description(self, pitching: Series, batting: Series) -> str:
        """
        Build a human-readable description of the play.

        Args:
            pitching: Series with pitcher data
            batting: Series with batter data

        Returns:
            Human-readable play description
        """
        result = self.outcomes.score_book_cd
        outs_after = self.outs
        out_text = "out" if outs_after == 1 else "outs"

        desc = (
            f"{pitching.Player} vs {batting.Player}: {result}, {outs_after} {out_text}"
        )

        if self.bases.runs_scored > 0:
            players = []
            for pid in self.bases.player_scored.keys():
                players.append(self.bases.player_scored[pid])
            players_str = ", ".join(players) if players else "runner(s)"
            desc += f". {self.bases.runs_scored} run(s) scored ({players_str})"

        runners = self.bases.describe_runners()
        if runners:
            desc += f". {runners}"

        return desc

    def sim_ab(self) -> Tuple[Series, Series]:
        """
        simulates an ab in a game
        :return: a tuple containing the updates series data for the pitcher and hitter as a result of the ab
        """
        cur_pitcher_index = self.teams[self.team_pitching()].cur_pitcher_index
        pitching = self.teams[
            self.team_pitching()
        ].cur_pitcher_stats()  # data for pitcher
        pitching.Game_Fatigue_Factor, cur_percentage = self.teams[
            self.team_pitching()
        ].update_fatigue(cur_pitcher_index)

        cur_batter_index = self.teams[self.team_hitting()].batter_index_in_lineup(
            self.batting_num[self.team_hitting()]
        )
        batting = self.teams[self.team_hitting()].batter_stats_in_lineup(
            cur_batter_index
        )
        self.bases.new_ab(batter_num=cur_batter_index, player_name=batting.Player)
        self.at_bat.ab_outcome(
            pitching,
            batting,
            self.outcomes,
            self.outs,
            self.bases.is_runner_on_base_num(1),
            self.bases.is_runner_on_base_num(3),
            self.teams[self.team_pitching()].lineup_def_war,
        )
        self.outs = self.outs + self.outcomes.outs_on_play
        self.bases.handle_runners(
            score_book_cd=self.outcomes.score_book_cd,
            bases_to_advance=self.outcomes.bases_to_advance,
            on_base_b=self.outcomes.on_base_b,
            outs=self.outs,
        )
        self.outcomes.set_runs_score(
            self.bases.runs_scored
        )  # runs and rbis for batter and pitcher
        self.teams[self.team_pitching()].box_score.pitching_result(
            cur_pitcher_index, self.outcomes, pitching.Condition
        )
        self.teams[self.team_hitting()].box_score.batting_result(
            cur_batter_index, self.outcomes, self.bases.player_scored
        )

        if self.chatty:
            out_text = "Out" if self.outs <= 1 else "Outs"
            play_text = (
                f"Pitcher: {pitching.Player} against {self.team_names[self.team_hitting()]} "
                f"batter #{self.batting_num[self.team_hitting()]} {batting.Player} - "
                f"{self.outcomes.score_book_cd}, {self.outs} {out_text}\n"
            )
            self.game_recap += play_text
            if self.play_by_play_callback:
                self.play_by_play_callback(play_text)

        self.prior_batter_out_name[self.team_hitting()] = batting.Player
        self.prior_batter_out_num[self.team_hitting()] = cur_batter_index
        return pitching, batting

    def sim_half_inning(self) -> None:
        """
        simulates a half inning of a game
        :return: None
        """
        pitch_switch = (
            False  # did we switch pitchers this inning, don't sub if closer came in
        )
        top_or_bottom = "top" if self.top_bottom == 0 else "bottom"

        # Reset plays for this half-inning
        self.current_inning_num = self.inning[self.team_hitting()]
        self.current_inning_plays["top"].plays = []
        self.current_inning_plays["top"].batting_team = self.team_names[AWAY]
        self.current_inning_plays["top"].pitching_team = self.team_names[HOME]
        self.current_inning_plays["bottom"].plays = []
        self.current_inning_plays["bottom"].batting_team = self.team_names[HOME]
        self.current_inning_plays["bottom"].pitching_team = self.team_names[AWAY]

        if self.chatty:
            play_text = f"\nStarting the {top_or_bottom} of inning {self.inning[self.team_hitting()]}.\n"
            self.game_recap += play_text
            if self.play_by_play_callback:
                self.play_by_play_callback(play_text)
        self.extra_innings()  # set runner on second if it is extra innings
        while self.outs < 3:
            # check for pitching change due to fatigue or game sit
            pitch_switch = self.pitching_sit(
                self.teams[self.team_pitching()].cur_pitcher_stats(),
                pitch_switch=pitch_switch,
            )
            self.stolen_base_sit()  # check for base stealing and then resolve ab
            if self.outs >= 3:
                break  # handle caught stealing

            self.balk_wild_pitch()  # handle wild pitch and balks
            __pitching, __batting = self.sim_ab()  # resolve ab

            # Create structured play result
            play_result = PlayResult(
                batter_hash=str(__batting.name),
                batter_name=__batting.Player,
                pitcher_hash=str(__pitching.name),
                pitcher_name=__pitching.Player,
                result=self.outcomes.score_book_cd,
                outs_after=self.outs,
                runners_on_base=self.bases.describe_runners(),
                runs_scored=[
                    self.bases.player_scored.get(pid, "")
                    for pid in self.bases.player_scored.keys()
                ]
                if self.bases.runs_scored > 0
                else [],
                play_description=self._build_play_description(__pitching, __batting),
            )
            self.current_inning_plays[top_or_bottom].plays.append(play_result)

            if self.bases.runs_scored > 0:  # did a run score?
                self.update_inning_score(number_of_runs=self.bases.runs_scored)
            if self.bases.runs_scored > 0 and self.chatty:
                players = ""
                for player_id in self.bases.player_scored.keys():
                    players = (
                        players + ", " + self.bases.player_scored[player_id]
                        if players != ""
                        else self.bases.player_scored[player_id]
                    )
                play_text = (
                    f"\tScored {self.bases.runs_scored} run(s)!  ({players})\n"
                    f"\tThe score is {self.team_names[0]} {self.total_score[0]} to"
                    f" {self.team_names[1]} {self.total_score[1]}\n"
                )
                self.game_recap += play_text
                if self.play_by_play_callback:
                    self.play_by_play_callback(play_text)
            if (
                    self.bases.count_runners() >= 1 and self.outs < 3 and self.chatty
            ):  # leave out batter check for runner
                play_text = f"\t{self.bases.describe_runners()}\n"
                self.game_recap += play_text
                if self.play_by_play_callback:
                    self.play_by_play_callback(play_text)
            self.batting_num[self.team_hitting()] = (
                self.batting_num[self.team_hitting()] + 1
                if (self.batting_num[self.team_hitting()] + 1) <= 9
                else 1
            )  # wrap around lineup
            # check for walk off
            if (
                    self.is_extra_innings()
                    and self.total_score[AWAY] < self.total_score[HOME]
            ):
                break  # end the half inning

        # half inning over
        self.update_inning_score(
            number_of_runs=0
        )  # push a zero on the board if no runs score this half inning

        # Save plays to structured game
        inning_num = self.inning[self.team_hitting()]
        # Extend or initialize the innings list
        while len(self.structured_game.innings) < inning_num:
            self.structured_game.innings.append({})
        self.structured_game.innings[inning_num - 1][top_or_bottom] = InningHalf(
            batting_team=self.current_inning_plays[top_or_bottom].batting_team,
            pitching_team=self.current_inning_plays[top_or_bottom].pitching_team,
            plays=list(self.current_inning_plays[top_or_bottom].plays),
            runs_scored=sum(
                1
                for p in self.current_inning_plays[top_or_bottom].plays
                if p.runs_scored
            ),
        )

        self.bases.clear_bases()
        if self.chatty:
            play_text = (
                f"\nCompleted {top_or_bottom} half of inning {self.inning[self.team_hitting()]}\n"
                f"The score is {self.team_names[0]} {self.total_score[0]} to {self.team_names[1]} "
                f"{self.total_score[1]}\n"
            )
            self.game_recap += play_text
            if self.play_by_play_callback:
                self.play_by_play_callback(play_text)
            self.print_inning_score()
        self.inning[self.team_hitting()] += 1
        self.top_bottom = (
            0 if self.top_bottom == 1 else 1
        )  # switch teams hitting and pitching
        self.outs = 0  # rest outs to zero
        return

    def is_game_end(self) -> bool:
        """
        checks to see if the game should be over.  handles situations like home team leading after top of 9 or
        extra innings
        :return:
        """
        return (
            False
            if self.inning[AWAY] <= 9
               or self.inning[HOME] <= 8
               or (
                       self.inning[AWAY] != self.inning[HOME]
                       and self.total_score[AWAY] >= self.total_score[HOME]
               )
               or self.total_score[AWAY] == self.total_score[HOME]
            else True
        )

    def win_loss_record(self) -> None:
        """
        update the teams win and loss records and record for winning and losing pitchers.  also updates saves
        :return: None
        """
        home_win = 0 if self.total_score[0] > self.total_score[1] else 1
        self.win_loss.append(
            [abs(home_win - 1), home_win]
        )  # if home win away team is 0, 1
        self.win_loss.append(
            [home_win, abs(home_win - 1)]
        )  # if home win home team is  1, 0

        # assign winning and losing pitchers, if home team lost assign win to away and vice versa
        if home_win == 0:
            self.teams[AWAY].box_score.pitching_win_loss_save(
                self.winning_pitcher, win_b=True, save_b=self.is_save_sit[AWAY]
            )  #
            self.teams[HOME].box_score.pitching_win_loss_save(
                self.losing_pitcher, win_b=False, save_b=False
            )
        else:
            self.teams[AWAY].box_score.pitching_win_loss_save(
                self.losing_pitcher, win_b=False, save_b=False
            )
            self.teams[HOME].box_score.pitching_win_loss_save(
                self.winning_pitcher, win_b=True, save_b=self.is_save_sit[HOME]
            )
        return

    def end_game(self) -> None:
        """
        handle end of the game including updating condition of players, win loss records, box scores, and printing
        :return: None
        """
        self.teams[AWAY].set_batting_condition()
        self.teams[HOME].set_batting_condition()
        self.win_loss_record()
        self.teams[AWAY].box_score.totals()
        self.teams[HOME].box_score.totals()
        if self.print_box_score_b:  # print or not to print...
            self.game_recap += self.teams[AWAY].box_score.print_boxes()
            self.game_recap += self.teams[HOME].box_score.print_boxes()
        self.print_inning_score(
            final=True
        )  # Pass final=True to print the Final heading and score table
        return

    def sim_game(self) -> Tuple[List[int], List[int], List[List[int]], str]:
        """
        simulate an entire game
        :return: tuple contains a list of total score for each team, inning by inning score and win loss records,
            and the output string
        """
        # self.game_recap += f'{self.team_names[0]} vs. {self.team_names[1]} - Final:\n'
        # if self.is_followed_game:
        #     followed_teams_in_game = [team for team in self.team_names if team in self.team_to_follow]
        #     # self.game_recap += f'Following team(s): {", ".join(followed_teams_in_game)}\n'
        while self.is_game_end() is False:
            self.sim_half_inning()
        self.end_game()
        return self.total_score, self.inning, self.win_loss, self.game_recap

    def sim_game_structured(
            self,
    ) -> Tuple[List[int], List[int], List[List[int]], str, GameRecap]:
        """
        Simulate an entire game and return both legacy string and structured data.

        :return: tuple of (total_score, inning_scores, win_loss, legacy_string, structured_game)
        """
        logger.info(f"sim_game_structured called for {self.team_names}")
        while self.is_game_end() is False:
            self.sim_half_inning()
        self.end_game()

        # Build structured game recap
        logger.info("Calling _build_structured_game_recap")
        self._build_structured_game_recap()

        return (
            self.total_score,
            self.inning,
            self.win_loss,
            self.game_recap,
            self.structured_game,
        )

    def _build_structured_game_recap(self) -> GameRecap:
        """
        Build the structured GameRecap from accumulated game data.
        Call this at the end of the game before returning.
        """
        # Update final score
        self.structured_game.final_score = (
            self.total_score[AWAY],
            self.total_score[HOME],
        )

        # Update inning scores - use InningRow directly
        self.structured_game.inning_scores = [
            InningScore(
                inning=row.number,
                away_runs=row.away_runs,
                home_runs=row.home_runs,
            )
            for row in self.inning_score
        ]
        # Check for extra innings
        self.structured_game.is_extra_innings = (
                len(self.structured_game.inning_scores) > 9
        )
        self.structured_game.final_inning = len(self.structured_game.inning_scores)

        # Build lineups from team DataFrames
        self.structured_game.away_lineup = self._build_team_lineup(self.teams[AWAY])
        self.structured_game.home_lineup = self._build_team_lineup(self.teams[HOME])

        # Build box scores from team box_score objects
        logger.info("About to build away_box_score")
        self.structured_game.away_box_score = self._build_team_box_score(
            self.teams[AWAY], AWAY
        )
        logger.info(f"Away box_score built: {self.structured_game.away_box_score}")
        logger.info("About to build home_box_score")
        self.structured_game.home_box_score = self._build_team_box_score(
            self.teams[HOME], HOME
        )
        logger.info(f"Home box_score built: {self.structured_game.home_box_score}")

        # Find winning/losing pitcher names from box scores
        for box_score in [
            self.structured_game.away_box_score,
            self.structured_game.home_box_score,
        ]:
            if box_score and box_score.pitchers:
                for pitcher in box_score.pitchers:
                    if (
                            pitcher.stats.W > 0
                            and self.structured_game.winning_pitcher is None
                    ):
                        self.structured_game.winning_pitcher = pitcher.name
                    if (
                            pitcher.stats.L > 0
                            and self.structured_game.losing_pitcher is None
                    ):
                        self.structured_game.losing_pitcher = pitcher.name
                    if pitcher.stats.SV > 0:
                        self.structured_game.save_pitcher = pitcher.name

        return self.structured_game

    def _build_team_lineup(self, team: bbteam.Team) -> TeamLineup:
        """Build a structured TeamLineup from the team's lineup DataFrame."""
        lineup = TeamLineup(team=team.team_name)

        # Get batting lineup from gameplay_lineup_df
        if hasattr(team, "gameplay_lineup_df") and team.gameplay_lineup_df is not None:
            lineup_df = team.gameplay_lineup_df
            # Handle both DataFrame and Series
            if isinstance(lineup_df, pd.DataFrame):
                for idx, row in lineup_df.iterrows():
                    player_entry = PlayerBattingEntry(
                        hashcode=str(idx),
                        name=row.get("Player", "Unknown"),
                        position=str(row.get("Pos", "")),
                        age=int(row.get("Age", 0)) if pd.notna(row.get("Age")) else 0,
                        team=team.team_name,
                        stats=BattingStats(),
                    )
                    lineup.batters.append(player_entry)
            elif isinstance(lineup_df, pd.Series):
                player_entry = PlayerBattingEntry(
                    hashcode=str(lineup_df.name),
                    name=lineup_df.get("Player", "Unknown"),
                    position=str(lineup_df.get("Pos", "")),
                    age=int(lineup_df.get("Age", 0))
                    if pd.notna(lineup_df.get("Age"))
                    else 0,
                    team=team.team_name,
                    stats=BattingStats(),
                )
                lineup.batters.append(player_entry)

        # Get starting pitcher from gameplay_pitching_df
        if (
                hasattr(team, "gameplay_pitching_df")
                and team.gameplay_pitching_df is not None
        ):
            pitch_df = team.gameplay_pitching_df
            if isinstance(pitch_df, pd.DataFrame):
                for idx, row in pitch_df.iterrows():
                    if row.get("GS", 0) > 0:  # Starting pitcher
                        pitcher_entry = PlayerPitchingEntry(
                            hashcode=str(idx),
                            name=row.get("Player", "Unknown"),
                            age=int(row.get("Age", 0))
                            if pd.notna(row.get("Age"))
                            else 0,
                            team=team.team_name,
                            stats=PitchingStats(),
                        )
                        lineup.starting_pitcher = pitcher_entry
                        break
            elif isinstance(pitch_df, pd.Series):
                if pitch_df.get("GS", 0) > 0:  # Starting pitcher
                    pitcher_entry = PlayerPitchingEntry(
                        hashcode=str(pitch_df.name),
                        name=pitch_df.get("Player", "Unknown"),
                        age=int(pitch_df.get("Age", 0))
                        if pd.notna(pitch_df.get("Age"))
                        else 0,
                        team=team.team_name,
                        stats=PitchingStats(),
                    )
                    lineup.starting_pitcher = pitcher_entry

        return lineup

    def _build_team_box_score(self, team: bbteam.Team, team_idx: int) -> TeamBoxScore:
        """Build a structured TeamBoxScore from the team's box_score object."""
        box = team.box_score

        # DEBUG
        # logger.info(f"_build_team_box_score: team={team.team_name}, box={box}")
        # if box and hasattr(box, "box_batting"):
        #     logger.info(f"  box_batting is None: {box.box_batting is None}")
        #     logger.info(
        #         f"  box_batting empty: {box.box_batting.empty if box.box_batting is not None else 'N/A'}"
        #     )
        #     if box.box_batting is not None and not box.box_batting.empty:
        #         logger.info(
        #             f"  box_batting rows: {len(box.box_batting)}, columns: {list(box.box_batting.columns)[:5]}"
        #         )

        # Build batter entries
        batters = []
        if box.box_batting is not None and not box.box_batting.empty:
            for idx, row in box.box_batting.iterrows():
                if idx == "Totals":
                    continue
                player_entry = PlayerBattingEntry(
                    hashcode=str(idx),
                    name=row.get("Player", "Unknown"),
                    position=row.get("Pos", ""),
                    age=int(row.get("Age", 0)),
                    team=team.team_name,
                    stats=BattingStats(
                        G=float(row.get("G", 0)),
                        AB=float(row.get("AB", 0)),
                        R=float(row.get("R", 0)),
                        H=float(row.get("H", 0)),
                        D=float(row.get("2B", 0)),
                        T=float(row.get("3B", 0)),
                        HR=float(row.get("HR", 0)),
                        RBI=float(row.get("RBI", 0)),
                        SB=float(row.get("SB", 0)),
                        CS=float(row.get("CS", 0)),
                        BB=float(row.get("BB", 0)),
                        SO=float(row.get("SO", 0)),
                        SH=float(row.get("SH", 0)),
                        SF=float(row.get("SF", 0)),
                        HBP=float(row.get("HBP", 0)),
                    ),
                )
                batters.append(player_entry)

        # Build pitcher entries
        pitchers = []
        # DEBUG
        # logger.info(f"  box_pitching is None: {box.box_pitching is None}")
        # logger.info(
        #     f"  box_pitching empty: {box.box_pitching.empty if box.box_pitching is not None else 'N/A'}"
        # )
        if box.box_pitching is not None and not box.box_pitching.empty:
            # logger.info(
            #     f"  box_pitching rows: {len(box.box_pitching)}, columns: {list(box.box_pitching.columns)[:5]}"
            # )
            for idx, row in box.box_pitching.iterrows():
                if idx == "Totals":
                    continue
                player_entry = PlayerPitchingEntry(
                    hashcode=str(idx),
                    name=row.get("Player", "Unknown"),
                    age=int(row.get("Age", 0)),
                    team=team.team_name,
                    stats=PitchingStats(
                        G=float(row.get("G", 0)),
                        GS=float(row.get("GS", 0)),
                        CG=float(row.get("CG", 0)),
                        SHO=float(row.get("SHO", 0)),
                        IP=float(row.get("IP", 0)),
                        H=float(row.get("H", 0)),
                        D=float(row.get("2B", 0)),
                        T=float(row.get("3B", 0)),
                        ER=float(row.get("ER", 0)),
                        SO=float(row.get("SO", 0)),
                        BB=float(row.get("BB", 0)),
                        HR=float(row.get("HR", 0)),
                        W=float(row.get("W", 0)),
                        L=float(row.get("L", 0)),
                        SV=float(row.get("SV", 0)),
                        BS=float(row.get("BS", 0)),
                        HLD=float(row.get("HLD", 0)),
                    ),
                )
                pitchers.append(player_entry)

        result = TeamBoxScore(
            team=team.team_name,
            batters=batters,
            pitchers=pitchers,
            total_hits=box.total_hits,
            total_errors=box.total_errors,
        )
        # DEBUG
        # logger.info(
        #     f"  Returning TeamBoxScore with {len(batters)} batters, {len(pitchers)} pitchers"
        # )
        return result

    def sim_game_threaded(self, q: queue, use_structured: bool = False) -> None:
        """
        handles input and output using the queue for multi-threading

        :param q: queue for data exchange (output only, team_to_follow now passed via __init__)
        :param use_structured: if True, return GameRecap structured data instead of legacy string
        :return: None
        """
        if use_structured:
            g_score, g_innings, g_win_loss, final_game_recap, structured_game = (
                self.sim_game_structured()
            )
            q.put(
                (
                    g_score,
                    g_innings,
                    g_win_loss,
                    self.teams[AWAY].box_score,
                    self.teams[HOME].box_score,
                    final_game_recap,
                    structured_game,
                )
            )
        else:
            g_score, g_innings, g_win_loss, final_game_recap = self.sim_game()
            q.put(
                (
                    g_score,
                    g_innings,
                    g_win_loss,
                    self.teams[AWAY].box_score,
                    self.teams[HOME].box_score,
                    final_game_recap,
                    None,
                )
            )
        return


# test a number of games
if __name__ == "__main__":
    # Configure logger level - change to "DEBUG" for more detailed logs
    from bblogger import configure_logger

    configure_logger("INFO")

    startdt = datetime.datetime.now()

    away_team = "LAD"
    home_team = "MIL"

    # MIL_lineup = {647549: 'LF', 239398: 'C', 224423: '1B', 138309: 'DH', 868055: 'CF', 520723: 'SS',
    #               299454: '3B', 46074: '2B', 752787: 'RF'}
    # NYM_starter = 626858
    # MIL_starter = 288650
    sims = 1
    season_win_loss = [[0, 0], [0, 0]]  # away record pos 0, home pos 1
    score_total = [0, 0]
    # team0_season_df = None
    for sim_game_num in range(1, sims + 1):
        print(f"Game number {sim_game_num}: from bbgame.py sims {sims}")
        game = Game(
            home_team_name=home_team,
            away_team_name=away_team,
            chatty=True,
            print_lineup=True,
            print_box_score_b=True,
            load_seasons=[2023, 2024, 2025],
            new_season=2026,
            # load_batter_file='random-player-projected-stats-pp-Batting.csv',
            # load_pitcher_file='random-player-projected-stats-pp-Pitching.csv',
            load_batter_file="player-projected-stats-pp-Batting.csv",
            load_pitcher_file="player-projected-stats-pp-Pitching.csv",
            interactive=False,
            show_bench=False,
            # , starting_pitchers=[MIL_starter, BOS_starter]
            # , starting_lineups=[MIL_lineup, None]
        )

        # Use the new structured format
        score, inning, win_loss, game_recap_str, structured_game = (
            game.sim_game_structured()
        )

        # Print legacy format (for comparison)
        print("=" * 80)
        print("LEGACY STRING FORMAT:")
        print("=" * 80)
        print(game_recap_str)

        # Print structured format (new)
        print("\n" + "=" * 80)
        print("STRUCTURED FORMAT (Pydantic):")
        print("=" * 80)
        print(f"Game: {structured_game.away_team} @ {structured_game.home_team}")
        print(
            f"Final Score: {structured_game.away_team} {structured_game.final_score[0]} - {structured_game.home_team} {structured_game.final_score[1]}"
        )
        print(
            f"Innings: {structured_game.final_inning}"
            + (" (Extra Innings)" if structured_game.is_extra_innings else "")
        )
        print(f"\nInning Scores:")
        for inn in structured_game.inning_scores:
            print(
                f"  Inning {inn.inning}: {structured_game.away_team} {inn.away_runs} - {structured_game.home_team} {inn.home_runs}"
            )

        print(f"\nAway Team ({structured_game.away_team}) Box Score:")
        if structured_game.away_box_score:
            print(f"  Total Hits: {structured_game.away_box_score.total_hits}")
            print(f"  Batters: {len(structured_game.away_box_score.batters)}")
            print(f"  Pitchers: {len(structured_game.away_box_score.pitchers)}")

        print(f"\nHome Team ({structured_game.home_team}) Box Score:")
        if structured_game.home_box_score:
            print(f"  Total Hits: {structured_game.home_box_score.total_hits}")
            print(f"  Batters: {len(structured_game.home_box_score.batters)}")
            print(f"  Pitchers: {len(structured_game.home_box_score.pitchers)}")

        # Show sample batter stats
        print(f"\nSample Batting Entry (first batter):")
        if structured_game.away_box_score and structured_game.away_box_score.batters:
            batter = structured_game.away_box_score.batters[0]
            print(f"  Name: {batter.name}")
            print(f"  Position: {batter.position}")
            print(
                f"  AB: {batter.stats.AB}, H: {batter.stats.H}, HR: {batter.stats.HR}, RBI: {batter.stats.RBI}"
            )
            print(
                f"  AVG: {batter.stats.AVG:.3f}, OBP: {batter.stats.OBP:.3f}, SLG: {batter.stats.SLG:.3f}, OPS: {batter.stats.OPS:.3f}"
            )

        print(f"\nStructured game model (JSON):")
        print(
            structured_game.model_dump_json(indent=2)[:2000] + "..."
            if len(structured_game.model_dump_json()) > 2000
            else structured_game.model_dump_json(indent=2)
        )

        season_win_loss[0] = list(
            np.add(np.array(season_win_loss[0]), np.array(win_loss[0]))
        )
        season_win_loss[1] = list(
            np.add(np.array(season_win_loss[1]), np.array(win_loss[1]))
        )
        score_total[0] = score_total[0] + score[0]
        score_total[1] = score_total[1] + score[1]
        # if team0_season_df is None:
        # team0_season_df = game.teams[AWAY].box_score.team_box_batting
        # else:
        #     col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
        #     team0_season_df = team0_season_df[col_list].add(game.teams[AWAY].box_score.box_batting[col_list])
        #     team0_season_df['Player'] = game.teams[AWAY].box_score.box_batting['Player']
        #     team0_season_df['Team'] = game.teams[AWAY].box_score.box_batting['Team']
        #     team0_season_df['Pos'] = game.teams[AWAY].box_score.box_batting['Pos']
        #     print('')
        print(
            f"\n{away_team} season : {season_win_loss[0][0]} W and {season_win_loss[0][1]} L"
        )
        print(
            f"{home_team} season : {season_win_loss[1][0]} W and {season_win_loss[1][1]} L"
        )
    print(
        f"away team scored {score_total[0]} for an average of {score_total[0] / sims}"
    )
    print(
        f"home team scored {score_total[1]} for an average of {score_total[1] / sims}"
    )
    print(startdt)
    print(datetime.datetime.now())
