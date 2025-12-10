"""
Main window for the baseball season simulation UI.

Provides the primary interface with toolbar controls, standings display,
game results, and tabs for schedule and injuries.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QTextEdit, QLabel,
    QToolBar, QPushButton, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from ui.season_worker import SeasonWorker
from bblogger import configure_logger

logger = configure_logger("INFO")


class SeasonMainWindow(QMainWindow):
    """
    Main application window for season simulation.

    Layout:
    - Menu bar with File, View, Simulation menus
    - Toolbar with control buttons (Start, Pause, Resume, Next Day, Stop)
    - Horizontal splitter:
      - Left (30%): Standings display (placeholder in Phase 1)
      - Right (70%): Tab widget with Today's Games, Schedule, Injuries
    - Status bar with day counter and simulation status
    """

    def __init__(self):
        """Initialize the main window and UI components."""
        super().__init__()

        # Window configuration
        self.setWindowTitle("Baseball Season Simulator")
        self.resize(1200, 800)

        # Season worker (created when simulation starts)
        self.worker = None

        # Setup UI components
        self._create_menus()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

        # Initial button states
        self._update_button_states(simulation_running=False, paused=False)

        logger.info("Main window initialized")

    def _create_menus(self):
        """Create menu bar with File, View, and Simulation menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu (for future expansion)
        view_menu = menubar.addMenu("&View")

        # Simulation menu
        sim_menu = menubar.addMenu("&Simulation")

        start_action = QAction("&Start Season", self)
        start_action.triggered.connect(self.start_season)
        sim_menu.addAction(start_action)

        pause_action = QAction("&Pause", self)
        pause_action.triggered.connect(self.pause_season)
        sim_menu.addAction(pause_action)

        resume_action = QAction("&Resume", self)
        resume_action.triggered.connect(self.resume_season)
        sim_menu.addAction(resume_action)

        sim_menu.addSeparator()

        stop_action = QAction("&Stop", self)
        stop_action.triggered.connect(self.stop_season)
        sim_menu.addAction(stop_action)

    def _create_toolbar(self):
        """Create toolbar with control buttons."""
        toolbar = QToolBar("Controls")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Start button
        self.start_btn = QPushButton("Start Season")
        self.start_btn.clicked.connect(self.start_season)
        toolbar.addWidget(self.start_btn)

        toolbar.addSeparator()

        # Pause button
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_season)
        toolbar.addWidget(self.pause_btn)

        # Resume button
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.clicked.connect(self.resume_season)
        toolbar.addWidget(self.resume_btn)

        # Next Day button
        self.next_day_btn = QPushButton("Next Day")
        self.next_day_btn.clicked.connect(self.next_day)
        toolbar.addWidget(self.next_day_btn)

        toolbar.addSeparator()

        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_season)
        toolbar.addWidget(self.stop_btn)

    def _create_central_widget(self):
        """Create the main layout with splitter, standings, and tabs."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Horizontal splitter for standings (left) and content (right)
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: Standings (placeholder for Phase 1)
        self.standings_placeholder = QTextEdit()
        self.standings_placeholder.setReadOnly(True)
        self.standings_placeholder.setPlaceholderText("Standings will appear here...")
        splitter.addWidget(self.standings_placeholder)

        # Right panel: Tab widget
        self.tab_widget = QTabWidget()

        # Tab 1: Today's Games
        self.games_text = QTextEdit()
        self.games_text.setReadOnly(True)
        self.games_text.setPlaceholderText("Game results will appear here...")
        self.tab_widget.addTab(self.games_text, "Today's Games")

        # Tab 2: Schedule (placeholder)
        self.schedule_placeholder = QTextEdit()
        self.schedule_placeholder.setReadOnly(True)
        self.schedule_placeholder.setPlaceholderText("Upcoming schedule will appear here...")
        self.tab_widget.addTab(self.schedule_placeholder, "Schedule")

        # Tab 3: Injuries (placeholder)
        self.injuries_placeholder = QTextEdit()
        self.injuries_placeholder.setReadOnly(True)
        self.injuries_placeholder.setPlaceholderText("Injury report will appear here...")
        self.tab_widget.addTab(self.injuries_placeholder, "Injuries")

        splitter.addWidget(self.tab_widget)

        # Set splitter proportions (30% left, 70% right)
        splitter.setSizes([360, 840])

        layout.addWidget(splitter)

    def _create_status_bar(self):
        """Create status bar with day counter and status message."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Day counter label
        self.day_label = QLabel("Day: 0 / 162")
        self.status_bar.addPermanentWidget(self.day_label)

        # Status message
        self.status_bar.showMessage("Ready to start season simulation")

    def start_season(self):
        """
        Start the season simulation.

        Creates a SeasonWorker, connects signals, and starts the worker thread.
        """
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Already Running",
                                "A season simulation is already running.")
            return

        logger.info("Starting season simulation")

        # Create worker with simulation parameters
        # For Phase 1, using default parameters
        self.worker = SeasonWorker(
            load_seasons=[2023, 2024, 2025],
            new_season=2026,
            team_to_follow=['NYM'],  # Default followed team
            random_data=False,
            rotation_len=5,
            num_games=162,
            only_nl_b=False
        )

        # Connect signals
        self.worker.signals.day_started.connect(self.on_day_started)
        self.worker.signals.game_completed.connect(self.on_game_completed)
        self.worker.signals.day_completed.connect(self.on_day_completed)
        self.worker.signals.gm_assessment_ready.connect(self.on_gm_assessment)
        self.worker.signals.injury_update.connect(self.on_injury_update)
        self.worker.signals.simulation_complete.connect(self.on_simulation_complete)
        self.worker.signals.error_occurred.connect(self.on_error)

        # Start worker thread
        self.worker.start()

        # Update UI state
        self._update_button_states(simulation_running=True, paused=False)
        self.status_bar.showMessage("Simulation started...")

    def pause_season(self):
        """Pause the simulation."""
        if self.worker and self.worker.isRunning():
            logger.info("Pausing simulation")
            self.worker.pause()
            self._update_button_states(simulation_running=True, paused=True)
            self.status_bar.showMessage("Simulation paused")

    def resume_season(self):
        """Resume the simulation from paused state."""
        if self.worker and self.worker.isRunning():
            logger.info("Resuming simulation")
            self.worker.resume()
            self._update_button_states(simulation_running=True, paused=False)
            self.status_bar.showMessage("Simulation resumed")

    def next_day(self):
        """Advance exactly one day, then pause."""
        if self.worker and self.worker.isRunning():
            logger.info("Advancing one day")
            self.worker.step_one_day()
            self._update_button_states(simulation_running=True, paused=False)
            self.status_bar.showMessage("Advancing one day...")

    def stop_season(self):
        """Stop the simulation entirely."""
        if self.worker and self.worker.isRunning():
            logger.info("Stopping simulation")
            self.worker.stop()
            self.worker.wait()  # Wait for thread to finish
            self._update_button_states(simulation_running=False, paused=False)
            self.status_bar.showMessage("Simulation stopped")

    def _update_button_states(self, simulation_running, paused):
        """
        Update button enabled/disabled states based on simulation state.

        Args:
            simulation_running (bool): Whether a simulation is currently running
            paused (bool): Whether the simulation is paused
        """
        self.start_btn.setEnabled(not simulation_running)
        self.pause_btn.setEnabled(simulation_running and not paused)
        self.resume_btn.setEnabled(simulation_running and paused)
        self.next_day_btn.setEnabled(simulation_running)
        self.stop_btn.setEnabled(simulation_running)

    # Signal handlers

    def on_day_started(self, day_num, schedule_text):
        """
        Handle day_started signal.

        Args:
            day_num (int): Current day number (0-indexed)
            schedule_text (str): Schedule for the day
        """
        logger.debug(f"Day {day_num + 1} started")
        self.day_label.setText(f"Day: {day_num + 1} / 162")
        self.status_bar.showMessage(f"Simulating day {day_num + 1}...")

        # Clear previous day's game results
        self.games_text.clear()
        self.games_text.append(f"=== Day {day_num + 1} ===\n")
        self.games_text.append(schedule_text + "\n\n")

    def on_game_completed(self, game_data):
        """
        Handle game_completed signal (followed team).

        Args:
            game_data (dict): Game result data with recap
        """
        logger.debug(f"Followed game completed: {game_data['away_team']} @ {game_data['home_team']}")
        self.games_text.append("=== Your Teams ===")
        self.games_text.append(game_data['game_recap'])
        self.games_text.append("\n")
        self.games_text.ensureCursorVisible()  # Auto-scroll

    def on_day_completed(self, game_results, standings_data):
        """
        Handle day_completed signal.

        Args:
            game_results (list): Batch of non-followed game results
            standings_data (dict): Current standings
        """
        logger.debug(f"Day completed with {len(game_results)} other games")

        # Display batch results in compact format
        if game_results:
            self.games_text.append("=== Today's Scores ===")
            for game in game_results:
                self.games_text.append(
                    f"{game['away_team']:>3} {game['away_r']:>2}  {game['away_h']:>2}  {game['away_e']:>1}    "
                    f"{game['home_team']:>3} {game['home_r']:>2}  {game['home_h']:>2}  {game['home_e']:>1}"

            self.games_text.append("\n")

        # Update standings display (placeholder for Phase 1)
        self._update_standings_display(standings_data)

        self.status_bar.showMessage(f"Day {standings_data.get('_day_num', '?')} complete")

    def _update_standings_display(self, standings_data):
        """
        Update standings placeholder with text display.

        Args:
            standings_data (dict): Standings with teams, wins, losses, pct, gb
        """
        self.standings_placeholder.clear()
        self.standings_placeholder.append("=== STANDINGS ===\n")
        self.standings_placeholder.append(f"{'Team':<5} {'W-L':<10} {'Pct':<6} {'GB':<4}\n")
        self.standings_placeholder.append("-" * 30 + "\n")

        teams = standings_data.get('teams', [])
        wins = standings_data.get('wins', [])
        losses = standings_data.get('losses', [])
        pcts = standings_data.get('pct', [])
        gbs = standings_data.get('gb', [])

        for i in range(len(teams)):
            wl = f"{wins[i]}-{losses[i]}"
            self.standings_placeholder.append(
                f"{teams[i]:<5} {wl:<10} {pcts[i]:<6.3f} {gbs[i]:<4}\n"
            )

    def on_gm_assessment(self, assessment_data):
        """
        Handle gm_assessment_ready signal.

        Args:
            assessment_data (dict): GM assessment report
        """
        team = assessment_data.get('team', 'Unknown')
        games = assessment_data.get('games_played', 0)
        logger.info(f"GM assessment ready for {team} at {games} games")

        # For Phase 1, just show a message
        # Phase 7 will implement full dialog
        QMessageBox.information(
            self,
            "GM Assessment",
            f"GM Assessment for {team} at {games} games\n\n"
            f"(Full report dialog will be implemented in Phase 7)"
        )

    def on_injury_update(self, injury_list):
        """
        Handle injury_update signal.

        Args:
            injury_list (list): List of injured players
        """
        logger.debug(f"Injury update: {len(injury_list)} injured players")

        # Update injuries placeholder
        self.injuries_placeholder.clear()
        self.injuries_placeholder.append("=== INJURY REPORT ===\n\n")

        if not injury_list:
            self.injuries_placeholder.append("No injured players")
        else:
            for injury in injury_list:
                self.injuries_placeholder.append(
                    f"{injury['player']} ({injury['team']}) - {injury['injury']}\n"
                    f"  Position: {injury['position']}, Days remaining: {injury['days_remaining']}, "
                    f"Status: {injury['status']}\n\n"
                )

    def on_simulation_complete(self):
        """Handle simulation_complete signal."""
        logger.info("Season simulation completed")
        self._update_button_states(simulation_running=False, paused=False)
        self.status_bar.showMessage("Season complete!")
        QMessageBox.information(self, "Season Complete",
                                "The season simulation has completed successfully.")

    def on_error(self, error_message):
        """
        Handle error_occurred signal.

        Args:
            error_message (str): Error description
        """
        logger.error(f"Simulation error: {error_message}")
        QMessageBox.critical(self, "Simulation Error", error_message)
        self._update_button_states(simulation_running=False, paused=False)
        self.status_bar.showMessage("Error occurred")

    def closeEvent(self, event):
        """
        Handle window close event.

        Ensures worker thread is stopped before closing.
        """
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Simulation Running",
                "A simulation is currently running. Stop it and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
