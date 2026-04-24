"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

--- File Context and Purpose ---
SHARED MODULE: Player history popup functionality
Displays player historical stats, projected stats, and current season stats in a popup.
Used by roster_widget.py and league_stats_widget.py.
"""

import tkinter as tk
from tkinter import ttk
from ui.theme import BG_PANEL


def show_history_popup(
    parent,
    player_name: str,
    historical_df,
    is_batter: bool,
    projected_row=None,
    current_season_row=None,
    current_season: int = None,
):
    """
    Open a popup window showing player stats:
    - Projected row at top (from projection files)
    - Current season accumulated stats
    - Historical seasons below

    Args:
        parent: Parent window (for tk.Toplevel)
        player_name: Player name for window title
        historical_df: DataFrame with historical stats (excluding current season)
        is_batter: True for batting columns, False for pitching columns
        projected_row: Optional Series with projected new-season stats
        current_season_row: Optional Series with current season accumulated stats
        current_season: Current season year (e.g., 2026)
    """
    popup = tk.Toplevel(parent)
    popup.title(f"{player_name} - Historical Stats")
    popup.geometry("1100x350")
    popup.resizable(True, True)
    popup.configure(bg=BG_PANEL)

    if is_batter:
        columns = (
            "Season",
            "Team",
            "Age",
            "G",
            "AB",
            "R",
            "H",
            "2B",
            "3B",
            "HR",
            "RBI",
            "BB",
            "K",
            "AVG",
            "OBP",
            "SLG",
            "OPS",
        )
    else:
        columns = (
            "Season",
            "Team",
            "Age",
            "G",
            "GS",
            "IP",
            "W",
            "L",
            "H",
            "R",
            "ER",
            "HR",
            "BB",
            "SO",
            "ERA",
            "WHIP",
        )

    tree_frame = tk.Frame(popup, bg=BG_PANEL)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    tree = ttk.Treeview(
        tree_frame,
        columns=columns,
        show="headings",
        height=8,
        yscrollcommand=scrollbar.set,
    )
    scrollbar.config(command=tree.yview)
    tree.tag_configure("projected", foreground="#d4a017")

    for col in columns:
        tree.heading(col, text=col)
        if col in ["Season", "Team"]:
            tree.column(col, width=60, anchor=tk.CENTER)
        elif col in ["Age", "G", "GS", "W", "L"]:
            tree.column(col, width=40, anchor=tk.CENTER)
        elif col in ["AB", "R", "H", "HR", "RBI", "SO"]:
            tree.column(col, width=45, anchor=tk.CENTER)
        elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
            tree.column(col, width=55, anchor=tk.CENTER)
        elif col == "IP":
            tree.column(col, width=50, anchor=tk.CENTER)
        else:
            tree.column(col, width=50, anchor=tk.CENTER)

    tree.pack(fill=tk.BOTH, expand=True)

    def _copy_history():
        sel = tree.selection()
        if not sel:
            return
        header = "\t".join(columns)
        rows = ["\t".join(str(v) for v in tree.item(i, "values")) for i in sel]
        tree.clipboard_clear()
        tree.clipboard_append(header + "\n" + "\n".join(rows))

    def _show_history_copy_menu(event):
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(label="Copy Row", command=_copy_history)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    tree.bind("<Button-3>", _show_history_copy_menu)
    tree.bind("<Control-c>", lambda e: _copy_history())

    def _format_batter_row(r, season_label: str):
        avg_val = r.get("AVG", r.get("BA", 0))
        return (
            season_label,
            r.get("Team", ""),
            int(r.get("Age", 0)),
            int(r.get("G", 0)),
            int(r.get("AB", 0)),
            int(r.get("R", 0)),
            int(r.get("H", 0)),
            int(r.get("2B", 0)),
            int(r.get("3B", 0)),
            int(r.get("HR", 0)),
            int(r.get("RBI", 0)),
            int(r.get("BB", 0)),
            int(r.get("SO", 0)),
            f"{float(avg_val):.3f}",
            f"{float(r.get('OBP', 0)):.3f}",
            f"{float(r.get('SLG', 0)):.3f}",
            f"{float(r.get('OPS', 0)):.3f}",
        )

    def _format_pitcher_row(r, season_label: str):
        return (
            season_label,
            r.get("Team", ""),
            int(r.get("Age", 0)),
            int(r.get("G", 0)),
            int(r.get("GS", 0)),
            f"{float(r.get('IP', 0)):.1f}",
            int(r.get("W", 0)),
            int(r.get("L", 0)),
            int(r.get("H", 0)),
            int(r.get("R", 0)),
            int(r.get("ER", 0)),
            int(r.get("HR", 0)),
            int(r.get("BB", 0)),
            int(r.get("SO", 0)),
            f"{float(r.get('ERA', 0)):.2f}",
            f"{float(r.get('WHIP', 0)):.2f}",
        )

    if projected_row is not None:
        try:
            r = projected_row
            if is_batter:
                values = _format_batter_row(r, "Projected")
            else:
                values = _format_pitcher_row(r, "Projected")
            tree.insert("", tk.END, values=values, tags=("projected",))
        except Exception as e:
            print(f"Warning: Error inserting projected row: {e}")

    if current_season_row is not None:
        try:
            r = current_season_row
            if is_batter:
                values = _format_batter_row(r, str(current_season))
            else:
                values = _format_pitcher_row(r, str(current_season))
            tree.insert("", tk.END, values=values)
        except Exception as e:
            print(f"Warning: Error inserting current season row: {e}")

    if current_season and "Season" in historical_df.columns:
        historical_df = historical_df[historical_df["Season"] != current_season]

    for idx, row in historical_df.iterrows():
        try:
            if is_batter:
                values = (
                    int(row.get("Season", 0)),
                    row.get("Team", ""),
                    int(row.get("Age", 0)),
                    int(row.get("G", 0)),
                    int(row.get("AB", 0)),
                    int(row.get("R", 0)),
                    int(row.get("H", 0)),
                    int(row.get("2B", 0)),
                    int(row.get("3B", 0)),
                    int(row.get("HR", 0)),
                    int(row.get("RBI", 0)),
                    int(row.get("BB", 0)),
                    int(row.get("SO", 0)),
                    f"{float(row.get('AVG', 0)):.3f}",
                    f"{float(row.get('OBP', 0)):.3f}",
                    f"{float(row.get('SLG', 0)):.3f}",
                    f"{float(row.get('OPS', 0)):.3f}",
                )
            else:
                values = (
                    int(row.get("Season", 0)),
                    row.get("Team", ""),
                    int(row.get("Age", 0)),
                    int(row.get("G", 0)),
                    int(row.get("GS", 0)),
                    f"{float(row.get('IP', 0)):.1f}",
                    int(row.get("W", 0)),
                    int(row.get("L", 0)),
                    int(row.get("H", 0)),
                    int(row.get("R", 0)),
                    int(row.get("ER", 0)),
                    int(row.get("HR", 0)),
                    int(row.get("BB", 0)),
                    int(row.get("SO", 0)),
                    f"{float(row.get('ERA', 0)):.2f}",
                    f"{float(row.get('WHIP', 0)):.2f}",
                )
            tree.insert("", tk.END, values=values)
        except Exception as e:
            print(f"Warning: Error inserting historical row: {e}")

    ttk.Button(popup, text="Close", command=popup.destroy, width=10).pack(pady=5)
    popup.focus_set()
    return popup