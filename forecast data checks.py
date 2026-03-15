import pandas as pd
import numpy as np

# Load files
df_proj = pd.read_csv('2023 2024 2025 aggr-stats-pp-Batting.csv')
df_hist = pd.read_csv('2023 2024 2025 historical-Batting.csv')

# Ensure 2025 is isolated for comparison
df_25 = df_hist[df_hist['Season'] == 2025].copy()

# Pre-calculate Projection Rates
df_proj['BA'] = df_proj['H'] / df_proj['AB']
df_proj['OBP'] = (df_proj['H'] + df_proj['BB'] + df_proj['HBP']) / df_proj['PA']
df_proj['SLG'] = (df_proj['H'] + df_proj['2B'] + 2 * df_proj['3B'] + 3 * df_proj['HR']) / df_proj['AB']
df_proj['Spread'] = df_proj['OBP'] - df_proj['BA']

# 1. Global League Integrity
print("=" * 80)
print(f"{'PREDICTED 2026 LEAGUE slash Line':^80}")
print("=" * 80)
lg_ba = df_proj['H'].sum() / df_proj['AB'].sum()
lg_obp = (df_proj['H'] + df_proj['BB'] + df_proj['HBP']).sum() / df_proj['PA'].sum()
lg_slg = (df_proj['H'] + df_proj['2B'] + 2 * df_proj['3B'] + 3 * df_proj['HR']).sum() / df_proj['AB'].sum()

print(f"League AVG: {lg_ba:.3f} | League OBP: {lg_obp:.3f} | League SLG: {lg_slg:.3f}")
print(f"OBP Spread: {lg_obp - lg_ba:.3f} (Target: ~.070)")
print("-" * 80)


# 2. Side-by-Side Spotlight Function
def player_diagnosis(name):
    # Filter to find the player
    p_hist_matches = df_25[df_25['Player'].str.contains(name, na=False)]
    p_proj_matches = df_proj[df_proj['Player'].str.contains(name, na=False)]

    if p_hist_matches.empty or p_proj_matches.empty:
        print(f"\n--- DIAGNOSIS: {name} (NOT FOUND) ---")
        return

    p_hist = p_hist_matches.iloc[0]
    p_proj = p_proj_matches.iloc[0]

    # ADD HASHCODE TO OUTPUT
    hist_hash = p_hist.get('Hashcode', 'MISSING')
    proj_hash = p_proj.get('Hashcode', 'MISSING')

    print(f"\n--- DIAGNOSIS: {name} ---")
    print(f"2025 Hash: {hist_hash}")
    print(f"2026 Hash: {proj_hash}")
    if hist_hash != proj_hash:
        print("!!! WARNING: Hashcode mismatch between history and projection !!!")

    stats = ['PA', 'AB', 'H', '2B', 'HR', 'BB', 'SO', 'BA', 'OBP', 'SLG']

    # Build comparison frame
    comp = pd.DataFrame({
        '2025 Act': [p_hist.get(s, 0) for s in stats],
        '2026 Proj': [p_proj.get(s, 0) for s in stats]
    }, index=stats)

    comp['2025 Act'] = pd.to_numeric(comp['2025 Act'], errors='coerce')
    comp['2026 Proj'] = pd.to_numeric(comp['2026 Proj'], errors='coerce')
    comp['Delta'] = comp['2026 Proj'] - comp['2025 Act']

    print(comp.round(3).to_string())


# Run spotlight for your key test cases
player_diagnosis('Will Smith')  # Check the mashup specifically
player_diagnosis('Caleb Durbin')
player_diagnosis('Cal Raleigh')
player_diagnosis('Eric Haase')

# 3. Leak Detector (The "Will Smith" Check)
print("\n" + "=" * 80)
print(f"{'OBP & SPREAD OUTLIERS (POTENTIAL MATH LEAKS)':^80}")
print("=" * 80)
# Flag anyone with OBP > .550 or Spread > .150
leaks = df_proj[(df_proj['OBP'] > 0.550) | (df_proj['Spread'] > 0.150)].sort_values('Spread', ascending=False)
if not leaks.empty:
    # Included Hashcode here to see if outliers share a hash
    print(leaks[['Player', 'Hashcode', 'PA', 'BA', 'OBP', 'Spread', 'BB']].head(15).to_string(index=False))
else:
    print("No OBP leaks detected.")

# 4. Top Hits / Top Drops (The "Regression" Check)
print("\n" + "=" * 80)
print(f"{'BIGGEST REGRESSION HITS (AVG)':^80}")
print("=" * 80)

# Merge on Hashcode instead of Name to ensure clean tracking
merged = pd.merge(df_25, df_proj, on='Hashcode', suffixes=('_25', '_26'))

# If names don't match after hashing merge, we have a name-string issue
merged['Name_Match'] = merged['Player_25'] == merged['Player_26']

merged['BA_25'] = merged['H_25'] / merged['AB_25'].replace(0, 1)
merged['BA_26'] = merged['H_26'] / merged['AB_26'].replace(0, 1)
merged['BA_Delta'] = merged['BA_26'] - merged['BA_25']

print("\nTop 5 Gainers in AVG (Check for Hash Collisions):")
print(merged.sort_values('BA_Delta', ascending=False)[['Player_26', 'Hashcode', 'BA_25', 'BA_26', 'BA_Delta']].head(
    5).to_string(index=False))

print("\nTop 10 RAW MATH (Check for high BA outliers):")
cols = ['Player_26', 'Hashcode', 'PA_26', 'H_26', 'AB_26', 'BA_26']
print(merged.sort_values('BA_26', ascending=False)[cols].head(10).to_string(index=False))

import pandas as pd
import numpy as np

