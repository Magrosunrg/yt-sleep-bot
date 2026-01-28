import os
import time
import re
import subprocess
import qbittorrentapi
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import undetected_chromedriver as uc

# Configuration for qBittorrent
QBIT_HOST = "localhost"
QBIT_PORT = 8080
QBIT_USER = "admin"
QBIT_PASS = "adminadmin"

# Configuration for Aria2
if os.name == 'nt':
    ARIA2_PATH = os.path.join(os.getcwd(), "tools", "aria2c.exe")
else:
    ARIA2_PATH = "aria2c"

from urllib.parse import quote

class TorrentManager:
    def __init__(self, download_dir=None):
        self.download_dir = download_dir if download_dir else os.path.join(os.getcwd(), "temp_torrents")
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            
        self.qbt_client = self._connect_qbittorrent()

    def _connect_qbittorrent(self):
        try:
            conn_info = dict(
                host=QBIT_HOST,
                port=QBIT_PORT,
                username=QBIT_USER,
                password=QBIT_PASS,
            )
            qbt_client = qbittorrentapi.Client(**conn_info)
            qbt_client.auth_log_in()
            print(f"✅ Connected to qBittorrent ({qbt_client.app.version})")
            return qbt_client
        except Exception as e:
            print(f"⚠️ Could not connect to qBittorrent: {e}")
            print("   (Will attempt to use Aria2 as fallback if available)")
            return None

    def search_1337x(self, query, category=None):
        """
        Searches 1337x.to for the query and returns the magnet link of the top result.
        Uses Selenium to bypass Cloudflare/JS checks.
        
        :param category: Optional category for specialized search (e.g., 'Movies', 'TV')
                         If provided, uses /category-search/{query}/{category}/1/
        """
        if category:
            print(f"🔍 Searching 1337x.to (Category: {category}) for: {query}")
        else:
            print(f"🔍 Searching 1337x.to for: {query}")
        
        magnet_link = None
        driver = None
        
        try:
            # Cleanup Profile Locks
            profile_dir = os.path.join(os.getcwd(), "selenium_profile")
            if os.path.exists(profile_dir):
                for root, dirs, files in os.walk(profile_dir):
                    for file in files:
                        if file in ('LOCK', 'SingletonLock'):
                            try:
                                os.remove(os.path.join(root, file))
                            except:
                                pass

            # Setup Undetected Chromedriver
            # This library patches the driver to be undetectable by Cloudflare
            def get_options():
                options = uc.ChromeOptions()
                # EXPLICITLY DISABLE HEADLESS
                # options.add_argument("--headless=new") 
                options.headless = False
                options.add_argument("--start-maximized")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                
                # Use persistent profile to save Cloudflare/Human Verification status
                profile_dir = os.path.join(os.getcwd(), "selenium_profile")
                if not os.path.exists(profile_dir):
                    os.makedirs(profile_dir)
                options.add_argument(f"--user-data-dir={profile_dir}")
                return options
            
            # Initialize Driver with Fallbacks
            driver = None
            
            # Attempt 1: Undetected Chromedriver (Auto)
            try:
                print("   🚀 Launching Browser (Method A: UC Auto)...")
                driver = uc.Chrome(options=get_options(), use_subprocess=True)
            except Exception as e:
                print(f"   ⚠️ Method A failed: {e}")
                
                # Attempt 2: Undetected Chromedriver (Retry without subprocess)
                try:
                    print("   🚀 Launching Browser (Method B: UC Retry)...")
                    driver = uc.Chrome(options=get_options(), use_subprocess=False)
                except Exception as e2:
                    print(f"   ⚠️ Method B failed: {e2}")
                    
                    # Attempt 3: Standard Selenium (Fallback)
                    print("   🚀 Launching Browser (Method C: Standard Selenium)...")
                    try:
                        # Re-create standard options (UC options object might be incompatible)
                        std_options = Options()
                        std_options.add_argument("--start-maximized")
                        std_options.add_argument("--window-size=1920,1080")
                        std_options.add_argument("--disable-blink-features=AutomationControlled")
                        std_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                        std_options.add_experimental_option('useAutomationExtension', False)
                        std_options.add_argument("--no-sandbox")
                        std_options.add_argument("--disable-dev-shm-usage")
                        
                        # Use same profile
                        profile_dir = os.path.join(os.getcwd(), "selenium_profile")
                        std_options.add_argument(f"user-data-dir={profile_dir}")
                        
                        service = Service(ChromeDriverManager().install())
                        driver = webdriver.Chrome(service=service, options=std_options)
                    except Exception as e3:
                        print(f"   ⚠️ Method C failed: {e3}")
                        
                        # Attempt 4: Standard Selenium with FRESH Profile (Last Resort)
                        print("   🚀 Launching Browser (Method D: Standard Selenium - FRESH PROFILE)...")
                        try:
                            std_options = Options()
                            std_options.add_argument("--start-maximized")
                            std_options.add_argument("--window-size=1920,1080")
                            std_options.add_argument("--disable-blink-features=AutomationControlled")
                            std_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                            std_options.add_experimental_option('useAutomationExtension', False)
                            std_options.add_argument("--no-sandbox")
                            std_options.add_argument("--disable-dev-shm-usage")
                            
                            # No user-data-dir (fresh profile)
                            
                            service = Service(ChromeDriverManager().install())
                            driver = webdriver.Chrome(service=service, options=std_options)
                        except Exception as e4:
                            print(f"   ❌ All browser launch methods failed.")
                            raise e4
            
            encoded_query = quote(query)
            
            # 1. Go to Search Page
            if category:
                # Category search format: https://1337x.to/category-search/{query}/{category}/1/
                search_url = f"https://1337x.to/category-search/{encoded_query}/{category}/1/"
            else:
                # Default sort search: https://1337x.to/sort-search/{query}/seeders/desc/1/
                search_url = f"https://1337x.to/sort-search/{encoded_query}/seeders/desc/1/"
            
            driver.get(search_url)
            
            # Quick check for "No results" to avoid Cloudflare wait
            # 1337x displays "No results were returned" in a visible banner
            try:
                # Give it a tiny moment to render if needed, but page_source is usually immediate after get
                if "No results were returned" in driver.page_source:
                    print("   ❌ 1337x: No results found (Page indicates empty).")
                    return None
            except:
                pass

            # Wait for results table
            try:
                # 1. Check if we need to verify manually (Visible Mode)
                print("   ⏳ Waiting for search results (Solve CAPTCHA if needed)...")
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "table-list"))
                )
                print("   ✅ Results loaded!")
            except:
                print("   ⚠️ Cloudflare/Verification detected or Timeout!")
                print("   Please check the browser window and solve the CAPTCHA.")
                try:
                    # Give user more time to solve it manually since window is visible
                    WebDriverWait(driver, 120).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "table-list"))
                    )
                    print("   ✅ Verification passed!")
                except:
                    print("   ❌ Verification failed or timed out.")
                    return None


            # 2. Get First Result Link
            results = driver.find_elements(By.CSS_SELECTOR, "td.name a[href*='/torrent/']")
            if not results:
                print("   ❌ No torrent results found.")
                return None
            
            # Check seeders for the top results to avoid dead torrents
            top_result = None
            for i, result in enumerate(results[:5]): # Check top 5
                try:
                    # Enforce Year Match if Query has Year
                    query_year_match = re.search(r'\b(19|20)\d{2}\b', query)
                    if query_year_match:
                        query_year = query_year_match.group(0)
                        result_year_match = re.search(r'\b(19|20)\d{2}\b', result.text)
                        if result_year_match:
                            if query_year != result_year_match.group(0):
                                print(f"   ⚠️ Skipping result '{result.text}' due to year mismatch (Query: {query_year} vs Result: {result_year_match.group(0)})")
                                continue

                    # Navigate up to tr to find seeds. 1337x structure: tr > td.seeds
                    # We are in td.name > a. So ancestor tr is correct.
                    row = result.find_element(By.XPATH, "./ancestor::tr")
                    seeds_element = row.find_element(By.CSS_SELECTOR, "td.seeds")
                    seeds_text = seeds_element.text.replace(',', '')
                    seeds = int(seeds_text)
                    
                    if seeds > 0:
                        top_result = result
                        print(f"   ✅ Found healthy torrent: {result.text} (Seeds: {seeds})")
                        break
                    else:
                        print(f"   ⚠️ Skipping dead torrent: {result.text} (Seeds: 0)")
                except Exception as e:
                    # If we can't parse seeds, assume it's okay and try it
                    print(f"   ⚠️ Could not parse seeds for result {i+1}: {e}")
                    top_result = result
                    break
            
            if not top_result:
                print("   ❌ No healthy torrents found (all checked have 0 seeds).")
                return None

            top_url = top_result.get_attribute("href")
            # print(f"   📄 Found Page: {top_result.text}") # Already printed above
            
            # 3. Go to Details Page
            driver.get(top_url)
            
            # 4. Extract Magnet
            magnet_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='magnet:?']"))
            )
            magnet_link = magnet_element.get_attribute("href")
            
            if magnet_link:
                print("   🧲 Magnet Link extracted successfully.")
            
        except Exception as e:
            print(f"   ❌ Error searching 1337x: {e}")
        finally:
            if driver:
                driver.quit()
                
        return magnet_link

    def download_torrent(self, magnet_link, timeout_minutes=30):
        """
        Downloads torrent using qBittorrent or Aria2 (fallback).
        """
        if not magnet_link:
            return None

        # Fallback to Aria2 if qBit is missing
        if not self.qbt_client:
            if os.path.exists(ARIA2_PATH):
                return self.download_with_aria2(magnet_link, timeout_minutes)
            else:
                print("❌ qBittorrent not connected AND Aria2 not found.")
                print("   Please start qBittorrent OR check Aria2 installation.")
                return None

        # qBittorrent Logic
        try:
            print("⬇️ Adding torrent to qBittorrent queue...")
            self.qbt_client.torrents_add(urls=magnet_link, save_path=self.download_dir)
            time.sleep(2)
            
            torrents = self.qbt_client.torrents_info(sort='added_on', reverse=True, limit=1)
            if not torrents:
                print("❌ Could not verify torrent addition.")
                return None
                
            torrent = torrents[0]
            t_hash = torrent.hash
            t_name = torrent.name
            print(f"   📦 Downloading: {t_name}")
            
            start_time = time.time()
            
            while True:
                t_info = self.qbt_client.torrents_info(torrent_hashes=t_hash)[0]
                progress = t_info.progress * 100
                state = t_info.state
                
                if progress >= 100 or state in ['uploading', 'pausedUP', 'queuedUP', 'stalledUP']:
                    print(f"\r   ✅ Download Complete: 100%                         ")
                    break
                    
                elapsed = (time.time() - start_time) / 60
                if elapsed > timeout_minutes:
                    print(f"\n   ⏱️ Timeout reached ({timeout_minutes}m). Aborting.")
                    self.qbt_client.torrents_delete(torrent_hashes=t_hash, delete_files=True)
                    return None
                
                print(f"\r   ⏳ Progress: {progress:.1f}% | Speed: {t_info.dlspeed/1024/1024:.1f} MB/s | State: {state}", end="")
                time.sleep(5)
            
            return self._find_video_file(t_name)
                
        except Exception as e:
            print(f"   ❌ qBittorrent Error: {e}")
            return None

    def download_with_aria2(self, magnet_link, timeout_minutes=30):
        print(f"⬇️ Using Aria2 fallback for download...")
        print(f"   📂 Output Dir: {self.download_dir}")
        
        # Add public trackers to boost connection speed
        trackers = [
            "udp://tracker.opentrackr.org:1337/announce",
            "udp://open.stealth.si:80/announce",
            "udp://9.rarbg.com:2810/announce",
            "udp://tracker.openbittorrent.com:80/announce",
            "udp://tracker.torrent.eu.org:451/announce",
            "udp://explodie.org:6969/announce",
            "udp://tracker.coppersurfer.tk:6969/announce",
            "http://tracker.openbittorrent.com:80/announce"
        ]
        tracker_str = ",".join(trackers)
        
        # Command: aria2c --seed-time=0 -d DIR "MAGNET"
        cmd = [
            ARIA2_PATH,
            "--seed-time=0",
            "--summary-interval=5",
            "--allow-overwrite=true",
            "--bt-tracker=" + tracker_str,
            "--bt-stop-timeout=" + str(timeout_minutes * 60),
            "-d", self.download_dir,
            magnet_link
        ]
        
        try:
            # We use subprocess.Popen to monitor output or just .run() and wait?
            # .run() shows stdout to console which is good.
            print("   🚀 Starting Aria2 process (this terminal will show progress)...")
            print("   (If it gets stuck on [METADATA] for >2 mins, press Ctrl+C to try YouTube fallback)")
            
            # Using Popen to stream output line by line might be better for UI, but simple run is safer for now.
            # Warning: This is blocking.
            process = subprocess.run(cmd, check=True)
            
            print("   ✅ Aria2 finished.")
            
            # Find the file
            # Aria2 doesn't give us the name easily, we have to search the dir for new files?
            # Or just search recursively for video files.
            return self._find_video_file(None)
            
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Aria2 failed with exit code {e.returncode}")
            return None
        except KeyboardInterrupt:
            print("\n   ⚠️ Download cancelled by user.")
            return None
        except Exception as e:
            print(f"   ❌ Aria2 Error: {e}")
            return None

    def _find_video_file(self, torrent_name_hint):
        """Helper to find the largest video file in download_dir, prioritizing the torrent name folder."""
        video_extensions = ('.mp4', '.mkv', '.avi', '.mov')
        largest_file = None
        max_size = 0
        
        search_roots = [self.download_dir]
        
        # If we have a hint, check if it exists as a folder first
        if torrent_name_hint:
             hint_path = os.path.join(self.download_dir, torrent_name_hint)
             if os.path.exists(hint_path) and os.path.isdir(hint_path):
                 print(f"   📂 Focusing search in torrent folder: {torrent_name_hint}")
                 search_roots = [hint_path] # ONLY search this folder
             else:
                 # It might be a single file torrent or name mismatch.
                 # We can filter files by name match if we are in the root dir
                 pass
        
        candidates = []

        # Walk through the search roots
        for search_root in search_roots:
            for root, dirs, files in os.walk(search_root):
                for f in files:
                    if f.lower().endswith(video_extensions):
                        full_path = os.path.join(root, f)
                        size = os.path.getsize(full_path)
                        
                        # If we are searching the generic root and have a hint, 
                        # try to verify the filename contains part of the hint?
                        # Or just rely on the folder check above. 
                        # If the torrent is a single file, it lands in download_dir directly.
                        # Ideally, we should check if 'torrent_name_hint' is in the filename?
                        
                        is_candidate = True
                        if torrent_name_hint and search_root == self.download_dir:
                            # If we are in the main dir, and we have a hint, 
                            # ensure the file matches the hint somewhat to avoid picking random old files.
                            # But torrent name might differ slightly from filename.
                            # Heuristic: If hint is "Movie.2020", file should probably contain "Movie".
                            pass
                            
                        if is_candidate:
                            if size > max_size:
                                max_size = size
                                largest_file = full_path
        
        if largest_file:
            print(f"   🎥 Found Video File: {largest_file}")
            return largest_file
        else:
            print("   ❌ No video file found in download directory.")
            return None
