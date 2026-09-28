"""
Monte Carlo season simulator.

Runs many independent full-season simulations (regular season + playoffs) and
tallies World Series appearances, wins, and matchups across all runs. Each
iteration is fully independent, so iterations are distributed across a pool of
worker processes (via ProcessPoolExecutor) to use multiple CPU cores instead of
running the loop serially in a single process.

Usage:
    python season_monte_carlo.py --iterations 1000 --workers 10
"""

import argparse
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

import bbseason
from bblogger import configure_logger


def _run_one_season(new_season: int = 2026) -> dict:
    """Run one full season + playoff simulation and return the World Series result.

    Defined at module level (not nested) so ProcessPoolExecutor can pickle and ship
    it to worker processes. Each call happens in its own process with its own
    interpreter/GIL, so CPU-bound season sims run truly in parallel instead of
    serialized behind the GIL like Python threads would be.
    """
    configure_logger("WARNING")  # each worker process starts fresh; re-suppress noisy logging

    # Accumulates the one result we care about from this run; populated by the
    # tracking_handler callback as the season's output events fire.
    result = {"al_winner": None, "nl_winner": None, "champion": None}

    def tracking_handler(category, text, metadata=None):
        """Capture the World Series matchup and champion from the season's output events."""
        if category == bbseason.OutputCategory.WORLD_SERIES_START:
            if metadata:
                result["al_winner"] = metadata.get("al_winner")
                result["nl_winner"] = metadata.get("nl_winner")
        elif category == bbseason.OutputCategory.WORLD_SERIES_END:
            if metadata:
                result["champion"] = metadata.get("champion")

    # Build a fresh season: loads player/team data from CSVs, sets up the
    # regular-season schedule, and applies the real-world injury report.
    season = bbseason.BaseballSeason(
        load_seasons=[2020, 2021, 2022, 2023, 2024, 2025, 2026],
        new_season=new_season,
        season_length=162,
        series_length=3,
        rotation_len=5,
        season_interactive=False,
        season_chatty=False,
        season_print_lineup_b=False,
        season_print_box_score_b=False,
        suppress_console_output=True,
        output_handler=tracking_handler,
        load_batter_file="player-projected-stats-pp-Batting.csv",
        load_pitcher_file="player-projected-stats-pp-Pitching.csv",
        load_schedule_file="2026 MLB Schedule.csv",
        il_file="il_report_2026.csv",
    )

    # Run the full 162-game regular season and, if the followed criteria are met,
    # the playoffs through the World Series; tracking_handler captures the outcome.
    season.sim_full_season()
    return result


def run_monte_carlo(iterations: int = 1000, workers: int = 10) -> None:
    """Run `iterations` independent season simulations across a pool of worker processes.

    Distributes the simulations across `workers` OS processes (not threads) so the
    work runs on multiple CPU cores in parallel instead of being serialized behind
    the GIL. Results are tallied into Counters and a summary is printed at the end.

    :param iterations: Number of independent season simulations to run.
    :param workers: Number of worker processes to run simulations in parallel.
    :return: None
    """
    # Suppress all the standard INFO logging to make the loop run quietly
    configure_logger("WARNING")

    ws_appearances = Counter()  # team -> number of World Series appearances
    ws_wins = Counter()  # team -> number of World Series championships
    ws_matchups = Counter()  # "AL vs NL" -> number of times that matchup occurred

    print(f"Starting {iterations} season simulations across {workers} worker processes. This may take a while...\n")
    start_time = time.time()

    completed = 0
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit every iteration up front; the pool schedules them across workers
        # as slots free up, so at most `workers` seasons ever run at once.
        futures = [executor.submit(_run_one_season) for _ in range(iterations)]
        # as_completed yields results in the order runs finish (not submission order),
        # which gives real-time progress feedback as soon as any worker finishes.
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            al_winner = result.get("al_winner")
            nl_winner = result.get("nl_winner")
            champion = result.get("champion")

            if al_winner and nl_winner:
                ws_appearances[al_winner] += 1
                ws_appearances[nl_winner] += 1
                ws_matchups[f"{al_winner} vs {nl_winner}"] += 1

            if champion:
                ws_wins[champion] += 1
                print(f"Iteration {completed}/{iterations}: {champion} wins")
            else:
                print(f"Iteration {completed}/{iterations}: No winner determined (Simulation did not complete playoffs)")

    # --- Print Results ---
    elapsed = time.time() - start_time
    print("\n" + "=" * 50)
    print(f"{iterations:,} SEASON SIMULATION RESULTS (Took {elapsed / 60:.1f} minutes)")
    print("=" * 50)

    print("\n🏆 WORLD SERIES CHAMPIONSHIPS:")
    for team, wins in ws_wins.most_common():
        print(f"{team}: {wins} ({(wins / iterations) * 100:.1f}%)")

    print("\n⚾ WORLD SERIES APPEARANCES:")
    for team, apps in ws_appearances.most_common():
        print(f"{team}: {apps} ({(apps / iterations) * 100:.1f}%)")

    print("\n⚔️ MOST COMMON MATCHUPS:")
    for matchup, count in ws_matchups.most_common(10):
        print(f"{matchup}: {count} times ({(count / iterations) * 100:.1f}%)")


if __name__ == "__main__":
    # CLI entry point: `python season_monte_carlo.py --iterations 1000 --workers 10`
    parser = argparse.ArgumentParser(description="Run a Monte Carlo simulation of the season across worker processes")
    parser.add_argument("--iterations", type=int, default=1000, help="Number of season simulations to run")
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of worker processes (default: 10)",
    )
    args = parser.parse_args()

    run_monte_carlo(iterations=args.iterations, workers=args.workers)
