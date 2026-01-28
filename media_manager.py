import os
import requests
import random
import re
import shutil
from typing import Optional

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

class MediaManager:
    PIXABAY_KEY = "53831594-57335d5f2bda798c1cdd84801"

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.headers = {"Authorization": self.api_key} if self.api_key else {}

    def search_video(self, query: str, orientation: str = "landscape", per_page: int = 15, context_subject: str = None) -> dict:
        """
        Search for a video and return the download URL or local path with source info.
        Priority: 
        - If context_subject (e.g. Movie Name) is provided: YouTube -> X -> Stock
        - Otherwise: Pexels -> Pixabay -> Mixkit -> YouTube -> X
        Returns: {'url': str, 'source': str} or None
        """
        if not query or not query.strip():
            return None
        
        # Helper for recursive fallback
        def try_search(q, attempt_youtube_x=True, specific_subject=None):
            # 0. Specific Subject Search (YouTube Priority)
            if specific_subject and yt_dlp:
                # Construct a specific query
                # Use "scene" to find clips from movies/series
                yt_query = f"{specific_subject} {q} scene"
                print(f"🎬 Searching YouTube for specific subject: {yt_query}")
                path = self._search_youtube(yt_query)
                if path:
                    return {'url': path, 'source': 'YouTube'}
                
                # Fallback to just subject + query (broad)
                yt_query = f"{specific_subject} {q}"
                path = self._search_youtube(yt_query)
                if path:
                    return {'url': path, 'source': 'YouTube'}

            # 1. Pexels (Stock - Safe Zone)
            if self.api_key and not specific_subject:
                url = self._search_pexels(q, orientation, per_page)
                if url: 
                    print(f"Found on Pexels: {q}")
                    return {'url': url, 'source': 'Pexels'}
            
            # 2. Pixabay (Stock)
            if not specific_subject:
                url = self._search_pixabay(q)
                if url: 
                    print(f"Found on Pixabay: {q}")
                    return {'url': url, 'source': 'Pixabay'}
            
            # 3. Mixkit (Stock)
            if not specific_subject:
                url = self.search_video_mixkit(q)
                if url: 
                    print(f"Found on Mixkit: {q}")
                    return {'url': url, 'source': 'Mixkit'}
            
            if not attempt_youtube_x:
                return None

            # 4. YouTube (Evidence Zone / Fallback)
            if yt_dlp:
                yt_query = f"{q} news footage creative commons" if not specific_subject else f"{q} scene"
                path = self._search_youtube(yt_query)
                if path: 
                    print(f"Found on YouTube: {yt_query}")
                    return {'url': path, 'source': 'YouTube'}

            # 5. X (Reaction Zone)
            if yt_dlp:
                x_query = f"{q} official video"
                path = self._search_twitter(x_query)
                if path:
                    print(f"Found on X (Twitter): {x_query}")
                    return {'url': path, 'source': 'X (Twitter)'}
            
            return None
        
        # 1. Try full query
        result = try_search(query, specific_subject=context_subject)
        if result: return result
        
        # Fallback: If specific search failed, try generic stock
        if context_subject:
             print(f"⚠️ Specific search for '{context_subject}' failed. Falling back to generic stock for '{query}'")
             result = try_search(query, specific_subject=None)
             if result: return result

        # 2. Try first 2 words if query is long (Stock only first)
        words = query.split()
        if len(words) > 2:
            short_query = " ".join(words[:2])
            print(f"Retrying search with: {short_query}")
            result = try_search(short_query, attempt_youtube_x=False, specific_subject=None) 
            if result: return result
            
        # 3. Try last word (Subject)
        if len(words) > 1:
            last_word = words[-1]
            print(f"Retrying search with: {last_word}")
            result = try_search(last_word, specific_subject=None)
            if result: return result
            
        return None

    def search_candidates(self, query: str, per_page: int = 10) -> list:
        """Returns a list of candidate dicts: {url, thumbnail, source, id} for CLIP scoring."""
        candidates = []
        
        # 1. Pexels Candidates
        if self.api_key:
            url = f"https://api.pexels.com/videos/search?query={query}&per_page={per_page}&orientation=landscape"
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for vid in data.get("videos", []):
                        # Find best video file (1080p preferred)
                        best_link = None
                        video_files = vid.get("video_files", [])
                        
                        hd_files = [f for f in video_files if f.get("height") == 1080]
                        if hd_files: 
                            best_link = hd_files[0].get("link")
                        elif video_files:
                            best_link = video_files[0].get("link")
                        
                        if best_link:
                            candidates.append({
                                "url": best_link,
                                "thumbnail": vid.get("image"), 
                                "source": "Pexels",
                                "id": vid.get("id")
                            })
            except Exception as e:
                print(f"Pexels Candidate Search Error: {e}")
        
        return candidates

    def _search_pexels(self, query: str, orientation: str, per_page: int) -> Optional[str]:
        # Pexels Video Search API
        url = f"https://api.pexels.com/videos/search?query={query}&per_page={per_page}&orientation={orientation}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                videos = data.get("videos", [])
                if videos:
                    video = random.choice(videos)
                    video_files = video.get("video_files", [])
                    
                    # Sort to find best quality matching orientation
                    best_file = None
                    target_w = 1920 if orientation == "landscape" else 1080
                    target_h = 1080 if orientation == "landscape" else 1920
                    
                    for vf in video_files:
                        if vf.get("width") == target_w and vf.get("height") == target_h:
                            best_file = vf
                            break
                    
                    if not best_file:
                        # Fallback to any HD
                        hd_files = [f for f in video_files if f.get("quality") == "hd"]
                        if hd_files:
                            best_file = hd_files[0]
                        elif video_files:
                            best_file = video_files[0]

                    if best_file:
                        return best_file.get("link")
            else:
                print(f"Pexels API Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Media Search Error: {e}")
        return None

    def _search_pixabay(self, query: str) -> Optional[str]:
        """Checks Pixabay as a secondary stock source."""
        url = f"https://pixabay.com/api/videos/?key={self.PIXABAY_KEY}&q={query}&per_page=3"
        try:
            r = requests.get(url, timeout=10).json()
            if r.get('hits'):
                return r['hits'][0]['videos']['medium']['url']
        except Exception as e:
            print(f"Pixabay Search Error: {e}")
        return None

    def _search_youtube(self, query: str) -> Optional[str]:
        """Search and download a snippet from YouTube using yt-dlp."""
        filename = f"temp_yt_{random.randint(1000, 9999)}.mp4"
        
        try:
            # 1. Get Info First
            ydl_opts_info = {
                'default_search': 'ytsearch1:',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            }
            
            video_url = None
            duration = 0
            
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(query, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                
                video_url = info.get('webpage_url')
                duration = info.get('duration', 0)
                
            if not video_url:
                return None

            # 2. Determine Download Range
            # If video is short (< 60s), download all. 
            # If long, download a 10s clip from 10% in (skipping intro).
            download_ranges = None
            
            if duration > 0 and duration < 60:
                print(f"   ⬇️ Downloading full short video ({duration}s): {query}")
                download_ranges = None # Full download
            else:
                # Pick a segment. For "scenes", the start is usually good.
                start = min(duration * 0.1, 15) # Start at 10% or 15s, whichever is smaller
                end = start + 10 # 10s clip
                print(f"   ⬇️ Downloading snippet {start}-{end}s from {duration}s video: {query}")
                
                download_ranges = lambda info, ydl: [{'start_time': start, 'end_time': end}]

            # 3. Download
            ydl_opts = {
                'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]',
                'quiet': True,
                'no_warnings': True,
                'outtmpl': filename,
                'force_keyframes_at_cuts': True,
            }
            
            if download_ranges:
                ydl_opts['download_ranges'] = download_ranges
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                
            if os.path.exists(filename):
                return os.path.abspath(filename)
                
        except Exception as e:
            print(f"YouTube Search Error: {e}")
            if os.path.exists(filename):
                try: os.remove(filename)
                except: pass
                
        return None

    def _search_twitter(self, query: str) -> Optional[str]:
        """Search for a video on X/Twitter via DuckDuckGo scraping and download with yt-dlp."""
        filename = f"temp_x_{random.randint(1000, 9999)}.mp4"
        
        # 1. Find tweet URLs using DuckDuckGo
        tweet_urls = self._find_twitter_urls(query)
        if not tweet_urls:
            return None
            
        print(f"Found {len(tweet_urls)} potential X links. Trying to download...")
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            'quiet': True,
            'no_warnings': True,
            'outtmpl': filename,
        }
        
        for url in tweet_urls:
            print(f"Trying X URL: {url}")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    if os.path.exists(filename):
                        # Verify file size > 0
                        if os.path.getsize(filename) > 0:
                            return os.path.abspath(filename)
            except Exception as e:
                print(f"X Download Failed for {url}: {e}")
                
        return None

    def _find_twitter_urls(self, query: str) -> list:
        """Scrapes DuckDuckGo for twitter video URLs."""
        urls = []
        try:
            # Query: site:twitter.com OR site:x.com [query] video
            search_term = f"site:twitter.com {query} video"
            url = "https://html.duckduckgo.com/html/"
            payload = {'q': search_term}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                # Regex for twitter/x status URLs
                pattern = r'(https?://(?:twitter\.com|x\.com)/[^/]+/status/\d+)'
                matches = re.findall(pattern, response.text)
                if matches:
                    # Deduplicate and return
                    urls = list(set(matches))
        except Exception as e:
            print(f"DuckDuckGo Search Error: {e}")
            
        return urls

    def search_video_mixkit(self, query: str) -> Optional[str]:
        """Search for a video on Mixkit (No API Key required)."""
        try:
            # Slugify query
            slug = query.lower().strip().replace(" ", "-")
            url = f"https://mixkit.co/free-stock-video/{slug}/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                # Find all mp4 links
                matches = re.findall(r'(https://assets.mixkit.co/videos/[^"]+\.mp4)', response.text)
                if matches:
                    # Prefer 1080p, then 720p, then 360p
                    unique_matches = list(set(matches))
                    
                    # Sort by resolution priority
                    def resolution_score(url):
                        if "1080" in url: return 3
                        if "720" in url: return 2
                        if "360" in url: return 1
                        return 0
                        
                    unique_matches.sort(key=resolution_score, reverse=True)
                    return unique_matches[0]
        except Exception as e:
            print(f"Mixkit Search Error: {e}")
        return None

    def search_image(self, query: str, orientation: str = "landscape") -> Optional[str]:
        """Search for an image on Pexels."""
        if not self.api_key:
            return None
            
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=15&orientation={orientation}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                photos = data.get("photos", [])
                if photos:
                    photo = random.choice(photos)
                    return photo["src"]["large2x"]
        except Exception as e:
            print(f"Image Search Error: {e}")
        return None

    def download_file(self, url_or_path: str, filename: str) -> bool:
        # Check if it's a local file path (from YouTube or cache)
        # Note: url_or_path could be a windows path 'C:\\...' or url 'http...'
        is_local = False
        try:
            if os.path.exists(url_or_path) and os.path.isfile(url_or_path):
                is_local = True
        except:
            pass
            
        if is_local:
             try:
                 if os.path.abspath(url_or_path) != os.path.abspath(filename):
                     shutil.copy2(url_or_path, filename)
                 return True
             except Exception as e:
                 print(f"File Copy Error: {e}")
                 return False

        try:
            response = requests.get(url_or_path, stream=True, timeout=20)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
        except Exception as e:
            print(f"Download Error: {e}")
        return False
