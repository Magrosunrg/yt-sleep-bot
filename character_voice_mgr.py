import os
import requests
import re
import yt_dlp
import time

# MoviePy imports with proper fallback
try:
    from moviepy.editor import AudioFileClip
except ImportError:
    try:
        from moviepy.audio.io.AudioFileClip import AudioFileClip
    except ImportError:
        from moviepy import AudioFileClip

# Ensure voices directory exists
VOICES_DIR = os.path.join(os.getcwd(), "voices")
if not os.path.exists(VOICES_DIR):
    os.makedirs(VOICES_DIR)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"

def parse_vtt_for_speech(vtt_path, min_duration=12):
    """
    Parses a VTT file to find a clean speech segment.
    Returns (start_time, end_time) or None.
    """
    if not os.path.exists(vtt_path):
        return None
        
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex for timestamp: 00:00:00.000 or 00:00.000
        time_pattern = re.compile(r'((?:\d{2}:)?\d{2}:\d{2}\.\d{3}) --> ((?:\d{2}:)?\d{2}:\d{2}\.\d{3})')
        
        blocks = content.split('\n\n')
        candidates = []
        
        def to_sec(t_str):
            parts = t_str.split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h)*3600 + int(m)*60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m)*60 + float(s)
            return 0.0

        for block in blocks:
            match = time_pattern.search(block)
            if not match: continue
                
            start_str, end_str = match.groups()
            start = to_sec(start_str)
            end = to_sec(end_str)
            
            # Clean text
            lines = [l for l in block.split('\n') if not time_pattern.search(l) and '-->' not in l and l.strip() != 'WEBVTT']
            text = " ".join(lines).strip().lower()
            
            # Filter bad blocks (indicators of multiple speakers or non-speech)
            if not text: continue
            bad_markers = ['[', ']', '(', ')', '♪', 'music', 'applause', 'cheering', 'laughter', 'screaming', 'yelling', 'explosion', 'gunshot', 'sound', 'noise']
            if any(x in text for x in bad_markers): continue
            if '>>' in block or '-' in block.split('\n')[0]: continue # Speaker change often marked with >> or -
            
            candidates.append({'start': start, 'end': end})
            
        # Find continuous chain of speech
        if not candidates: return None
        
        current_chain_start = candidates[0]['start']
        current_chain_end = candidates[0]['end']
        
        for i in range(1, len(candidates)):
            curr = candidates[i]
            prev = candidates[i-1]
            
            # If gap is small (< 2s), treat as continuous
            if curr['start'] - prev['end'] < 2.0:
                current_chain_end = curr['end']
            else:
                # Check if previous chain was long enough
                if current_chain_end - current_chain_start >= min_duration:
                    return (current_chain_start, current_chain_end) # Return FULL chain (start, end)
                
                # Reset
                current_chain_start = curr['start']
                current_chain_end = curr['end']
                
        # Check last chain
        if current_chain_end - current_chain_start >= min_duration:
             return (current_chain_start, current_chain_end)
            
        return None
        
    except Exception as e:
        print(f"⚠️ VTT Parse Error: {e}")
        return None

