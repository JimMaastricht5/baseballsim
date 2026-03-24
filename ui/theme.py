"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Dark theme configuration for the baseball simulation UI.

Defines the full color palette and exposes setup_dark_theme() which configures
all ttk styles globally in a single call.  Individual tk.* widgets still need
bg/fg set by hand; ttk.* widgets inherit the global styles.
"""

import tkinter as tk
from tkinter import ttk

# ── Background layers ─────────────────────────────────────────────────────────
BG_DARK      = "#0d1117"   # Root window, toolbar, status bar
BG_PANEL     = "#161b27"   # Main panels (standings, tab frames)
BG_WIDGET    = "#1c2333"   # Treeview / ScrolledText backgrounds
BG_ELEVATED  = "#21262d"   # Input fields, slightly raised elements

# ── Accent colours ────────────────────────────────────────────────────────────
ACCENT_BLUE  = "#58a6ff"   # Active tabs, column headers, links
ACCENT_GOLD  = "#d4a017"   # Followed team, day-header text
ACCENT_GREEN = "#2ea043"   # Start Season button
ACCENT_ORANGE= "#e0882d"   # Pause button

# ── Text colours ──────────────────────────────────────────────────────────────
TEXT_PRIMARY   = "#e6edf3"  # Main readable text
TEXT_SECONDARY = "#8b949e"  # Subdued labels, qualifiers
TEXT_HEADING   = "#ffffff"  # Section headings (STANDINGS, RESULTS…)

# ── Row colours ───────────────────────────────────────────────────────────────
ROW_EVEN     = "#1c2333"
ROW_ODD      = "#161b27"
ROW_SELECTED = "#1f3b5e"
ROW_FOLLOWED = "#2a3f1c"   # Subtle green tint for followed team row
FG_FOLLOWED  = "#d4a017"   # Gold text for followed team

# ── Misc ──────────────────────────────────────────────────────────────────────
BORDER       = "#30363d"   # Frame borders, separators

# ── Injury row colours (adapted for dark bg) ──────────────────────────────────
ROW_IL       = "#3d1515"   # Dark red for IL players
ROW_DTD      = "#2e2a00"   # Dark yellow for day-to-day players


def setup_dark_theme(root: tk.Tk) -> None:
    """
    Apply the dark theme globally to a tkinter root window.

    Configures the root window background and all ttk styles in one call.
    Call this before creating any widgets so that the styles are available
    when widgets are instantiated.

    Args:
        root: The root tkinter window
    """
    root.configure(bg=BG_DARK)

    style = ttk.Style(root)
    style.theme_use('default')

    # ── Notebook (tabs) ───────────────────────────────────────────────────────
    style.configure("TNotebook", background=BG_DARK, borderwidth=0)
    style.configure("TNotebook.Tab",
        background=BG_PANEL, foreground=TEXT_SECONDARY,
        padding=[12, 6], font=('Segoe UI', 10, 'bold'))
    style.map("TNotebook.Tab",
        background=[('selected', ACCENT_BLUE), ('active', '#2d5a9e')],
        foreground=[('selected', TEXT_HEADING), ('active', TEXT_HEADING)])

    # ── Treeview ──────────────────────────────────────────────────────────────
    style.configure("Treeview",
        background=BG_WIDGET, foreground=TEXT_PRIMARY,
        fieldbackground=BG_WIDGET, rowheight=22,
        font=('Segoe UI', 9))
    style.configure("Treeview.Heading",
        background=BG_PANEL, foreground=ACCENT_BLUE,
        font=('Segoe UI', 9, 'bold'), relief='flat')
    style.map("Treeview",
        background=[('selected', ROW_SELECTED)],
        foreground=[('selected', TEXT_HEADING)])

    # ── Scrollbar ─────────────────────────────────────────────────────────────
    style.configure("TScrollbar",
        background=BG_PANEL, troughcolor=BG_DARK,
        arrowcolor=TEXT_SECONDARY, borderwidth=0)

    # ── Progressbar ───────────────────────────────────────────────────────────
    style.configure("TProgressbar",
        background=ACCENT_BLUE, troughcolor=BG_DARK)

    # ── Combobox ──────────────────────────────────────────────────────────────
    style.configure("TCombobox",
        background=BG_ELEVATED, foreground=TEXT_PRIMARY,
        fieldbackground=BG_ELEVATED, arrowcolor=TEXT_SECONDARY,
        selectbackground=ROW_SELECTED, insertcolor=TEXT_PRIMARY)
    style.map("TCombobox",
        fieldbackground=[('readonly', BG_ELEVATED), ('disabled', BG_PANEL)],
        foreground=[('readonly', TEXT_PRIMARY), ('disabled', TEXT_SECONDARY)],
        selectbackground=[('readonly', BG_ELEVATED)])

    # ── Separator ─────────────────────────────────────────────────────────────
    style.configure("TSeparator", background=BORDER)

    # ── Generic ttk frame / label (fallback) ─────────────────────────────────
    style.configure("TFrame", background=BG_PANEL)
    style.configure("TLabel", background=BG_PANEL, foreground=TEXT_PRIMARY)

    # ── Named button styles ───────────────────────────────────────────────────
    style.configure("Start.TButton",
        background=ACCENT_GREEN, foreground=TEXT_HEADING,
        font=('Segoe UI', 10, 'bold'), relief='flat', padding=[8, 4])
    style.map("Start.TButton",
        background=[('active', '#3bb54a'), ('disabled', BG_ELEVATED)],
        foreground=[('disabled', TEXT_SECONDARY)])

    style.configure("Pause.TButton",
        background=ACCENT_ORANGE, foreground=TEXT_HEADING,
        font=('Segoe UI', 10), relief='flat', padding=[8, 4])
    style.map("Pause.TButton",
        background=[('active', '#e89a3c'), ('disabled', BG_ELEVATED)],
        foreground=[('disabled', TEXT_SECONDARY)])

    style.configure("Nav.TButton",
        background=BG_ELEVATED, foreground=TEXT_PRIMARY,
        font=('Segoe UI', 10), relief='flat', padding=[8, 4])
    style.map("Nav.TButton",
        background=[('active', '#2d333b'), ('disabled', BG_PANEL)],
        foreground=[('disabled', TEXT_SECONDARY)])

    style.configure("GM.TButton",
        background=ACCENT_BLUE, foreground=TEXT_HEADING,
        font=('Segoe UI', 10, 'bold'), relief='flat', padding=[8, 4])
    style.map("GM.TButton",
        background=[('active', '#79b8ff'), ('disabled', BG_ELEVATED)],
        foreground=[('disabled', TEXT_SECONDARY)])

    style.configure("Action.TButton",
        background="#4CAF50", foreground=TEXT_HEADING,
        font=('Segoe UI', 10, 'bold'), relief='flat', padding=[8, 4])
    style.map("Action.TButton",
        background=[('active', '#5cbf60'), ('disabled', BG_ELEVATED)],
        foreground=[('disabled', TEXT_SECONDARY)])

    style.configure("Save.TButton",
        background="#2196F3", foreground=TEXT_HEADING,
        font=('Segoe UI', 10, 'bold'), relief='flat', padding=[8, 4])
    style.map("Save.TButton",
        background=[('active', '#42a5f5'), ('disabled', BG_ELEVATED)],
        foreground=[('disabled', TEXT_SECONDARY)])
