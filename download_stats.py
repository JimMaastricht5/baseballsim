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
    def __init__(self, season: Optional[List[int]] = None, generate_random: bool = False, 
                 new_season: Optional[int] = None, headless: bool = True):
        """
        Initialize the stats downloader
        
        Args:
            season: Season year(s) to download (defaults to current year)
            generate_random: Whether to generate random data during preprocessing
            new_season: Optional new season to create from existing data
            headless: Whether to run browser in headless mode
        """
        if season is None:
            self.seasons = [2024]  # last full season
        elif isinstance(season, list):
            self.seasons = season
        else:
            self.seasons = [season]
            
        self.generate_random = generate_random
        self.new_season = new_season
        self.headless = headless
        
        # RotoWire URLs
        self.batting_url = 'https://www.rotowire.com/baseball/stats.php'
        self.pitching_url = 'https://www.rotowire.com/baseball/stats.php'  # Same page, different tabs
        
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
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            driver.get(self.batting_url)
            
            # Wait for page to load
            wait = WebDriverWait(driver, 20)
            
            # Look for batting stats table or tab
            logger.info("Waiting for batting stats to load...")
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            
            # Select the correct year
            logger.info(f"Looking for year {season} selection...")
            try:
                # Look for year selection elements after "Season" text
                year_selectors = [
                    f"//a[contains(text(), '{season}')]",
                    f"//button[contains(text(), '{season}')]",
                    f"//span[contains(text(), '{season}')]",
                    f"//div[contains(text(), '{season}')]",
                    f"//li[contains(text(), '{season}')]"
                ]
                
                year_element = None
                for selector in year_selectors:
                    try:
                        year_element = driver.find_element(By.XPATH, selector)
                        logger.info(f"Found year {season} using selector: {selector}")
                        break
                    except:
                        continue
                
                if year_element:
                    logger.info(f"Clicking on year {season}")
                    year_element.click()
                    logger.info(f"Year {season} clicked successfully")
                    
                    # Add immediate check after click
                    logger.info("Checking page state after year click...")
                    time.sleep(1)
                    logger.info("1 second passed after year click")
                    time.sleep(1)
                    logger.info("2 seconds passed after year click")
                    
                else:
                    logger.warning(f"Could not find year {season} selection")
            except Exception as e:
                logger.warning(f"Error selecting year {season}: {e}")
            
            # Wait for page to fully load after year selection
            logger.info("Waiting for page to reload after year selection...")
            time.sleep(3)
            logger.info("3 second wait completed")
            
            # Wait for page to fully load
            time.sleep(2)
            
            # Look for "Export Table Data" text and CSV button
            logger.info("Looking for Export Table Data section...")
            
            # Try different possible selectors for the CSV button
            csv_selectors = [
                "//a[contains(text(), 'CSV')]",
                "//button[contains(text(), 'CSV')]",
                "//input[@value='CSV']",
                "//a[contains(@href, 'csv')]"
            ]
            
            csv_button = None
            for selector in csv_selectors:
                try:
                    csv_button = driver.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if csv_button:
                logger.info("Found CSV export button, clicking...")
                csv_button.click()
                
                # Wait for download to complete
                time.sleep(5)
                
                # Check if file was downloaded and rename it
                batter_file = f'{season} player-stats-Batters.csv'
                downloaded_files = [f for f in os.listdir('.') if f.endswith('.csv') and 'batting' in f.lower()]
                if not downloaded_files:
                    downloaded_files = [f for f in os.listdir('.') if f.endswith('.csv') and os.path.getmtime(f) > time.time() - 60]
                
                if downloaded_files:
                    # Rename the most recent CSV file
                    latest_file = max(downloaded_files, key=os.path.getmtime)
                    os.rename(latest_file, batter_file)
                    logger.info(f"Batting stats saved to {batter_file}")
                    return True
                else:
                    logger.error("No CSV file was downloaded")
                    logger.info("Chrome window left open for debugging - close manually when done")
                    error_occurred = True
                    return False
            else:
                logger.error("Could not find CSV export button")
                logger.info("Chrome window left open for debugging - close manually when done")
                error_occurred = True
                return False
                
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
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            driver.get(self.pitching_url)
            
            # Wait for page to load
            wait = WebDriverWait(driver, 20)
            
            # Look for pitching stats tab or button
            logger.info("Looking for pitching stats tab...")
            
            # Try to find pitching tab/button
            pitching_selectors = [
                "//a[contains(text(), 'Pitching')]",
                "//button[contains(text(), 'Pitching')]",
                "//span[contains(text(), 'Pitching')]",
                "//div[contains(text(), 'Pitching')]",
                "//li[contains(text(), 'Pitching')]"
            ]
            
            pitching_tab = None
            for selector in pitching_selectors:
                try:
                    pitching_tab = driver.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if pitching_tab:
                logger.info("Found pitching tab, clicking...")
                pitching_tab.click()
                time.sleep(3)  # Wait for tab to load
            else:
                logger.warning("No pitching tab found, assuming pitching stats are already visible")
            
            # Wait for table to load
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

            # Select the correct year
            logger.info(f"Looking for year {season} selection...")
            try:
                # Look for year selection elements after "Season" text
                year_selectors = [
                    f"//a[contains(text(), '{season}')]",
                    f"//button[contains(text(), '{season}')]",
                    f"//span[contains(text(), '{season}')]",
                    f"//div[contains(text(), '{season}')]",
                    f"//li[contains(text(), '{season}')]"
                ]
                
                year_element = None
                for selector in year_selectors:
                    try:
                        year_element = driver.find_element(By.XPATH, selector)
                        logger.info(f"Found year {season} using selector: {selector}")
                        break
                    except:
                        continue
                
                if year_element:
                    logger.info(f"Clicking on year {season}")
                    year_element.click()
                    logger.info(f"Year {season} clicked successfully")
                    
                    # Add immediate check after click
                    logger.info("Checking page state after year click...")
                    time.sleep(1)
                    logger.info("1 second passed after year click")
                    time.sleep(1)
                    logger.info("2 seconds passed after year click")
                    
                else:
                    logger.warning(f"Could not find year {season} selection")
            except Exception as e:
                logger.warning(f"Error selecting year {season}: {e}")

            # Wait for page to fully load after year selection
            logger.info("Waiting for page to reload after year selection...")
            time.sleep(3)
            logger.info("3 second wait completed")

            # Skip waiting for table since it's already present and just continue
            logger.info("Skipping table wait since table is already present")
            
            # Look for pitching tab/button and click it
            logger.info("Looking for pitching stats tab...")
            
            # Try to find pitching tab/button
            pitching_selectors = [
                "//a[contains(text(), 'Pitching')]",
                "//button[contains(text(), 'Pitching')]",
                "//span[contains(text(), 'Pitching')]",
                "//div[contains(text(), 'Pitching')]",
                "//li[contains(text(), 'Pitching')]"
            ]
            
            pitching_tab = None
            for selector in pitching_selectors:
                try:
                    pitching_tab = driver.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if pitching_tab:
                logger.info("Found pitching tab, clicking...")
                pitching_tab.click()
                logger.info("Pitching tab clicked, waiting for pitching stats to load...")
                time.sleep(5)  # Wait longer for pitching tab to load
                logger.info("Pitching tab load wait completed")
            else:
                logger.warning("No pitching tab found, assuming pitching stats are already visible")

            # Brief wait to ensure page is stable
            time.sleep(2)
            logger.info("Brief stability wait completed")

            # Look for CSV button specifically on pitching page
            logger.info("Looking for CSV button on pitching page...")
            
            # Try different possible selectors for the CSV button specifically
            csv_selectors = [
                "//a[contains(text(), 'CSV')]",
                "//button[contains(text(), 'CSV')]",
                "//input[@value='CSV']",
                "//a[contains(@href, 'csv')]",
                "//span[contains(text(), 'CSV')]",
                "//div[contains(text(), 'CSV')]",
                "//a[text()='CSV']",
                "//button[text()='CSV']"
            ]
            
            csv_button = None
            for selector in csv_selectors:
                try:
                    csv_button = driver.find_element(By.XPATH, selector)
                    logger.info(f"Found CSV button using selector: {selector}")
                    break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # If we still can't find the CSV button, try waiting a bit more
            if not csv_button:
                logger.info("CSV button not found, waiting longer and trying again...")
                time.sleep(2)
                for selector in csv_selectors:
                    try:
                        csv_button = driver.find_element(By.XPATH, selector)
                        logger.info(f"Found CSV button on retry using selector: {selector}")
                        break
                    except:
                        continue
            
            if csv_button:
                logger.info(f"Found CSV export button: {csv_button.tag_name}, text: '{csv_button.text}', href: '{csv_button.get_attribute('href')}'")
                
                # Scroll to the element first
                driver.execute_script("arguments[0].scrollIntoView(true);", csv_button)
                time.sleep(1)
                
                # Try multiple click methods for better reliability
                try:
                    # Method 1: Regular click
                    csv_button.click()
                    logger.info("Regular click successful")
                except Exception as e:
                    logger.warning(f"Regular click failed: {e}")
                    try:
                        # Method 2: JavaScript click
                        driver.execute_script("arguments[0].click();", csv_button)
                        logger.info("JavaScript click successful")
                    except Exception as e2:
                        logger.warning(f"JavaScript click failed: {e2}")
                        try:
                            # Method 3: Action chains click
                            ActionChains(driver).move_to_element(csv_button).click().perform()
                            logger.info("Action chains click successful")
                        except Exception as e3:
                            logger.error(f"All click methods failed: {e3}")
                            logger.info("Chrome window left open for debugging - close manually when done")
                            error_occurred = True
                            return False
                
                # Wait for download to complete
                logger.info("Waiting for download to complete...")
                time.sleep(3)
                
                # Check if file was downloaded and rename it
                pitcher_file = f'{season} player-stats-Pitching.csv'
                downloaded_files = [f for f in os.listdir('.') if f.endswith('.csv') and 'pitching' in f.lower()]
                if not downloaded_files:
                    downloaded_files = [f for f in os.listdir('.') if f.endswith('.csv') and os.path.getmtime(f) > time.time() - 60]
                
                if downloaded_files:
                    # Rename the most recent CSV file
                    latest_file = max(downloaded_files, key=os.path.getmtime)
                    os.rename(latest_file, pitcher_file)
                    logger.info(f"Pitching stats saved to {pitcher_file}")
                    return True
                else:
                    logger.error("No CSV file was downloaded")
                    logger.info("Chrome window left open for debugging - close manually when done")
                    error_occurred = True
                    return False
            else:
                logger.error("Could not find CSV export button")
                logger.info("Chrome window left open for debugging - close manually when done")
                error_occurred = True
                return False
                
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
                pitcher_file = f'{season} player-stats-Pitching.csv'
                
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
            preprocessor = BaseballStatsPreProcess(
                load_seasons=self.seasons,
                new_season=self.new_season,
                generate_random_data=self.generate_random,
                load_batter_file='player-stats-Batters.csv',
                load_pitcher_file='player-stats-Pitching.csv'
            )
            
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
            
        # Run preprocessing
        if not self.run_preprocessing():
            logger.error("Preprocessing failed")
            return False
            
        logger.info("Automated stats download and processing completed successfully!")
        return True

    def clean_up_files(self) -> None:
        """
        Clean up temporary download files
        """
        try:
            for season in self.seasons:
                batter_file = f'{season} player-stats-Batters.csv'
                pitcher_file = f'{season} player-stats-Pitching.csv'
                
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
        season=[2023],
        generate_random=False,  # Set to False for real data
        new_season=2026,
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