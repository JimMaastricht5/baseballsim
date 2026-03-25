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


def diagnose_h_surplus():
    # Load all datasets
    df_b_proj = pd.read_csv(B_PROJ_FILE)
    df_b_hist = pd.read_csv(B_HIST_FILE)
    df_p_proj = pd.read_csv(P_PROJ_FILE)
    df_p_hist = pd.read_csv(P_HIST_FILE)

    # Filter for 2025 (The Baseline)
    b_25 = df_b_hist[df_b_hist['Season'] == 2025]
    p_25 = df_p_hist[df_p_hist['Season'] == 2025]

    # Calculate Aggregate H/PA (The true "Hit Density" metric)
    # Using PA as the denominator for both avoids AB vs BF confusion
    b_25_h_rate = b_25['H'].sum() / b_25['PA'].sum()
    b_26_h_rate = df_b_proj['H'].sum() / df_b_proj['PA'].sum()

    p_25_h_rate = p_25['H'].sum() / p_25['PA'].sum()
    p_26_h_rate = df_p_proj['H'].sum() / df_p_proj['PA'].sum()

    # Calculate Deltas (Points of H/PA)
    hitter_delta = (b_26_h_rate - b_25_h_rate) * 1000
    pitcher_delta = (p_26_h_rate - p_25_h_rate) * 1000

    # Add after existing rate calculations
    p_25['BIP'] = p_25['PA'] - p_25['SO'] - p_25['BB']
    p_26_bip = df_p_proj['PA'] - df_p_proj['SO'] - df_p_proj['BB']
    bip_25_rate = p_25['H'].sum() / p_25['BIP'].sum()
    bip_26_rate = df_p_proj['H'].sum() / p_26_bip.sum()

    print("\n" + "=" * 90)
    print(f"{'HIT INFLATION DIAGNOSTIC (Rates per 1000 PA)':^90}")
    print("=" * 90)

    results = pd.DataFrame({
        '2025 Hist Rate': [b_25_h_rate, p_25_h_rate],
        '2026 Proj Rate': [b_26_h_rate, p_26_h_rate],
        'Delta (Points)': [hitter_delta, pitcher_delta]
    }, index=['Hitters (H/PA)', 'Pitchers (H_Allowed/PA)'])

    print(results.round(4))
    print("-" * 90)

    if hitter_delta > pitcher_delta:
        print(f"PROBABLE CULPRIT: HITTERS. They are projected for {hitter_delta:.1f} more hits per 1000 PA than 2025.")
    else:
        print(f"PROBABLE CULPRIT: PITCHERS. They are allowing {pitcher_delta:.1f} more hits per 1000 PA than 2025.")


def identify_pitching_outliers(min_pa=50):
    df_proj = pd.read_csv(P_PROJ_FILE)
    df_hist = pd.read_csv(P_HIST_FILE)
    df_25 = df_hist[df_hist['Season'] == 2025].copy()

    # Calculate 2025 Historical Rates
    df_25['H_PA_25'] = df_25['H'] / df_25['PA'].replace(0, 1)

    # Merge on Player
    merged = pd.merge(
        df_proj[['Player', 'PA', 'H']],
        df_25[['Player', 'H_PA_25']],
        on='Player'
    )

    # Calculate Projection Rates
    merged['H_PA_26'] = merged['H'] / merged['PA'].replace(0, 1)

    # Calculate Delta and Weighted Impact
    # Impact = How many 'Extra Hits' this player adds to the league total
    merged['H_Delta'] = merged['H_PA_26'] - merged['H_PA_25']
    merged['H_Surplus'] = merged['H_Delta'] * merged['PA']

    # Filter for meaningful volume
    outliers = merged[merged['PA'] >= min_pa].sort_values('H_Surplus', ascending=False)

    print("\n" + "=" * 90)
    print(f"{'TOP 10 PITCHING HIT-INFLATION DRIVERS':^90}")
    print("=" * 90)
    print(outliers[['Player', 'PA', 'H_PA_25', 'H_PA_26', 'H_Delta', 'H_Surplus']].head(10).to_string(index=False))
    print("-" * 90)


def deep_dive_pitching_outliers():
    df_proj = pd.read_csv(P_PROJ_FILE)
    df_hist = pd.read_csv(P_HIST_FILE)
    df_25 = df_hist[df_hist['Season'] == 2025].copy()

    # Calculate Rates for 2025
    df_25['K_PA_25'] = df_25['SO'] / df_25['PA'].replace(0, 1)
    df_25['H_PA_25'] = df_25['H'] / df_25['PA'].replace(0, 1)

    # Calculate Rates for 2026 Proj
    df_proj['K_PA_26'] = df_proj['SO'] / df_proj['PA'].replace(0, 1)
    df_proj['H_PA_26'] = df_proj['H'] / df_proj['PA'].replace(0, 1)

    merged = pd.merge(df_proj, df_25[['Player', 'K_PA_25', 'H_PA_25']], on='Player')

    # Identify the "Why"
    merged['K_Loss'] = merged['K_PA_26'] - merged['K_PA_25']
    merged['H_Gain'] = merged['H_PA_26'] - merged['H_PA_25']

    # "The BABIP Leak": Hits are up, but Strikeouts are stable
    # "The Stuff Decay": Hits are up because Strikeouts are down
    print("\n" + "=" * 90)
    print(f"{'WHY ARE THEY LEAKING HITS?':^90}")
    print("=" * 90)
    print(merged.sort_values('H_Gain', ascending=False)[
              ['Player', 'PA', 'H_Gain', 'K_Loss']
          ].head(10).to_string(index=False))

def diagnose_bi_vs_pa_leakage():
    """Compare the actual denominators being used in projection vs historical."""
    df_b_hist = pd.read_csv(B_HIST_FILE)
    df_p_hist = pd.read_csv(P_HIST_FILE)
    df_p_proj = pd.read_csv(P_PROJ_FILE)

    # Pitcher BIP analysis - this is the key!
    p_25 = df_p_hist[df_p_hist['Season'] == 2025].copy()

    # Historical: calculate actual BIP for 2025
    p_25['BIP'] = p_25['PA'] - p_25['SO'] - p_25['BB']
    p_25_h_bip = p_25['H'].sum() / p_25['BIP'].sum()  # Historical H/BIP

    # Projected: calculate what the projection assumes
    df_p_proj['BIP'] = df_p_proj['PA'] - df_p_proj['SO'] - df_p_proj['BB']
    proj_h_bip = df_p_proj['H'].sum() / df_p_proj['BIP'].sum()  # Proj H/BIP

    print("\n" + "=" * 90)
    print(f"{'BIP LEAKAGE DIAGNOSTIC (The Real Problem)':^90}")
    print("=" * 90)
    print(f"2025 Historical H/BIP: {p_25_h_bip:.4f}")
    print(f"2026 Projected H/BIP:  {proj_h_bip:.4f}")
    print(f"BIP Delta:            {(proj_h_bip - p_25_h_bip) * 1000:.1f} points")
    print("-" * 90)
    print("If negative, the projection is suppressing BABIP too aggressively.")
    print("Fix: Increase k_val for 'H' in pitcher k_vals (currently 2000).")

if __name__ == "__main__":
    check_batting_integrity()
    check_pitching_integrity()
    diagnose_h_surplus()
    identify_pitching_outliers()
    deep_dive_pitching_outliers()
    diagnose_bi_vs_pa_leakage()