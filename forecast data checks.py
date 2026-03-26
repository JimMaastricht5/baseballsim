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
    df_23_25 = df_hist[df_hist['Season'].isin([2023, 2024, 2025])].copy()

    # Calculate Rates for each baseline
    df_proj['BA'] = df_proj['H'] / df_proj['AB'].replace(0, 1)
    df_proj['BB_Rate'] = df_proj['BB'] / df_proj['PA'].replace(0, 1)
    df_proj['SO_Rate'] = df_proj['SO'] / df_proj['PA'].replace(0, 1)
    df_proj['OBP'] = (df_proj['H'] + df_proj['BB'] + df_proj.get('HBP', 0)) / df_proj['PA'].replace(0, 1)

    # 2023-2025 Historical (blend baseline)
    lg_ba_23_25 = df_23_25['H'].sum() / df_23_25['AB'].sum()
    lg_obp_23_25 = (df_23_25['H'] + df_23_25['BB']).sum() / df_23_25['PA'].sum()
    lg_bb_23_25 = df_23_25['BB'].sum() / df_23_25['PA'].sum()
    lg_so_23_25 = df_23_25['SO'].sum() / df_23_25['PA'].sum()
    
    # 2025 Historical
    lg_ba_25 = df_25['H'].sum() / df_25['AB'].sum()
    lg_obp_25 = (df_25['H'] + df_25['BB']).sum() / df_25['PA'].sum()
    lg_bb_25 = df_25['BB'].sum() / df_25['PA'].sum()
    lg_so_25 = df_25['SO'].sum() / df_25['PA'].sum()

    # 2026 Projected
    lg_ba = df_proj['H'].sum() / df_proj['AB'].sum()
    lg_obp = (df_proj['H'] + df_proj['BB']).sum() / df_proj['PA'].sum()
    lg_bb = df_proj['BB'].sum() / df_proj['PA'].sum()
    lg_so = df_proj['SO'].sum() / df_proj['PA'].sum()

    print("=" * 90)
    print(f"{'HITTER INTEGRITY CHECK: PROJECTION vs HISTORICAL BASELINES':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(f"League AVG:                 {lg_ba_23_25:.3f}         {lg_ba_25:.3f}       {lg_ba:.3f}")
    print(f"League OBP:                 {lg_obp_23_25:.3f}         {lg_obp_25:.3f}       {lg_obp:.3f}")
    print(f"BB Rate (BB/PA):            {lg_bb_23_25:.3f}         {lg_bb_25:.3f}       {lg_bb:.3f}")
    print(f"SO Rate (SO/PA):            {lg_so_23_25:.3f}         {lg_so_25:.3f}       {lg_so:.3f}")
    print(f"OBP Spread (OBP - AVG):    {lg_obp_23_25 - lg_ba_23_25:.3f}         {lg_obp_25 - lg_ba_25:.3f}       {lg_obp - lg_ba:.3f}")
    print("-" * 90)
    
    # Delta checks
    proj_vs_blend_obp = lg_obp - lg_obp_23_25
    proj_vs_25_obp = lg_obp - lg_obp_25
    proj_vs_blend_bb = lg_bb - lg_bb_23_25
    proj_vs_25_bb = lg_bb - lg_bb_25
    proj_vs_blend_so = lg_so - lg_so_23_25
    proj_vs_25_so = lg_so - lg_so_25
    
    print(f"2026 Proj vs 2023-2025 Blend: OBP {proj_vs_blend_obp:+.3f} | BB {proj_vs_blend_bb:+.3f} | SO {proj_vs_blend_so:+.3f}")
    print(f"2026 Proj vs 2025 Only:       OBP {proj_vs_25_obp:+.3f} | BB {proj_vs_25_bb:+.3f} | SO {proj_vs_25_so:+.3f}")
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
    df_23_25 = df_hist[df_hist['Season'].isin([2023, 2024, 2025])].copy()

    # We care about Hits and Walks allowed (The OBP drivers)
    df_proj['H_PA'] = df_proj['H'] / df_proj['PA'].replace(0, 1)
    df_proj['BB_PA'] = df_proj['BB'] / df_proj['PA'].replace(0, 1)
    df_proj['SO_PA'] = df_proj['SO'] / df_proj['PA'].replace(0, 1)
    df_proj['OBP_Against'] = (df_proj['H'] + df_proj['BB']) / df_proj['PA'].replace(0, 1)

    # 2023-2025 Baseline
    lg_h_pa_23_25 = df_23_25['H'].sum() / df_23_25['PA'].sum()
    lg_bb_pa_23_25 = df_23_25['BB'].sum() / df_23_25['PA'].sum()
    lg_so_pa_23_25 = df_23_25['SO'].sum() / df_23_25['PA'].sum()
    lg_obpa_23_25 = lg_h_pa_23_25 + lg_bb_pa_23_25
    
    # 2025 Baseline
    lg_h_pa_25 = df_25['H'].sum() / df_25['PA'].sum()
    lg_bb_pa_25 = df_25['BB'].sum() / df_25['PA'].sum()
    lg_so_pa_25 = df_25['SO'].sum() / df_25['PA'].sum()
    lg_obpa_25 = lg_h_pa_25 + lg_bb_pa_25

    # 2026 Projected
    lg_h_pa = df_proj['H'].sum() / df_proj['PA'].sum()
    lg_bb_pa = df_proj['BB'].sum() / df_proj['PA'].sum()
    lg_so_pa = df_proj['SO'].sum() / df_proj['PA'].sum()
    lg_obpa = lg_h_pa + lg_bb_pa

    print("\n" + "=" * 90)
    print(f"{'PITCHER INTEGRITY CHECK: PROJECTION vs HISTORICAL BASELINES':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(f"League Hits/PA:            {lg_h_pa_23_25:.3f}         {lg_h_pa_25:.3f}       {lg_h_pa:.3f}")
    print(f"League Walks/PA:            {lg_bb_pa_23_25:.3f}         {lg_bb_pa_25:.3f}       {lg_bb_pa:.3f}")
    print(f"League K/PA:               {lg_so_pa_23_25:.3f}         {lg_so_pa_25:.3f}       {lg_so_pa:.3f}")
    print(f"OBP Against:               {lg_obpa_23_25:.3f}         {lg_obpa_25:.3f}       {lg_obpa:.3f}")
    print("-" * 90)
    
    # Delta checks
    proj_vs_blend_obpa = lg_obpa - lg_obpa_23_25
    proj_vs_25_obpa = lg_obpa - lg_obpa_25
    proj_vs_blend_h = lg_h_pa - lg_h_pa_23_25
    proj_vs_25_h = lg_h_pa - lg_h_pa_25
    proj_vs_blend_so = lg_so_pa - lg_so_pa_23_25
    proj_vs_25_so = lg_so_pa - lg_so_pa_25
    
    print(f"2026 Proj vs 2023-2025 Blend: OBP {proj_vs_blend_obpa:+.3f} | H {proj_vs_blend_h:+.3f} | K {proj_vs_blend_so:+.3f}")
    print(f"2026 Proj vs 2025 Only:       OBP {proj_vs_25_obpa:+.3f} | H {proj_vs_25_h:+.3f} | K {proj_vs_25_so:+.3f}")
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

    # Filter for baselines
    b_25 = df_b_hist[df_b_hist['Season'] == 2025]
    b_23_25 = df_b_hist[df_b_hist['Season'].isin([2023, 2024, 2025])]
    p_25 = df_p_hist[df_p_hist['Season'] == 2025]
    p_23_25 = df_p_hist[df_p_hist['Season'].isin([2023, 2024, 2025])]

    # Calculate Aggregate H/PA for each baseline
    b_25_h_rate = b_25['H'].sum() / b_25['PA'].sum()
    b_23_25_h_rate = b_23_25['H'].sum() / b_23_25['PA'].sum()
    b_26_h_rate = df_b_proj['H'].sum() / df_b_proj['PA'].sum()

    p_25_h_rate = p_25['H'].sum() / p_25['PA'].sum()
    p_23_25_h_rate = p_23_25['H'].sum() / p_23_25['PA'].sum()
    p_26_h_rate = df_p_proj['H'].sum() / df_p_proj['PA'].sum()

    print("\n" + "=" * 90)
    print(f"{'HIT INFLATION DIAGNOSTIC: PROJECTION vs BASELINES':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(f"Hitters (H/PA):            {b_23_25_h_rate:.4f}       {b_25_h_rate:.4f}     {b_26_h_rate:.4f}")
    print(f"Pitchers (H_Allowed/PA):   {p_23_25_h_rate:.4f}       {p_25_h_rate:.4f}     {p_26_h_rate:.4f}")
    print("-" * 90)
    
    # Delta checks
    h_vs_blend = (b_26_h_rate - b_23_25_h_rate) * 1000
    h_vs_25 = (b_26_h_rate - b_25_h_rate) * 1000
    p_vs_blend = (p_26_h_rate - p_23_25_h_rate) * 1000
    p_vs_25 = (p_26_h_rate - p_25_h_rate) * 1000
    
    print(f"2026 Proj vs 2023-2025 Blend: Hitters {h_vs_blend:+.1f} pts | Pitchers {p_vs_blend:+.1f} pts")
    print(f"2026 Proj vs 2025 Only:       Hitters {h_vs_25:+.1f} pts | Pitchers {p_vs_25:+.1f} pts")
    print("-" * 90)


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

    # Pitcher BIP analysis
    p_25 = df_p_hist[df_p_hist['Season'] == 2025].copy()
    p_23_25 = df_p_hist[df_p_hist['Season'].isin([2023, 2024, 2025])].copy()

    # Historical: calculate actual BIP for 2025
    p_25['BIP'] = p_25['PA'] - p_25['SO'] - p_25['BB']
    p_25_h_bip = p_25['H'].sum() / p_25['BIP'].sum()  # Historical H/BIP

    # Historical: calculate actual BIP for 2023-2025
    p_23_25['BIP'] = p_23_25['PA'] - p_23_25['SO'] - p_23_25['BB']
    p_23_25_h_bip = p_23_25['H'].sum() / p_23_25['BIP'].sum()

    # Projected: calculate what the projection assumes
    df_p_proj['BIP'] = df_p_proj['PA'] - df_p_proj['SO'] - df_p_proj['BB']
    proj_h_bip = df_p_proj['H'].sum() / df_p_proj['BIP'].sum()  # Proj H/BIP

    print("\n" + "=" * 90)
    print(f"{'BIP LEAKAGE DIAGNOSTIC (BABIP Comparison)':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(f"Historical H/BIP:          {p_23_25_h_bip:.4f}         {p_25_h_bip:.4f}       {proj_h_bip:.4f}")
    print("-" * 90)
    
    # Delta checks
    bip_vs_blend = (proj_h_bip - p_23_25_h_bip) * 1000
    bip_vs_25 = (proj_h_bip - p_25_h_bip) * 1000
    print(f"2026 Proj vs 2023-2025 Blend: {bip_vs_blend:+.1f} points")
    print(f"2026 Proj vs 2025 Only:       {bip_vs_25:+.1f} points")
    print("-" * 90)

if __name__ == "__main__":
    check_batting_integrity()
    check_pitching_integrity()
    diagnose_h_surplus()
    identify_pitching_outliers()
    deep_dive_pitching_outliers()
    diagnose_bi_vs_pa_leakage()