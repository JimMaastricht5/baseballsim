
"""
--- File Context and Purpose ---
MLB player salary data loading and management.
This module loads historical salary data from CSV files and merges it with player
statistics by matching on player hashcodes. Provides utilities for handling missing
salary data by filling with league minimum values.

Key Functions:
- retrieve_salary(): Loads salary CSV, reformats player names, creates hashcodes
- fill_nan_salary(): Fills missing salary values with league minimum (default $740,000)
- compare_strings(): Debug utility for comparing strings and identifying differences

Salary Data Format:
- Input: CSV with columns [Player (Last, First), Position, Salary, ...]
- Output: DataFrame indexed by Hashcode with columns [Salary, MLS]
- Player names converted from "Last, First" to "First Last" for hashcode matching

Usage:
    df_salary = retrieve_salary('mlb-salaries-2000-24.csv', hash_function)
    df = pd.merge(df, df_salary, on='Hashcode', how='left')
    df = fill_nan_salary(df, 'Salary', value=740000)  # 2024 league minimum

Contact: JimMaastricht5@gmail.com
"""
import pandas as pd
import hashlib
import numpy as np
import re

def compare_strings(str1, str2):
  """Compares two strings and prints differences. useful for hashcode issues
  Args:
    str1: The first string.
    str2: The second string.
  """
  for i in range(min(len(str1), len(str2))):
    if str1[i] != str2[i]:
      print(f"Difference at index {i}: {str1[i]} vs. {str2[i]}")
  if len(str1) != len(str2):
    print(f"Length mismatch: {len(str1)} vs. {len(str2)}")
  return


def retrieve_salary(war_file_name, hashfunc, debug=False):
    # war files include full seasons up to and including 2023
    try:
        df = pd.read_csv(war_file_name)
    except FileNotFoundError:
        return None

    df = df.drop(['Unnamed: 4', 'Unnamed: 5', 'Unnamed: 6'], axis=1)
    df['Player'] = df['Player'].apply(lambda x: x.split(',')[1].lstrip().rstrip() + ' '
                                                + x.split(',')[0].lstrip().rstrip())
    df = df.rename(columns={'Player': 'Player_S', df.columns[2]: 'Salary'})  # col 2 is 2024 -> salary
    df['Salary'] = df['Salary'].astype(str)
    df['Salary'] = df['Salary'].apply(lambda x: x.replace('$', '').replace(',', '').replace('nan', '0'))
    df = df.dropna(subset=['Salary'])
    df['Salary'] = df['Salary'].astype(float).astype(int)

    # 1. Define the hitter universe
    hitter_positions = ['dh', '1b', '2b', '3b', 'ss', 'c', 'lf', 'rf', 'cf']
    # 2. Use np.where to assign the role (Vectorized & Fast)
    df['Role'] = np.where(df["Pos'n"].str.lower().isin(hitter_positions), 'Hitter', 'Pitcher')
    df['Hashcode'] = df.apply(
        lambda row: hashfunc(row['Player_S'], row['Role']),
        axis=1
    )
    df.drop(['Player_S'], axis=1, inplace=True)
    df = df.set_index('Hashcode')
    return df


def fill_nan_salary(df, column_name, value=740000):
    # 1. Ensure the column is numeric (converts strings like "0" to 0 and "nan" to NaN)
    df[column_name] = pd.to_numeric(df[column_name], errors='coerce')

    # 2. Fill zeros and NaNs
    # We use .fillna() for the NaNs and .replace() for the zeros
    df[column_name] = df[column_name].replace(0, np.nan).fillna(value)

    # 3. Cast back to int for clean output
    df[column_name] = df[column_name].astype(int)

    return df

def create_hash(name, role):
    # This ensures "Will Smith_Hitter" and "Will Smith_Pitcher"
    # generate two completely unique hex/integer values
    combined_string = f"{name}_{role}"
    return hashlib.md5(combined_string.encode()).hexdigest()


if __name__ == '__main__':
    war_files = ['mlb-salaries-2000-24.csv']
    for wf in war_files:
        df_sal = retrieve_salary(wf, create_hash)
        print(df_sal.to_string())
        print(df_sal.shape)

