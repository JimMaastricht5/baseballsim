import pandas as pd
import numpy as np

# Load files
df_proj = pd.read_csv('2023 2024 2025 aggr-stats-pp-Batting.csv')
df_hist = pd.read_csv('2023 2024 2025 historical-Batting.csv')


# Helper to find column names that might vary
def get_col(df, options):
    for opt in options:
        if opt in df.columns:
            return opt
    return None


# 1. League Integrity Check
lg_ba = df_proj['H'].sum() / df_proj['AB'].sum()
lg_obp = (df_proj['H'] + df_proj['BB'] + df_proj['HBP']).sum() / df_proj['PA'].sum()
lg_spread = lg_obp - lg_ba

print("=" * 60)
print(f"PREDICTED 2026 LEAGUE QUALITY")
print("=" * 60)
print(f"League BA:     {lg_ba:.3f}")
print(f"League OBP:    {lg_obp:.3f} (Target: ~.315)")
print(f"League Spread: {lg_spread:.3f} (Target: ~.070)")
print("=" * 60)

# 2. Specific Player Spotlight: Caleb Durbin
durbin_proj = df_proj[df_proj['Player'].str.contains('Caleb Durbin', na=False)]
durbin_hist = df_hist[(df_hist['Player'].str.contains('Caleb Durbin', na=False)) & (df_hist['Season'] == 2025)]

print("\n--- CALEB DURBIN VALIDATION ---")
if not durbin_proj.empty and not durbin_hist.empty:
    # Resolve column names for historical vs projected
    h_ba = get_col(durbin_hist, ['AVG', 'BA', 'BAvg'])
    p_ba = get_col(durbin_proj, ['BA', 'AVG'])

    comparison = pd.DataFrame({
        'Metric': ['AB', 'H', 'HR', 'BA', 'OBP', 'SLG'],
        '2025 Actual': [
            durbin_hist['AB'].iloc[0], durbin_hist['H'].iloc[0], durbin_hist['HR'].iloc[0],
            durbin_hist[h_ba].iloc[0] if h_ba else 0,
            durbin_hist['OBP'].iloc[0], durbin_hist['SLG'].iloc[0]
        ],
        '2026 Proj': [
            durbin_proj['AB'].iloc[0], durbin_proj['H'].iloc[0], durbin_proj['HR'].iloc[0],
            durbin_proj[p_ba].iloc[0] if p_ba else 0,
            durbin_proj['OBP'].iloc[0], durbin_proj['SLG'].iloc[0]
        ]
    })
    print(comparison.to_string(index=False))
else:
    print("[ALERT] Caleb Durbin not found in one of the files.")

# 3. Identify "Math Breakers"
# Ensure BA and OBP columns are referenced correctly
p_ba = get_col(df_proj, ['BA', 'AVG'])
df_proj['OBP_BA_Spread'] = df_proj['OBP'] - df_proj[p_ba]
suspects = df_proj[df_proj['PA'] >= 100].sort_values('OBP_BA_Spread', ascending=False).head(10)

print("\n--- TOP 10 ELITE DISCIPLINE (OR POTENTIAL LEAKS) ---")
print(suspects[['Player', 'PA', p_ba, 'OBP', 'OBP_BA_Spread', 'BB', 'HBP']])

# 4. Check for Scientific Notation
float_errors = df_proj[df_proj['HBP'] < 0]
if not float_errors.empty:
    print(f"\n[ALERT] Found {len(float_errors)} rows with negative HBP values!")