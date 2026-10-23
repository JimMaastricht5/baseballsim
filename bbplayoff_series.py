# Copyright (c) 2024 Jim Maastricht
"""
Playoff series simulation between two teams.

Wraps BaseballSeason.run_playoff_series so fatigue, injuries and streaks carry from game to game.
The two team names pick out a series in the loaded schedule (the last run of games between them, e.g. the World
Series games in "2026 MLB Schedule.csv"). The schedule decides everything else: which team is home, the game order
and dates, the length of the series, and a date with no game is a rest day. Nothing is hard coded. A ValueError is
raised if the schedule has no games between the teams or the series has an even number of games. Everyone starts
the series with fresh conditions (no fatigue, no IL) using the current 2026 data files. The series can be run several
times (num_series) to tally how often each team wins and the average games each team needed to win, every run
starting from freshly loaded data. Series can run in parallel threads (max_threads): each thread plays its own
independent series on its own loaded data and the main thread accumulates the results.

Classes:
    BaseballPlayoffSeries - Sets up and runs one series or several, returns the winner or the tally of winners.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

import bbseason
from bblogger import configure_logger
from bbseason import BaseballSeason, OutputHandlerType

MAX_ROTATION_LEN = 5  # Team builds a five man rotation, a shorter rotation uses its first n starters


class BaseballPlayoffSeries:
    def __init__(
        self,
        team_a: str = "MIL",
        team_b: str = "TBR",
        rotation_len: int = 4,
        round_name: str = "Playoff Series",
        num_series: int = 4,
        load_seasons: Optional[List[int]] = None,
        new_season: int = 2026,
        load_batter_file: str = "player-projected-stats-pp-Batting.csv",
        load_pitcher_file: str = "player-projected-stats-pp-Pitching.csv",
        output_handler: Optional[OutputHandlerType] = None,
    ) -> None:
        """
        Load the data and prepare a series between two teams.
        :param team_a: one of the two teams (default MIL), order does not matter
        :param team_b: the other team (default TBR), with team_a this picks the series out of the schedule
        :param rotation_len: number of starting pitchers in the rotation (1 to 5)
        :param round_name: label for the series in the output, e.g. "World Series"
        :param num_series: how many times run_all plays the series, tallying the winners
        :param output_handler: optional handler for series output, defaults to console
        """
        if team_a == team_b:
            raise ValueError(f"A series needs two different teams, got {team_a} twice")
        if not 1 <= rotation_len <= MAX_ROTATION_LEN:
            raise ValueError(f"rotation_len must be between 1 and {MAX_ROTATION_LEN}, got {rotation_len}")
        if num_series < 1:
            raise ValueError(f"num_series must be at least 1, got {num_series}")

        self.teams = (team_a, team_b)
        self.round_name = round_name
        self.num_series = num_series
        # set from the schedule when the series is run
        self.home_team: Optional[str] = None
        self.away_team: Optional[str] = None
        self.best_of: Optional[int] = None
        self.games_played: Optional[int] = None  # games the last series took
        self.games_to_win: dict[str, list[int]] = {team: [] for team in self.teams}  # per series, by winner

        self._season_args = dict(
            load_seasons=load_seasons if load_seasons is not None else [2020, 2021, 2022, 2023, 2024, 2025, 2026],
            new_season=new_season,
            team_list=list(self.teams),
            rotation_len=rotation_len,
            load_batter_file=load_batter_file,
            load_pitcher_file=load_pitcher_file,
            output_handler=output_handler,
        )
        self._season_used = False
        self._build_season()

    def _build_season(self) -> None:
        """Load the data into a new season, so nothing (fatigue, injuries, streaks, stats) carries over."""
        self.season = BaseballSeason(**self._season_args)
        valid_teams = set(self.season.baseball_data.get_all_team_names())
        for team in self.teams:
            if team not in valid_teams:
                raise ValueError(f"Unknown team {team}, valid teams: {sorted(valid_teams)}")

        self._reset_to_fresh_conditions()
        self._season_used = False

    def _reset_to_fresh_conditions(self) -> None:
        """Everyone starts rested with a 0-0 series record, regardless of how the data files were last saved."""
        data = self.season.baseball_data
        data.new_season_pitching_data["Condition"] = 100
        data.new_season_batting_data["Condition"] = 100
        for team in self.teams:
            self.season.team_win_loss[team] = [0, 0]

    def run(self, show_game_results: bool = True) -> str:
        """
        Simulate the series and return the winning team abbreviation. Each call starts from freshly loaded data.
        :param show_game_results: False suppresses all the series output (game results, off days, banners)
        """
        if self._season_used:
            self._build_season()
        self._season_used = True
        season = self.season
        if not show_game_results:
            season.output_handler = bbseason.null_output_handler  # this season object is replaced on the next run
        season.schedule_manager.clear_playoffs()
        games = season.schedule_manager.build_playoff_series_from_schedule(*self.teams, self.round_name)

        # the schedule sets home and away (game 1's host is the home team) and the length of the series
        self.home_team, self.away_team = games[0].home, games[0].away
        self.best_of = len(games)

        season.output_handler(
            bbseason.OutputCategory.PLAYOFF_ROUND_START,
            f"\n{'*' * 20} {self.round_name.upper()}: {self.away_team} at {self.home_team} {'*' * 20}\n",
        )
        winner = season.run_playoff_series(self.away_team, self.home_team, self.best_of, self.round_name)
        # records start at 0-0 for the series, so the wins of both teams are the games played
        self.games_played = sum(season.team_win_loss[team][0] for team in self.teams)

        winner_wins, winner_losses = season.team_win_loss[winner]
        city = season.team_city_dict.get(winner, winner)
        winner_label = winner if city == winner else f"{city} ({winner})"
        season.output_handler(
            bbseason.OutputCategory.PLAYOFF_ROUND_END,
            f"\n{'=' * 80}\n{winner_label} win the {self.round_name} {winner_wins}-{winner_losses}\n{'=' * 80}\n",
            metadata={"winner": winner},
        )
        return winner

    def _emit(self, text: str) -> None:
        """Print a summary line through the output handler the series was given (console by default)."""
        handler = self._season_args["output_handler"] or bbseason.console_output_handler
        handler(bbseason.OutputCategory.SIM_PROGRESS, text, None)

    def _simulate_independent_series(self) -> tuple[str, int]:
        """
        Play one series on its own freshly loaded season and return (winner, games played). Shares nothing with
        other series, so it is safe to call from several threads at once.
        """
        args = self._season_args
        series = BaseballPlayoffSeries(
            *self.teams,
            rotation_len=args["rotation_len"],
            round_name=self.round_name,
            num_series=1,
            load_seasons=args["load_seasons"],
            new_season=args["new_season"],
            load_batter_file=args["load_batter_file"],
            load_pitcher_file=args["load_pitcher_file"],
            output_handler=bbseason.null_output_handler,
        )
        winner = series.run(show_game_results=False)
        return winner, series.games_played

    def _run_series_in_threads(self, wins: dict[str, int], max_threads: int) -> None:
        """
        Play num_series series with up to max_threads running at once. Only this (the calling) thread updates the
        tally, as each series finishes, so the accumulated results need no locking. Series are numbered in the order
        they finish.
        """
        with ThreadPoolExecutor(max_workers=min(max_threads, self.num_series)) as executor:
            futures = [executor.submit(self._simulate_independent_series) for _ in range(self.num_series)]
            try:
                for number, future in enumerate(as_completed(futures), start=1):
                    winner, games_played = future.result()  # raises here if a series failed
                    wins[winner] += 1
                    self.games_to_win[winner].append(games_played)
                    self._emit(
                        f"Series {number} of {self.num_series}: {winner} wins. Series record: {self._record_text(wins)}\n"
                    )
            except BaseException:
                for future in futures:
                    future.cancel()  # don't start series that haven't begun
                raise

    def run_all(self, show_game_results: bool = False, max_threads: int = 1) -> dict[str, int]:
        """
        Simulate the series num_series times, each from freshly loaded data, and tally the winners.
        :param show_game_results: False (the default) prints only a line per series, the final record and the
            average games to win, True also prints the game by game results of every series
        :param max_threads: how many series can run at the same time, 1 runs them one after another. Game results
            can't be shown when more than one runs at once, the lines would interleave
        :return: series wins by team, in the order the teams were given, e.g. {"MIL": 3, "TBR": 1}. The games each
            winner needed are in games_to_win, see average_games_to_win
        """
        if max_threads < 1:
            raise ValueError(f"max_threads must be at least 1, got {max_threads}")
        if max_threads > 1 and show_game_results:
            raise ValueError("Game results can't be shown when series run in parallel, the output would interleave")

        wins = {team: 0 for team in self.teams}
        self.games_to_win = {team: [] for team in self.teams}
        spacing = "\n" if show_game_results else ""  # blank lines only help when game results are between the lines
        if max_threads > 1:
            self._emit(
                f"Multi-threaded run: up to {max_threads} threads, so several series play at the same time. "
                f"Series x of y is numbered in the order series finish, not the order they started, "
                f"so x does not identify a particular series.\n"
            )
            self._run_series_in_threads(wins, max_threads)
        else:
            for number in range(1, self.num_series + 1):
                if show_game_results:
                    self._emit(f"\n#### Series {number} of {self.num_series} ####\n")
                winner = self.run(show_game_results=show_game_results)
                wins[winner] += 1
                self.games_to_win[winner].append(self.games_played)
                self._emit(
                    f"{spacing}Series {number} of {self.num_series}: {winner} wins. Series record: "
                    f"{self._record_text(wins)}\n"
                )
        self._emit(f"{spacing}Series record after {self.num_series}: {self._record_text(wins)}\n")
        average_text = " ".join(
            f"{team} {'n/a' if average is None else format(average, '.1f')}"
            for team, average in self.average_games_to_win().items()
        )
        self._emit(f"Average games to win: {average_text}\n")
        return wins

    def average_games_to_win(self) -> dict[str, Optional[float]]:
        """Average number of games each team needed to win the series it won, None for a team with no wins."""
        return {team: (sum(games) / len(games) if games else None) for team, games in self.games_to_win.items()}

    @staticmethod
    def _record_text(wins: dict[str, int]) -> str:
        """Series wins as text, e.g. "MIL 3 TBR 1"."""
        return " ".join(f"{team} {count}" for team, count in wins.items())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate a playoff series from the schedule between two teams")
    parser.add_argument("team_a", nargs="?", default="MIL", help="One team abbreviation (default: MIL)")
    parser.add_argument("team_b", nargs="?", default="TBR", help="The other team abbreviation (default: TBR)")
    parser.add_argument("--round-name", default="Playoff Series", help='Label for the series, e.g. "World Series"')
    parser.add_argument("--rotation-len", type=int, default=4, help="Starting pitchers in the rotation (default: 4)")
    parser.add_argument("--num-series", type=int, default=4, help="Times to play the series, tallying winners (default: 4)")
    parser.add_argument("--max-threads", type=int, default=1, help="Series to run at the same time (default: 1)")
    parser.add_argument(
        "--show-game-results",
        action="store_true",
        help="Also print the game by game results (default: only a line per series and the final results)",
    )
    args = parser.parse_args()

    configure_logger("INFO", console_level="WARNING")  # INFO still goes to the log file, not the console
    BaseballPlayoffSeries(
        args.team_a, args.team_b, rotation_len=args.rotation_len, round_name=args.round_name, num_series=args.num_series
    ).run_all(show_game_results=args.show_game_results, max_threads=args.max_threads)