# 1. LOAD PITCHING FILES
# Assuming your naming convention remains consistent
df_proj = pd.read_csv('2023 2024 2025 aggr-stats-pp-Pitching.csv')
df_hist = pd.read_csv('2023 2024 2025 historical-Pitching.csv')

# Isolate 2025 for comparison
df_25 = df_hist[df_hist['Season'] == 2025].copy()

# Pre-calculate Projection Rates (Pitching Standard)
df_proj['ERA'] = (df_proj['ER'] * 9) / df_proj['IP']
df_proj['WHIP'] = (df_proj['H'] + df_proj['BB']) / df_proj['IP']
df_proj['K9'] = (df_proj['SO'] * 9) / df_proj['IP']
df_proj['BB9'] = (df_proj['BB'] * 9) / df_proj['IP']
df_proj['K_BB'] = df_proj['SO'] / df_proj['BB'].replace(0, 1)  # Avoid div by zero

# 2. GLOBAL LEAGUE INTEGRITY (PITCHING)
print("=" * 80)
print(f"{'PREDICTED 2026 LEAGUE PITCHING TOTALS':^80}")
print("=" * 80)
lg_era = (df_proj['ER'].sum() * 9) / df_proj['IP'].sum()
lg_whip = (df_proj['H'].sum() + df_proj['BB'].sum()) / df_proj['IP'].sum()
lg_k9 = (df_proj['SO'].sum() * 9) / df_proj['IP'].sum()

print(f"League ERA: {lg_era:.3f} | League WHIP: {lg_whip:.3f} | League K/9: {lg_k9:.3f}")
print(f"Target ERA range: 4.00 - 4.50 (Currently: {lg_era:.3f})")
print("-" * 80)


# 3. SIDE-BY-SIDE PITCHER DIAGNOSIS
def pitcher_diagnosis(name):
    p_hist_matches = df_25[df_25['Player'].str.contains(name, na=False, case=False)]
    p_proj_matches = df_proj[df_proj['Player'].str.contains(name, na=False, case=False)]

    if p_hist_matches.empty or p_proj_matches.empty:
        print(f"\n--- DIAGNOSIS: {name} (NOT FOUND) ---")
        return

    p_hist = p_hist_matches.iloc[0]
    p_proj = p_proj_matches.iloc[0]

    hist_hash = p_hist.get('Hashcode', 'MISSING')
    proj_hash = p_proj.get('Hashcode', 'MISSING')

    print(f"\n--- PITCHER DIAGNOSIS: {name} ---")
    print(f"2025 Hash: {hist_hash} | 2026 Hash: {proj_hash}")

    if hist_hash != proj_hash:
        print("!!! WARNING: Hashcode mismatch detected !!!")

    # Relevant Pitching Stats
    stats = ['IP', 'W', 'L', 'SV', 'H', 'ER', 'BB', 'SO', 'ERA', 'WHIP', 'K9']

    # Build comparison frame
    comp = pd.DataFrame({
        '2025 Act': [p_hist.get(s, 0) for s in stats],
        '2026 Proj': [p_proj.get(s, 0) for s in stats]
    }, index=stats)

    comp['2025 Act'] = pd.to_numeric(comp['2025 Act'], errors='coerce')
    comp['2026 Proj'] = pd.to_numeric(comp['2026 Proj'], errors='coerce')
    comp['Delta'] = comp['2026 Proj'] - comp['2025 Act']

    print(comp.round(3).to_string())


# TEST CASES: Change these to your specific "whacked" pitchers
pitcher_diagnosis('Paul Skenes')
pitcher_diagnosis('Tarik Skubal')
pitcher_diagnosis('Zack Wheeler')
pitcher_diagnosis('Josh Hader')

# 4. RATIO LEAK DETECTOR (ERA/WHIP OUTLIERS)
print("\n" + "=" * 80)
print(f"{'ERA & WHIP OUTLIERS (POTENTIAL MATH LEAKS)':^80}")
print("=" * 80)
# Flag anyone with ERA < 1.50 or WHIP < 0.80 (with significant IP)
leaks = df_proj[(df_proj['IP'] > 40) & ((df_proj['ERA'] < 1.50) | (df_proj['WHIP'] < 0.85))].sort_values('ERA')

if not leaks.empty:
    cols = ['Player', 'Hashcode', 'IP', 'ERA', 'WHIP', 'K9', 'BB9']
    print(leaks[cols].head(15).to_string(index=False))
else:
    print("No obvious pitching leaks detected for high-volume pitchers.")

# 5. REGRESSION CHECK (ERA DELTA)
print("\n" + "=" * 80)
print(f"{'BIGGEST PROJECTED REGRESSION (ERA)':^80}")
print("=" * 80)

merged = pd.merge(df_25, df_proj, on='Hashcode', suffixes=('_25', '_26'))

# Calculate ERAs for Delta (avoiding 0 IP)
merged['ERA_25'] = (merged['ER_25'] * 9) / merged['IP_25'].replace(0, 1)
merged['ERA_26'] = (merged['ER_26'] * 9) / merged['IP_26'].replace(0, 1)
merged['ERA_Delta'] = merged['ERA_26'] - merged['ERA_25']

print("\nTop 5 Improved ERA (Check for unrealistic drops):")
print(merged.sort_values('ERA_Delta', ascending=True)[['Player_26', 'Hashcode', 'ERA_25', 'ERA_26', 'ERA_Delta']].head(
    5).to_string(index=False))

print("\nTop 5 Exploding ERA (Check for hash collisions):")
print(merged.sort_values('ERA_Delta', ascending=False)[['Player_26', 'Hashcode', 'ERA_25', 'ERA_26', 'ERA_Delta']].head(
    5).to_string(index=False))