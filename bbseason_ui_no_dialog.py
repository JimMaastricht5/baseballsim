"""
Launch script without startup dialog for testing
"""
import datetime
from bbseason_ui import main

if __name__ == "__main__":
    start_time = datetime.datetime.now()

    # Launch without startup dialog
    main(load_seasons=[2023, 2024, 2025],
         new_season=2026,
         season_length=162,
         series_length=3,
         rotation_len=5,
         season_chatty=True,
         season_print_lineup_b=True,
         season_print_box_score_b=True,
         season_team_to_follow='MIL',
         show_startup_dialog=False)  # DISABLED FOR TESTING

    end_time = datetime.datetime.now()
    run_time = end_time - start_time
    total_seconds = run_time.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    print(f'Total run time: {minutes} minutes, {seconds} seconds')