def identify_character(prompt, model=DEFAULT_MODEL):
    """
    Extracts the character name from the story prompt using Ollama.
    """
    system_prompt = (
        "Identify the MAIN character whose perspective the story is told from. "
        "Return ONLY the character name (and actor name if known/applicable). "
        "Do not return 'The Consultant' if it's Christoph Waltz, return 'Christoph Waltz'. "
        "If it's a fictional character without a known actor, return the character name. "
        "CRITICAL: If the user asks for a specific character (e.g. 'Tyler Durden'), return the actor who played THAT specific character (e.g. 'Brad Pitt'), NOT the narrator or other characters.\n"
        "Examples:\n"
        "Prompt: 'Tell the story from Elon Musk's perspective' -> Elon Musk\n"
        "Prompt: 'Story of The Consultant from Regus's perspective' -> Christoph Waltz\n"
        "Prompt: 'Story of Joker' -> Heath Ledger\n"
        "Prompt: 'Story of Fight Club from Tyler Durden's perspective' -> Brad Pitt\n"
        "Return ONLY the name."
    )
    
    payload = {
        "model": model,
        "prompt": f"{system_prompt}\n\nPrompt: {prompt}",
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            name = response.json().get("response", "").strip()
            # Cleanup
            name = re.sub(r'[^\w\s]', '', name)
            return name
    except Exception as e:
        print(f"❌ Character ID failed: {e}")
        return None

def get_character_reference(character_name, movie_name=None):
    """
    Downloads a reference audio clip for the character from YouTube.
    Tries to find a clean speaking segment (dialogue) from the movie if movie_name is provided.
    Retries multiple videos if one fails.
    """
    safe_name = character_name.replace(" ", "_")
    output_path = os.path.join(VOICES_DIR, f"{safe_name}.wav")
    
    if os.path.exists(output_path):
        print(f"✅ Voice reference found for {character_name}")
        return output_path
        
    print(f"🔍 Searching YouTube for voice reference: {character_name} (Movie: {movie_name})")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'outtmpl': os.path.join(VOICES_DIR, f"temp_{safe_name}_%(id)s.%(ext)s"), # Use ID to avoid conflicts
        'default_search': 'ytsearch5', # Search 5 videos for retry
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Construct Query
            if movie_name:
                # Prioritize "scene" and "dialogue" to find actual movie clips
                query = f"'{movie_name}' '{character_name}' speaking scene dialogue 1080p" 
            else:
                query = f"{character_name} interview monologue speech"
            
            print(f"   🔎 Query: {query}")
            info = ydl.extract_info(query, download=False)
            
            if not info or 'entries' not in info:
                return None
            
            # RETRY LOOP: Try each video in the results
            for entry in info['entries']:
                video_id = entry.get('id')
                video_title = entry.get('title', 'Unknown')
                duration = entry.get('duration', 0)
                
                # Skip shorts or very long full movies (unless we want to risk it, but >20 mins might be slow)
                # But user wants "from the movie", so maybe full movie clips are okay.
                # Let's stick to clips < 15 mins for speed, or assume we download only audio.
                # Audio download of 2 hours is fast.
                
                print(f"   🔄 Trying video: {video_title} ({duration}s)")
                
                try:
                    # Download this specific video
                    # We need to set the URL specifically or let ydl download the entry
                    # ydl.download([entry['webpage_url']]) -> This might re-trigger search if we are not careful
                    # But since we have the URL, it's fine.
                    
                    ydl.download([entry['webpage_url']])
                    
                    # Find the downloaded files for THIS video ID
                    temp_files = [f for f in os.listdir(VOICES_DIR) if f.startswith(f"temp_{safe_name}_{video_id}") and not f.endswith('.vtt')]
                    vtt_files = [f for f in os.listdir(VOICES_DIR) if f.startswith(f"temp_{safe_name}_{video_id}") and f.endswith('.vtt')]
                    
                    if not temp_files:
                        print(f"      ⚠️ No audio file found for {video_id}. Retrying next...")
                        continue
                        
                    temp_file = os.path.join(VOICES_DIR, temp_files[0])
                    print(f"      ✅ Audio downloaded: {temp_files[0]}")
                    
                    # Analyze VTT
                    start_time = 0
                    if duration > 0:
                         start_time = duration / 2 # Default to middle
                    
                    vtt_path = None
                    seg = None  # Initialize seg to None
                    if vtt_files:
                        vtt_path = os.path.join(VOICES_DIR, vtt_files[0])
                        print(f"      📜 Parsing subtitles: {vtt_files[0]}")
                        seg = parse_vtt_for_speech(vtt_path)
                        if seg:
                            start_time, end_time = seg
                            print(f"      🎯 Found clean speech: {start_time}s - {end_time}s")
                        else:
                            print("      ⚠️ No clean speech segment found in subs.")
                            # If we strictly want clean speech, we might want to skip this video?
                            # But fallback is better than nothing.
                            # Let's continue with default middle if movie_name is not set, 
                            # but if movie_name IS set, maybe we want to be stricter?
                            # For now, use fallback.
                    
                    # Extract 15s Clip (or up to natural break)
                    print(f"      ✂️ Extracting sample starting at {start_time}s...")
                    
                    try:
                        clip = AudioFileClip(temp_file)
                        
                        # Determine natural end time
                        # If we have VTT data, end_time is the natural end of a sentence/phrase
                        if seg:
                            # If natural end is waay too long (> 30s), we might still want to cut, 
                            # but ideally we find a break earlier. For now, let's just cap it at 20s.
                            # But if the natural end is close (e.g. 16s), use it.
                            natural_duration = end_time - start_time
                            if natural_duration > 20:
                                end_t = start_time + 15
                            else:
                                end_t = end_time
                        else:
                            # Fallback if no VTT
                            end_t = min(start_time + 15, clip.duration)
                        
                        # Safety checks
                        if end_t > clip.duration: end_t = clip.duration
                        
                        if end_t - start_time < 3:
                            # Too short? try to extend
                            end_t = min(start_time + 10, clip.duration)
                        
                        print(f"      ✂️ Final Cut: {start_time}s to {end_t}s (Duration: {end_t - start_time:.1f}s)")
                        
                        subclip = clip.subclip(start_time, end_t)
                        subclip.write_audiofile(output_path, codec='pcm_s16le', fps=22050, verbose=False, logger=None)
                        clip.close()
                        subclip.close()
                        
                        # Verify output exists and has size
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                            print(f"   ✅ Success! Voice reference saved: {output_path}")
                            
                            # CLEANUP
                            try: os.remove(temp_file)
                            except: pass
                            if vtt_path: 
                                try: os.remove(vtt_path)
                                except: pass
                                
                            return output_path
                        else:
                            print("      ❌ Extraction failed (file empty or missing).")
                            
                    except Exception as ex:
                        print(f"      ❌ Extraction error: {ex}")
                    
                    # Cleanup on failure
                    try: os.remove(temp_file)
                    except: pass
                    if vtt_path: 
                        try: os.remove(vtt_path)
                        except: pass
                        
                except Exception as e:
                    print(f"      ❌ Download/Process failed for video {video_id}: {e}")
                    continue
            
            print("❌ All retries failed. Could not get voice reference.")
            return None
            
    except Exception as e:
        print(f"❌ Voice retrieval critical failure: {e}")
        return None

if __name__ == "__main__":
    # Test
    name = identify_character("Tell the story of 'The Consultant' from Regus's perspective")
    print(f"Character: {name}")
    if name:
        get_character_reference(name)
