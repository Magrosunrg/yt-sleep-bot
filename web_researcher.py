import requests
from bs4 import BeautifulSoup
import re
import time
import random

# Mocking WebSearch since we are inside the environment where we can only use the provided tool.
# However, the user wants me to implement this logic. 
# Since I cannot call "WebSearch" from within the python script (unless I wrap the tool call),
# I must assume the python script runs in an environment where it can access the web OR
# I (the agent) perform the search and pass the results to the script.
#
# BUT, the user said "ollama can use `https://...`". 
# This implies the script should fetch the content.
# 
# Given the environment restrictions (I don't know if the python environment has internet access),
# I should probably rely on the Agent (me) to do the fetching and pass it as arguments,
# OR assume `requests` works.
# 
# The user's prompt implies automation: "ollama can use...".
# I will implement a class that *attempts* to fetch if possible, or expects data to be passed.
#
# Actually, the best approach for this "pair programming" session is:
# 1. I (the Agent) use WebSearch to get the info.
# 2. I pass the extracted info into the `generate_story_script` function as arguments.
# 
# HOWEVER, to make it "automated" for future runs (without me), the script needs to do it.
# I will assume the script can make HTTP requests.
# I will implement a `WebResearcher` class.

class WebResearcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def clean_text(self, text):
        return re.sub(r'\s+', ' ', text).strip()

    def get_filmsite_slug(self, movie_name):
        # Basic slugify: Fight Club -> fightclub
        return re.sub(r'[^a-z0-9]', '', movie_name.lower())

    def search_filmsite(self, movie_name):
        """
        Attempts to find the filmsite.org page for the movie.
        Since we can't easily use a search engine API in raw python without a key,
        we will try to guess the URL.
        """
        slug = self.get_filmsite_slug(movie_name)
        url = f"https://www.filmsite.org/{slug}.html"
        
        try:
            print(f"   🔎 Checking Filmsite URL: {url}...")
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                return url, response.text
            
            # Try with 'the' removed or added?
            if "the" in slug:
                slug_no_the = slug.replace("the", "")
                url2 = f"https://www.filmsite.org/{slug_no_the}.html"
                print(f"   🔎 Checking Filmsite URL: {url2}...")
                response = requests.get(url2, headers=self.headers, timeout=5)
                if response.status_code == 200:
                    return url2, response.text
            
            return None, None
        except Exception as e:
            print(f"   ⚠️ Filmsite lookup failed: {e}")
            return None, None

    def get_filmsite_scenes(self, movie_name):
        url, html = self.search_filmsite(movie_name)
        if not html:
            return None, None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Filmsite structure varies, but main text is often in <font size="2"> or paragraphs
        # We want the beginning and end.
        paragraphs = soup.find_all('p')
        text_paragraphs = [p.get_text() for p in paragraphs if len(p.get_text()) > 100]
        
        if not text_paragraphs:
            # Fallback for older HTML structure
            text = soup.get_text()
            # Split by newlines and filter
            text_paragraphs = [t for t in text.split('\n\n') if len(t) > 100]

        if not text_paragraphs:
            return None, None
            
        opening_scene = text_paragraphs[0] + "\n" + text_paragraphs[1] if len(text_paragraphs) > 1 else text_paragraphs[0]
        
        # Ending is tricky because of footers. Take the last substantial paragraph.
        # Filter out "copyright" or "rights reserved"
        valid_endings = [p for p in text_paragraphs[-5:] if "copyright" not in p.lower() and "rights reserved" not in p.lower()]
        ending_scene = valid_endings[-1] if valid_endings else text_paragraphs[-1]
        
        return opening_scene, ending_scene

    def get_ranker_best_quote(self, movie_name):
        """
        Searches Ranker for "[Movie Name] Best Quotes" and extracts the #1 ranked quote.
        """
        try:
            # 1. Search Ranker API
            search_url = "https://api.ranker.com/search"
            params = {
                "term": f"{movie_name} best quotes"
            }
            # Ranker API requires a User-Agent
            print(f"   🔎 Searching Ranker for '{movie_name} best quotes'...")
            response = requests.get(search_url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"   ⚠️ Ranker Search API failed: {response.status_code}")
                return None
            
            data = response.json()
            items = data.get("items", [])
            
            if not items:
                print("   ⚠️ No Ranker lists found.")
                return None
            
            # Find the best matching list (prefer "Best Quotes" in title)
            target_item = None
            for item in items:
                name = item.get("name", "").lower()
                if "quote" in name and movie_name.lower() in name:
                    target_item = item
                    break
            
            if not target_item:
                target_item = items[0] # Fallback to first result
                
            list_url = target_item.get("url")
            if not list_url:
                return None
                
            if list_url.startswith("//"):
                list_url = "https:" + list_url
                
            print(f"   🔎 Fetching Ranker List: {list_url}")
            
            # 2. Fetch List Page
            list_resp = requests.get(list_url, headers=self.headers, timeout=10)
            if list_resp.status_code != 200:
                return None
                
            html = list_resp.text
            
            # 3. Extract JSON Data
            import json
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
            if not match:
                print("   ⚠️ Could not find __NEXT_DATA__ in Ranker page.")
                return None
                
            next_data = json.loads(match.group(1))
            
            # Navigate to items
            # Path: props -> pageProps -> listContext -> pageData -> listItems
            try:
                list_items = next_data['props']['pageProps']['listContext']['pageData']['listItems']
            except KeyError:
                print("   ⚠️ Could not navigate JSON structure in Ranker data.")
                return None
                
            if not list_items:
                return None
                
            # Find #1 rank
            # Usually sorted, but let's be safe
            best_item = None
            for item in list_items:
                if item.get("rank") == 1:
                    best_item = item
                    break
            
            if not best_item and list_items:
                best_item = list_items[0]
                
            if best_item:
                quote_html = best_item.get("blather", "") or best_item.get("name", "")
                # Clean HTML tags
                soup = BeautifulSoup(quote_html, "html.parser")
                quote_text = soup.get_text()
                print(f"   ✅ Found Best Quote: {quote_text[:50]}...")
                return quote_text.strip()
                
            return None

        except Exception as e:
            print(f"   ⚠️ Ranker lookup failed: {e}")
            return None

    def search_ranker_best_quote(self, movie_name):
        """
        Searches Ranker for the best quote/scene.
        Since we can't use Google Search API, we'll try to construct a query 
        or rely on the user providing the info if this fails.
        
        For now, we will try to scrape a likely URL if possible, 
        but Ranker URLs are not predictable (they have slugs like 'fight-club-movie-quotes').
        
        Strategy: Try to construct the likely list URL.
        """
        slug = movie_name.lower().replace(" ", "-")
        # Common format: https://www.ranker.com/list/[movie-name]-movie-quotes/[author]
        # This is too hard to guess.
        
        # Alternative: We return a generic instruction for Ollama 
        # if we can't find the specific ranker list.
        # BUT, the user explicitly said "ollama can use...".
        # This implies I should perhaps implement a function that takes a URL 
        # if the USER provided one, or I (the agent) should have found it.
        
        return None

if __name__ == "__main__":
    wr = WebResearcher()
    o, e = wr.get_filmsite_scenes("Fight Club")
    print("Opening:", o[:100])
    print("Ending:", e[:100])
