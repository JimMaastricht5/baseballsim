import pandas as pd
import numpy as np

# --- CONFIGURATION ---
B_PROJ_FILE = '2023 2024 2025 aggr-stats-pp-Batting.csv'
B_HIST_FILE = '2023 2024 2025 historical-Batting.csv'
P_PROJ_FILE = '2023 2024 2025 aggr-stats-pp-Pitching.csv'
P_HIST_FILE = '2023 2024 2025 historical-Pitching.csv'


def check_batting_integrity():
    df_proj = pd.read_csv(B_PROJ_FILE)
    df_hist = pd.read_csv(B_HIST_FILE)
    df_25 = df_hist[df_hist['Season'] == 2025].copy()

    # Calculate Rates
    df_proj['BA'] = df_proj['H'] / df_proj['AB'].replace(0, 1)
    df_proj['BB_Rate'] = df_proj['BB'] / df_proj['PA'].replace(0, 1)
    df_proj['OBP'] = (df_proj['H'] + df_proj['BB'] + df_proj.get('HBP', 0)) / df_proj['PA'].replace(0, 1)

    print("=" * 90)
    print(f"{'HITTER INTEGRITY CHECK: THE OBP SINKHOLE':^90}")
    print("=" * 90)

    lg_ba = df_proj['H'].sum() / df_proj['AB'].sum()
    lg_obp = (df_proj['H'] + df_proj['BB']).sum() / df_proj['PA'].sum()
    lg_bb_rate = df_proj['BB'].sum() / df_proj['PA'].sum()

    print(f"League AVG: {lg_ba:.3f} | League OBP: {lg_obp:.3f} | League BB-Rate: {lg_bb_rate:.3f}")
    print(f"OBP Spread (OBP - AVG): {lg_obp - lg_ba:.3f} (Target: .070+)")

    if lg_obp < .310:
        print(f"!!! CRITICAL: League OBP is COLD ({lg_obp:.3f}). Increase H and BB weights in Preprocessor.")
    print("-" * 90)

    # Spotlights
    for name in ['Will Smith', 'Caleb Durbin', 'Cal Raleigh', 'Eric Haase', 'Brice Turang']:
        p_proj = df_proj[df_proj['Player'].str.contains(name, na=False)].iloc[0:1]
        p_hist = df_25[df_25['Player'].str.contains(name, na=False)].iloc[0:1]

        if not p_proj.empty and not p_hist.empty:
            print(f"\nDIAGNOSIS: {name}")
            stats = ['PA', 'AB', 'H', 'BB', 'SO', 'BA', 'OBP']

            # Add H/AB and BB/PA for rate-based tracking
            h_25 = p_hist['H'].values[0] / p_hist['AB'].values[0]
            bb_25 = p_hist['BB'].values[0] / p_hist['PA'].values[0]

            comp = pd.DataFrame({
                '2025 Act': [p_hist['PA'].iloc[0], p_hist['AB'].iloc[0], p_hist['H'].iloc[0], p_hist['BB'].iloc[0],
                             p_hist['SO'].iloc[0], h_25, bb_25],
                '2026 Proj': [p_proj['PA'].iloc[0], p_proj['AB'].iloc[0], p_proj['H'].iloc[0], p_proj['BB'].iloc[0],
                              p_proj['SO'].iloc[0], p_proj['BA'].iloc[0], p_proj['BB_Rate'].iloc[0]]
            }, index=['PA', 'AB', 'H', 'BB', 'SO', 'H/AB (BA)', 'BB/PA'])
            print(comp.round(3))


def check_pitching_integrity():
    df_proj = pd.read_csv(P_PROJ_FILE)
    df_hist = pd.read_csv(P_HIST_FILE)
    df_25 = df_hist[df_hist['Season'] == 2025].copy()

    # We care about Hits and Walks allowed (The OBP drivers)
    df_proj['H_PA'] = df_proj['H'] / df_proj['PA'].replace(0, 1)
    df_proj['BB_PA'] = df_proj['BB'] / df_proj['PA'].replace(0, 1)
    df_proj['OBP_Against'] = (df_proj['H'] + df_proj['BB']) / df_proj['PA'].replace(0, 1)

    print("\n" + "=" * 90)
    print(f"{'PITCHER INTEGRITY CHECK: THE PITCHER DOMINANCE LEAK':^90}")
    print("=" * 90)

    lg_h_pa = df_proj['H'].sum() / df_proj['PA'].sum()
    lg_bb_pa = df_proj['BB'].sum() / df_proj['PA'].sum()
    lg_obpa = lg_h_pa + lg_bb_pa

    print(f"League Hits/PA: {lg_h_pa:.3f} | League Walks/PA: {lg_bb_pa:.3f} | OBP Against: {lg_obpa:.3f}")

    if lg_obpa < .300:
        print(f"!!! WARNING: Pitchers are too dominant. Hits/PA should be closer to .240.")
    print("-" * 90)

    # Outlier detection for P
    stiflers = df_proj[(df_proj['PA'] > 200) & (df_proj['OBP_Against'] < 0.250)].sort_values('OBP_Against')
    if not stiflers.empty:
        print("PITCHERS SUPPRESSING OBP UNREALISTICALLY (< .250 OBP Against):")
        print(stiflers[['Player', 'PA', 'H_PA', 'BB_PA', 'OBP_Against']].head(10).to_string(index=False))


if __name__ == "__main__":
    check_batting_integrity()
    check_pitching_integrity()