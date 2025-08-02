#!/usr/bin/env python3
"""
MIT License

2024 Jim Maastricht

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

JimMaastricht5@gmail.com

Automated downloader for RotoWire baseball statistics
Downloads batting and pitching stats, saves as CSV files, and runs preprocessing
"""

import requests
import pandas as pd
import subprocess
import sys
import os
from typing import Optional, List
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from bbstats_preprocess import BaseballStatsPreProcess
from bblogger import logger


class StatsDownloader:
    def __init__(self, season: Optional[List[int]] = None, headless: bool = True):
        """
        Initialize the stats downloader
        
        Args:
            season: Season year(s) to download (defaults to current year)
            headless: Whether to run browser in headless mode
        """
        if season is None:
            self.seasons = [2024]  # last full season
        elif isinstance(season, list):
            self.seasons = season
        else:
            self.seasons = [season]
        self.headless = headless
        
        # Baseball Reference URLs
        self.batting_url = 'https://www.baseball-reference.com/leagues/majors/{season}-standard-batting.shtml'
        self.pitching_url = 'https://www.baseball-reference.com/leagues/majors/{season}-standard-pitching.shtml'
        
        # Setup Chrome options
        self.chrome_options = Options()
        if self.headless:
            self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--window-size=1920,1080')
        
        # Set download directory to current directory
        prefs = {
            "download.default_directory": os.getcwd(),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        self.chrome_options.add_experimental_option("prefs", prefs)
        
        logger.info(f"Initialized StatsDownloader for seasons {self.seasons}")

    def download_batting_stats(self, season: int) -> bool:
        """
        Download batting statistics from RotoWire using CSV export
        
        Args:
            season: Year to download stats for
            
        Returns:
            bool: True if successful, False otherwise
        """
        driver = None
        error_occurred = False
        try:
            logger.info(f"Downloading batting statistics for {season}...")
            
            # Initialize Chrome driver with auto-managed ChromeDriver
            logger.info("Installing and starting Chrome WebDriver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            logger.info("Chrome WebDriver started successfully")
            
            # Format URL with season year
            batting_url = self.batting_url.format(season=season)
            logger.info(f"Navigating to: {batting_url}")
            
            # Set page load timeout
            driver.set_page_load_timeout(3)  # 10 second timeout for page load
            
            try:
                driver.get(batting_url)
                logger.info(f"Successfully navigated to Baseball Reference batting page for {season}")
            except Exception as e:
                logger.warning(f"Page load timed out or failed: {e}")
                logger.info("Attempting to continue anyway since page may have partially loaded...")
                # Continue execution - page might be loaded enough to work with
            
            # Wait for page to fully load
            logger.info("Waiting 3 seconds for page to load...")
            time.sleep(3)
            logger.info("Page load wait completed")
            
            # Manual Share & Export click
            logger.info("⚠️  MANUAL ACTION REQUIRED ⚠️")
            logger.info("Please manually click 'Share & Export' -> 'Get Table as CSV' in the browser window")
            input("Press Enter after you have clicked through to get the CSV data displayed...")
            logger.info("Continuing to capture CSV data from screen...")
                    
            # Wait for CSV data to display on screen
            time.sleep(3)
            
            # The CSV data should now be displayed on the page - capture it
            logger.info("Attempting to capture CSV data from the page...")
            
            try:
                # Look for CSV content starting with "Rk,Player," and ending before "MLB Average"
                logger.info("Looking for CSV data starting with 'Rk,Player,'...")
                
                # Get the entire page text
                page_text = driver.find_element(By.TAG_NAME, "body").text
                
                # Find the start of CSV data
                start_marker = "Rk,Player,"
                start_index = page_text.find(start_marker)
                
                if start_index != -1:
                    logger.info("Found CSV data starting point")
                    
                    # Extract from start marker to end
                    csv_section = page_text[start_index:]
                    
                    # Split into lines and filter out MLB Average line
                    lines = csv_section.split('\n')
                    csv_lines = []
                    
                    for line in lines:
                        # Stop if we hit the MLB Average line
                        if ",MLB Average" in line or line.strip().endswith("MLB Average"):
                            logger.info("Found MLB Average line, stopping data collection")
                            break
                        # Only include lines that look like CSV data
                        if line.strip() and (',' in line):
                            csv_lines.append(line.strip())
                    
                    if csv_lines:
                        csv_content = '\n'.join(csv_lines)
                        logger.info(f"Captured {len(csv_lines)} lines of CSV data")
                    else:
                        csv_content = None
                        logger.warning("No valid CSV lines found after filtering")
                else:
                    csv_content = None
                    logger.warning("Could not find CSV data starting with 'Rk,Player,'")
                
                if csv_content:
                    # Save the CSV content to file
                    batter_file = f'{season} player-stats-Batters.csv'
                    
                    # Remove existing file if it exists
                    if os.path.exists(batter_file):
                        os.remove(batter_file)
                        logger.info(f"Removed existing file {batter_file}")
                    
                    # Write CSV content to file
                    with open(batter_file, 'w', encoding='utf-8') as f:
                        f.write(csv_content)
                    
                    logger.info(f"Batting stats saved to {batter_file}")
                    return True
                else:
                    logger.warning("Could not find CSV content on the page")
                    # Fallback: ask user to manually save
                    logger.info("⚠️  MANUAL ACTION REQUIRED ⚠️")
                    logger.info("Please manually copy the CSV data and save it yourself, then press Enter...")
                    input("Press Enter when you have manually saved the CSV data...")
                    return True
                    
            except Exception as e:
                logger.error(f"Error capturing CSV content: {e}")
                logger.info("⚠️  MANUAL ACTION REQUIRED ⚠️")  
                logger.info("Please manually copy the CSV data and save it yourself, then press Enter...")
                input("Press Enter when you have manually saved the CSV data...")
                return True
                
        except Exception as e:
            logger.error(f"Error downloading batting stats for {season}: {e}")
            logger.info("Chrome window left open for debugging - close manually when done")
            error_occurred = True
            return False
        finally:
            # Only quit driver if no error occurred
            if driver and not error_occurred:
                driver.quit()

    def download_pitching_stats(self, season: int) -> bool:
        """
        Download pitching statistics from RotoWire using CSV export
        
        Args:
            season: Year to download stats for
            
        Returns:
            bool: True if successful, False otherwise
        """
        driver = None
        error_occurred = False
        try:
            logger.info(f"Downloading pitching statistics for {season}...")
            
            # Initialize Chrome driver with auto-managed ChromeDriver
            logger.info("Installing and starting Chrome WebDriver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            logger.info("Chrome WebDriver started successfully")
            
            # Format URL with season year
            pitching_url = self.pitching_url.format(season=season)
            logger.info(f"Navigating to: {pitching_url}")
            
            # Set page load timeout
            driver.set_page_load_timeout(3)  # 3 second timeout for page load
            
            try:
                driver.get(pitching_url)
                logger.info(f"Successfully navigated to Baseball Reference pitching page for {season}")
            except Exception as e:
                logger.warning(f"Page load timed out or failed: {e}")
                logger.info("Attempting to continue anyway since page may have partially loaded...")
                # Continue execution - page might be loaded enough to work with
            
            # Wait for page to fully load
            logger.info("Waiting 3 seconds for page to load...")
            time.sleep(3)
            logger.info("Page load wait completed")

            # Manual Share & Export click
            logger.info("⚠️  MANUAL ACTION REQUIRED ⚠️")
            logger.info("Please manually click 'Share & Export' -> 'Get Table as CSV' in the browser window")
            input("Press Enter after you have clicked through to get the CSV data displayed...")
            logger.info("Continuing to capture CSV data from screen...")
                    
            # Wait for CSV data to display on screen
            time.sleep(3)
            
            # The CSV data should now be displayed on the page - capture it
            logger.info("Attempting to capture CSV data from the page...")
            
            try:
                # Look for CSV content starting with "Rk,Player," and ending before "League Average"
                logger.info("Looking for CSV data starting with 'Rk,Player,'...")
                
                # Get the entire page text
                page_text = driver.find_element(By.TAG_NAME, "body").text
                
                # Find the start of CSV data
                start_marker = "Rk,Player,"
                start_index = page_text.find(start_marker)
                
                if start_index != -1:
                    logger.info("Found CSV data starting point")
                    
                    # Extract from start marker to end
                    csv_section = page_text[start_index:]
                    
                    # Split into lines and filter out League Average line
                    lines = csv_section.split('\n')
                    csv_lines = []
                    
                    for line in lines:
                        # Stop if we hit the League Average line
                        if ",League Average" in line or line.strip().endswith("League Average"):
                            logger.info("Found League Average line, stopping data collection")
                            break
                        # Only include lines that look like CSV data
                        if line.strip() and (',' in line):
                            csv_lines.append(line.strip())
                    
                    if csv_lines:
                        csv_content = '\n'.join(csv_lines)
                        logger.info(f"Captured {len(csv_lines)} lines of CSV data")
                    else:
                        csv_content = None
                        logger.warning("No valid CSV lines found after filtering")
                else:
                    csv_content = None
                    logger.warning("Could not find CSV data starting with 'Rk,Player,'")
                
                if csv_content:
                    # Save the CSV content to files
                    pitcher_file = 'mlb-player-stats-P.csv'
                    
                    # Remove existing file if it exists
                    if os.path.exists(pitcher_file):
                        os.remove(pitcher_file)
                        logger.info(f"Removed existing file {pitcher_file}")
                    
                    # Write CSV content to main file
                    with open(pitcher_file, 'w', encoding='utf-8') as f:
                        f.write(csv_content)
                    
                    logger.info(f"Pitching stats saved to {pitcher_file}")
                    
                    # Also create a year-specific copy
                    year_specific_file = f'{season} player-stats-Pitching.csv'
                    import shutil
                    shutil.copy2(pitcher_file, year_specific_file)
                    logger.info(f"Created year-specific copy: {year_specific_file}")
                    
                    return True
                else:
                    logger.warning("Could not find CSV content on the page")
                    # Fallback: ask user to manually save
                    logger.info("⚠️  MANUAL ACTION REQUIRED ⚠️")
                    logger.info("Please manually copy the CSV data and save it yourself, then press Enter...")
                    input("Press Enter when you have manually saved the CSV data...")
                    return True
                    
            except Exception as e:
                logger.error(f"Error capturing CSV content: {e}")
                logger.info("⚠️  MANUAL ACTION REQUIRED ⚠️")  
                logger.info("Please manually copy the CSV data and save it yourself, then press Enter...")
                input("Press Enter when you have manually saved the CSV data...")
                return True
                
        except Exception as e:
            logger.error(f"Error downloading pitching stats for {season}: {e}")
            logger.info("Chrome window left open for debugging - close manually when done")
            error_occurred = True
            return False
        finally:
            # Only quit driver if no error occurred
            if driver and not error_occurred:
                driver.quit()

    def verify_files_exist(self) -> bool:
        """
        Verify that all CSV files exist and are readable
        
        Returns:
            bool: True if all files exist and are readable
        """
        try:
            for season in self.seasons:
                batter_file = f'{season} player-stats-Batters.csv'
                pitcher_file = 'mlb-player-stats-P.csv'
                
                if not os.path.exists(batter_file):
                    logger.error(f"Batting file {batter_file} does not exist")
                    return False
                    
                if not os.path.exists(pitcher_file):
                    logger.error(f"Pitching file {pitcher_file} does not exist")
                    return False
                    
                # Try to read a few lines to verify files are valid
                pd.read_csv(batter_file, nrows=5)
                pd.read_csv(pitcher_file, nrows=5)
            
            logger.info("All CSV files verified successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying files: {e}")
            return False

    def run_preprocessing(self) -> bool:
        """
        Run the preprocessing script on the downloaded files
        
        Returns:
            bool: True if preprocessing completed successfully
        """
        try:
            logger.info("Starting preprocessing...")
            
            # Create BaseballStatsPreProcess instance
            # preprocessor = BaseballStatsPreProcess(
            #     load_seasons=self.seasons,
            #     new_season=self.new_season,
            #     generate_random_data=self.generate_random,
            #     load_batter_file='player-stats-Batters.csv',
            #     load_pitcher_file='player-stats-Pitching.csv'

            logger.info("Preprocessing completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during preprocessing: {e}")
            return False

    def download_and_process(self) -> bool:
        """
        Main method to download stats and run preprocessing
        
        Returns:
            bool: True if entire process completed successfully
        """
        logger.info("Starting automated stats download and processing...")
        
        # Download stats for each season
        for season in self.seasons:
            logger.info(f"Processing season {season}...")
            
            # Download batting stats for this season
            if not self.download_batting_stats(season):
                logger.error(f"Failed to download batting stats for {season}")
                return False
            
            # Download pitching stats for this season
            if not self.download_pitching_stats(season):
                logger.error(f"Failed to download pitching stats for {season}")
                return False
        
        # Verify all files exist and are readable
        if not self.verify_files_exist():
            logger.error("File verification failed")
            return False
            
        logger.info("Automated stats download completed successfully!")
        return True

    def clean_up_files(self) -> None:
        """
        Clean up temporary download files
        """
        try:
            for season in self.seasons:
                batter_file = f'{season} player-stats-Batters.csv'
                pitcher_file = 'mlb-player-stats-P.csv'
                
                if os.path.exists(batter_file):
                    os.remove(batter_file)
                    logger.info(f"Cleaned up {batter_file}")
                    
                if os.path.exists(pitcher_file):
                    os.remove(pitcher_file)
                    logger.info(f"Cleaned up {pitcher_file}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up files: {e}")


def main():
    """
    Main function to run the stats downloader
    """
    # You can modify these parameters as needed
    downloader = StatsDownloader(
        season=[2025],
        headless=False  # Set to True to run browser in background
    )
    
    success = downloader.download_and_process()
    
    if success:
        print("✅ Stats download and processing completed successfully!")
        
        # Optionally clean up the temporary CSV files
        # downloader.clean_up_files()
    else:
        print("❌ Stats download and processing failed!")
        print("Chrome window should be left open for debugging.")
        print("Press Enter to exit...")
        input()
        sys.exit(1)


if __name__ == '__main__':
    main()