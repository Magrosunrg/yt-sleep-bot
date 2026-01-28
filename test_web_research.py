import sys
import os
from web_researcher import WebResearcher

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

def test_filmsite():
    print("--- Testing WebResearcher (Filmsite) ---")
    wr = WebResearcher()
    movie = "Fight Club"
    print(f"Movie: {movie}")
    
    opening, ending = wr.get_filmsite_scenes(movie)
    
    if opening:
        print("\n✅ Found Opening Scene:")
        print(f"'{opening[:200]}...'")
    else:
        print("\n❌ Opening Scene NOT Found.")
        
    if ending:
        print("\n✅ Found Ending Scene:")
        print(f"'{ending[:200]}...'")
    else:
        print("\n❌ Ending Scene NOT Found.")

if __name__ == "__main__":
    test_filmsite()
