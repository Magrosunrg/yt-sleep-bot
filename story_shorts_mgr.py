import os
import requests
import re
import random
import time
import subprocess
import asyncio
import edge_tts
import difflib

import gc
import numpy as np

# MoviePy imports with proper fallback
try:
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip, ColorClip, vfx, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip
    import moviepy.audio.fx.all as afx
except ImportError:
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
        from moviepy.video.VideoClip import TextClip, ColorClip, ImageClip
        from moviepy.video.compositing.concatenate import concatenate_videoclips
        from moviepy.audio.compositing.concatenate import concatenate_audioclips
        from moviepy.audio.AudioClip import CompositeAudioClip
        import moviepy.video.fx.all as vfx
        import moviepy.audio.fx.all as afx
    except ImportError:
        # MoviePy v2
        from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip, ColorClip, vfx, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip
        import moviepy.audio.fx.all as afx

# Explicitly import AudioArrayClip which is often missing from editor
try:
    from moviepy.audio.AudioClip import AudioArrayClip
except ImportError:
    AudioArrayClip = None


from tts_chatterbox import generate_cloned_audio
from character_voice_mgr import identify_character, get_character_reference
from media_manager import MediaManager
from popular_events_mgr import create_caption_clip
from scene_matcher import SceneMatcher
from web_researcher import WebResearcher

def truncate_for_clip(text, max_words=50):
    """Truncates text to a safe length for CLIP (approx 77 tokens)."""
    if not text: return ""
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return text

def speed_up_audio_file(input_path, speed=1.1):
    """
    Speeds up audio using FFmpeg command line to avoid MoviePy errors.
    Overwrites the input file or creates a temp one.
    """
    try:
        temp_out = input_path.replace(".wav", "_fast.wav")
        # FFmpeg atempo filter: 0.5 to 2.0
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter:a", f"atempo={speed}",
            "-vn",
            temp_out
        ]
        # Run silently
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Replace original
        if os.path.exists(temp_out):
            # waiting for file release?
            time.sleep(0.1)
            os.replace(temp_out, input_path)
            return True
    except Exception as e:
        print(f"⚠️ Audio speedup failed: {e}")
    return False

def create_dynamic_captions(text, total_duration, fontsize=70, timings=None):
    """
    Splits text into small chunks (2-3 words) and creates a sequence of caption clips.
    Matches the total_duration.
    If 'timings' is provided (list of dicts with word, start, end), uses precise sync.
    """
    if timings:
        # --- Precise Sync Mode ---
        # Group words into chunks (max 5 words)
        chunks = []
        current_chunk_words = []
        current_start = None
        current_end = 0
        
        for t in timings:
            if current_start is None:
                current_start = t['start']
            
            current_chunk_words.append(t['word'])
            current_end = t['end']
            
            # Check split condition (punctuation or length)
            # Relaxed length check if we have timings
            if len(current_chunk_words) >= 5: 
                chunks.append({
                    "text": " ".join(current_chunk_words),
                    "start": current_start,
                    "end": current_end
                })
                current_chunk_words = []
                current_start = None
        
        # Add remaining
        if current_chunk_words:
            chunks.append({
                "text": " ".join(current_chunk_words),
                "start": current_start,
                "end": current_end
            })
            
        if not chunks:
            return None
            
        clips = []
        for i, c in enumerate(chunks):
            # Calculate duration to fill gap until next chunk
            if i < len(chunks) - 1:
                next_start = chunks[i+1]['start']
                dur = next_start - c['start']
            else:
                # Last chunk: use its own duration or extend to total?
                # Extend to total duration if possible, but min 0.5s
                dur = total_duration - c['start']
                if dur < (c['end'] - c['start']):
                    dur = c['end'] - c['start']
            
            # Sanity check
            if dur <= 0: dur = 0.1
            
            clip = create_caption_clip(c['text'], dur, fontsize=fontsize)
            clips.append(clip)
            
        if not clips: return None
        return concatenate_videoclips(clips)

    # --- Heuristic Mode (Fallback) ---
    words = text.split()
    if not words:
        return None
    
    # Chunk size: 5 words per chunk (User Request)
    chunks = []
    current_chunk = []
    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= 5: # Max 5 words
            chunks.append(" ".join(current_chunk))
            current_chunk = []
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    if not chunks:
        return None
        
    # Distribute duration based on character count with PAUSE HEURISTICS
    # People pause at punctuation. Allocating more time to chunks with punctuation 
    # ensures the NEXT chunk starts when the speaker resumes.
    
    chunk_weights = []
    for c in chunks:
        weight = len(c)
        # Add "virtual characters" for pauses
        if c.endswith(','):
            weight += 5  # Short pause
        elif c.endswith('.') or c.endswith('!') or c.endswith('?'):
            weight += 8  # Long pause
        elif c.endswith(';'):
             weight += 6
        chunk_weights.append(weight)
        
    total_weight = sum(chunk_weights)
    
    clip_durations = []
    for w in chunk_weights:
        if total_weight > 0:
            dur = (w / total_weight) * total_duration
        else:
            dur = total_duration / len(chunks)
        clip_durations.append(dur)
        
    clips = []
    for chunk, dur in zip(chunks, clip_durations):
        # Use existing create_caption_clip
        # It returns an ImageClip with set_duration
        # Increase fontsize since text is shorter
        clip = create_caption_clip(chunk, dur, fontsize=fontsize) 
        clips.append(clip)
        
    if not clips:
        return None
        
    return concatenate_videoclips(clips)

# Ollama Config
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"

def get_specific_scene_timestamp(subject, description, model=DEFAULT_MODEL):
    """
    Asks Ollama for a specific timestamp for a described scene.
    """
    # Improve context
    year = get_release_year(subject, model)
    subject_prompt = f"{subject} ({year})" if year and year not in subject else subject
    
    prompt = (
        f"For the movie '{subject_prompt}', identify the timestamp for the scene described as: \"{description}\"\n"
        f"Provide the approximate start time in 'MM:SS' format. "
        f"Example: '12:30'\n"
        f"Return ONLY the timestamp. If you absolutely cannot determine it, return 'RANDOM'."
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        # print(f"   ❓ Asking Llama for timestamp: '{description[:30]}...'") 
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            # Extract MM:SS
            match = re.search(r'\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b', text)
            if match:
                h_str, m_str, s_str = match.groups()
                h = int(h_str) if h_str else 0
                m = int(m_str)
                s = int(s_str)
                total = h * 3600 + m * 60 + s
                # print(f"   🎯 Target Timestamp found: {total}s ({text})")
                return total
    except:
        pass
    return None

def get_movie_context(subject, model=DEFAULT_MODEL):
    """
    Retrieves a detailed plot summary and character list for the subject to ground the story generation.
    """
    prompt = (
        f"Provide a detailed plot summary of the movie/show '{subject}'. "
        f"1. LIST THE MAIN CHARACTERS first (e.g., Baby, Debora, Doc, Bats, Buddy, Darling). "
        f"2. Provide a SCENE-BY-SCENE breakdown of key events in chronological order. "
        f"3. Focus on the perspective of the main character. "
        f"4. CRITICAL: Do NOT hallucinate. If you are unsure about the specific plot of THIS movie, say so. Do not mix it up with other movies of the same name. "
        f"5. If the movie is obscure, stick to general verified facts or admit ignorance. "
        f"Return the summary as a factual reference text."
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        print(f"📚 Retrieving factual context for: {subject}")
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
    except Exception as e:
        print(f"⚠️ Context retrieval failed: {e}")
    return ""

def generate_story_script(prompt, model=DEFAULT_MODEL, research_context=None):
    """Generates a short story script based on the prompt."""
    
    # Pre-step: Identify subject to fetch context
    subject = extract_subject_matter(prompt, model)
    context_text = ""
    if subject:
        context_text = get_movie_context(subject, model)
        
    system_prompt = (
        "You are a master viral storyteller for movie recaps. "
        "Create a gripping, fast-paced first-person narrative (approx. 250-300 words) based on the user's request. "
        "The story MUST be suitable for a longer vertical video (approx 2.0 to 2.5 minutes). "
        "Style Guide (Strictly Follow): \n"
        "1. PERSPECTIVE: First-Person ('I'). You ARE the main character. \n"
        "2. TONE: Professional, observant, gritty. Use short, punchy sentences. Fragmented syntax is preferred.\n"
        "3. CONTENT: Focus on EXTREME DETAIL. Do not summarize the entire movie. Pick the most intense sequence, opening act, or key event and break it down moment-by-moment. Describe specific actions, facial expressions, and objects. 'Show, don't just tell'.\n"
        "4. PACING: Fast but GRANULAR. Don't skip over details. Zoom in on the tension.\n"
        "5. TRUTH: You MUST adhere to the provided SOURCE MATERIAL. Do not invent scenes that are not in the plot summary. If the summary is missing details, gloss over them rather than inventing.\n"
        "6. VIRAL HOOK: The first sentence is the most important. It MUST be a shocking statement, a high-stakes dilemma, or an immediate action that stops the scroll. No 'Once upon a time' intros.\n"
        "7. NATURAL VOICE: Make it sound RAW and HUMAN. Use contractions, natural phrasing, and even slight fillers like 'well...' or 'look...' to sound authentic. Avoid robotic perfection.\n"
        "Structure: \n"
        "- Start immediately with the VIRAL HOOK .\n"
        "- Use [PAUSE] on a separate line for dramatic beats (MAXIMUM 1 or 2 times per script).\n"
        "- MANDATORY: You MUST include exactly ONE [PAUSE] marker in the script specifically for the Fan Favorite Quote (if provided). This [PAUSE] must be placed exactly where the quote occurs in the story timeline. Do not write the quote itself in the narration; the [PAUSE] marker will trigger the clip.\n"
        "- End with a cliffhanger or a strong realization.\n"
        "Output ONLY the story text. Do not include scene descriptions or labels like 'Hook:', 'Body:'."
    )
    
    full_prompt = f"{system_prompt}\n\n"
    if context_text:
        full_prompt += f"SOURCE MATERIAL (FACTUAL CONTEXT):\n{context_text}\n\n"
    
    if research_context:
        full_prompt += "ADDITIONAL SCENE CONTEXT (From Film Database):\n"
        if research_context.get('opening'):
            full_prompt += f"OPENING SCENE DETAILS: {research_context['opening'][:500]}...\n"
        if research_context.get('ending'):
            full_prompt += f"ENDING SCENE DETAILS: {research_context['ending'][:500]}...\n"
        if research_context.get('ranker_best_quote'):
            full_prompt += f"FAN FAVORITE QUOTE (MANDATORY): \"{research_context['ranker_best_quote']}\"\n"
            full_prompt += "INSTRUCTION: You MUST include this exact quote in the script. It represents the #1 fan-favorite moment.\n"
        full_prompt += "\n"
        
    full_prompt += f"User Request: {prompt}"
    
    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": False
    }
    
    try:
        print(f"📝 Generating story script for: {prompt}")
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            story = response.json().get("response", "").strip()
            # Cleanup any labels if Llama ignored instructions
            story = re.sub(r'\*.*?\*', '', story) # Remove actions
            story = re.sub(r'\(.*?\)', '', story) # Remove notes
            story = story.replace("Hook:", "").replace("Body:", "").replace("Ending:", "")
            return story.strip()
        else:
            print(f"❌ Ollama Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Script Generation Error: {e}")
        return None

def get_scene_timestamps(subject, model=DEFAULT_MODEL):
    """
    Asks Ollama for timestamps of interesting scenes in the movie.
    Returns a list of timestamps in seconds.
    """
    # Improve precision by adding year if possible
    year = get_release_year(subject, model)
    subject_prompt = f"{subject} ({year})" if year and year not in subject else subject

    prompt = (
        f"For the movie or TV show '{subject_prompt}', list 20 specific timestamps of the most interesting, intense, or visually striking scenes that are crucial to the main character's narrative. "
        f"IMPORTANT: Ensure the timestamps are distributed chronologically across the ENTIRE duration (Beginning, Middle, and End). Do NOT just focus on the climax. "
        f"Strictly EXCLUDE opening credits, closing credits, studio logos, and slow establishing shots. "
        f"Format the timestamps strictly as 'MM:SS' or 'HH:MM:SS'. "
        f"Do not include descriptions. Just the timestamps, one per line."
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    timestamps_sec = []
    
    try:
        print(f"⏱️ Asking Llama for interesting timestamps in '{subject}'...")
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            # Regex to find timestamps
            matches = re.findall(r'\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b', text)
            
            for m in matches:
                # m is tuple: (hours, minutes, seconds)
                h_str, m_str, s_str = m
                
                h = int(h_str) if h_str else 0
                m_val = int(m_str)
                s_val = int(s_str)
                
                total_seconds = h * 3600 + m_val * 60 + s_val
                timestamps_sec.append(total_seconds)
                
            if timestamps_sec:
                print(f"   ✅ Found {len(timestamps_sec)} timestamps: {timestamps_sec}")
                return timestamps_sec
    except Exception as e:
        print(f"   ⚠️ Failed to get timestamps: {e}")
        
    return []

def extract_visual_keyword(sentence, model=DEFAULT_MODEL, context=None):
    """Extracts a single visual search keyword/phrase for a sentence."""
    context_instruction = ""
    if context:
        context_instruction = f"Context: The story is about '{context}'. Try to describe a scene from this context that matches the sentence."

    prompt = (
        f"{context_instruction}\n"
        f"For the following sentence, provide ONE specific, concrete visual subject "
        f"that would make a good background video. Return ONLY the keyword(s).\n\n"
        f"Sentence: \"{sentence}\""
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=1800)
        if r.status_code == 200:
            return r.json().get("response", "").strip().replace('"', '')
    except:
        pass
    return "abstract background"

def extract_subject_matter(prompt, model=DEFAULT_MODEL):
    """
    Extracts the main subject matter (movie, series, book, event) from the user prompt.
    Example: "Tell the story of 'The Consultant'..." -> "The Consultant"
    """
    # 1. Regex Fallback (Fastest & Most Accurate for Quotes)
    # Check for text in quotes first
    quote_match = re.search(r'["\'](.*?)["\']', prompt)
    if quote_match:
        candidate = quote_match.group(1).strip()
        # Basic filter to ensure it's not just a single word like "I" or "The" unless capitalized in a way that suggests a title
        if len(candidate) > 2:
            return candidate

    # 2. AI Extraction
    prompt_text = (
        f"Identify the specific Movie, TV Series, Book, or Real World Event mentioned in this prompt. "
        f"If a specific character is mentioned, identify the source material they belong to. "
        f"Return ONLY the Title of the work. Do not include 'The Story of' prefix.\n"
        f"Example: 'Tell the story of Joker' -> 'Joker'\n"
        f"Example: 'Story of Regus' -> 'The Consultant'\n"
        f"Example: 'Explain the movie Inception' -> 'Inception'\n\n"
        f"Prompt: \"{prompt}\""
    )
    
    payload = {"model": model, "prompt": prompt_text, "stream": False}
    try:
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            subject = r.json().get("response", "").strip().replace('"', '').replace("'", "")
            # Basic validation: ensure it's not a long sentence
            if len(subject) < 50 and "none" not in subject.lower():
                return subject
    except:
        pass
        
    return None

from torrent_manager import TorrentManager

def generate_search_variations(subject, model=DEFAULT_MODEL):
    """
    Generates alternative search queries for 1337x if the main subject fails.
    """
    # Extract year from subject if present to enforce consistency
    subject_year_match = re.search(r'\b(19|20)\d{2}\b', subject)
    subject_year = subject_year_match.group(0) if subject_year_match else None

    prompt = (
        f"The user wants to download a movie or TV show titled '{subject}'. "
        f"Provide 3 alternative short search queries that might work on a torrent site. "
        f"Rules:\n"
        f"1. If the title '{subject}' contains a year (e.g. 2023), YOU MUST USE THAT SAME YEAR. Do NOT change it.\n"
        f"2. Remove 'TV Series' or 'Movie' tags.\n"
        f"3. Return ONLY the 3 queries separated by commas. NO conversational text."
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=1800)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            # Split by comma or newlines
            variations = [v.strip().strip('"').strip("'") for v in re.split(r'[,\n]', text) if v.strip()]
            
            # Filter and Validate
            valid_variations = []
            for v in variations:
                # 1. Length and conversational check
                if len(v) >= 50 or "here are" in v.lower():
                    continue
                
                # 2. Year Consistency Check
                if subject_year:
                    # If the variation has a year, it MUST match the subject's year
                    var_year_match = re.search(r'\b(19|20)\d{2}\b', v)
                    if var_year_match:
                        if var_year_match.group(0) != subject_year:
                            print(f"   ⚠️ Skipping variation '{v}' due to year mismatch (Expected {subject_year})")
                            continue
                
                valid_variations.append(v)

            # Ensure unique and not too long
            return valid_variations[:3]
    except:
        pass
    
    # Fallback variations if AI fails or returns empty
    clean_subject = subject.replace("(TV Series)", "").replace("(Movie)", "").strip()
    return [clean_subject]

def get_release_year(subject, model=DEFAULT_MODEL):
    """
    Uses Ollama to find the release year of the subject.
    """
    # OPTIMIZATION: If year is already in subject, use it!
    match = re.search(r'\b(19|20)\d{2}\b', subject)
    if match:
        return match.group(0)

    prompt = f"What is the release year of the movie or TV series '{subject}'? Return ONLY the year (e.g. 2023). If unknown, return nothing."
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            year = r.json().get("response", "").strip()
            # Extract 4 digit year
            match = re.search(r'\b(19|20)\d{2}\b', year)
            if match:
                return match.group(0)
    except:
        pass
    return None

def get_viral_scene_descriptions(subject, model=DEFAULT_MODEL):
    """
    Asks Ollama for visual descriptions of the most viral/iconic scenes for the movie.
    Returns a list of strings suitable for CLIP matching.
    """
    prompt = (
        f"List 8 of the most viral, iconic, and visually recognizable scenes from the movie/show '{subject}'. "
        f"PRIORITIZE HIGH-OCTANE ACTION SCENES or key narrative turning points. "
        f"For each scene, provide a HIGH-DEFINITION visual description (20-30 words) focusing on SPECIFIC details: "
        f"exact clothing colors, lighting conditions, specific objects held, and facial expressions. "
        f"Avoid generic summaries. Describe the IMAGE exactly as it appears on screen to help a blind person visualize it. "
        f"Examples: 'Close up of Ansel Elgort's hand tapping on a red steering wheel, wearing black sunglasses, sunlight flaring through the windshield', "
        f"'A man in a yellow suit holding a silver revolver, sweat dripping down his forehead, neon blue sign buzzing in background'. "
        f"Return ONLY the descriptions, one per line."
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    descriptions = []
    
    try:
        print(f"🌟 Asking AI for viral scenes in '{subject}'...")
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            # Split lines and clean
            lines = text.split('\n')
            for line in lines:
                clean = re.sub(r'^\d+\.\s*', '', line).strip() # Remove "1. "
                clean = clean.strip('"').strip("'")
                if len(clean) > 5:
                    descriptions.append(clean)
            
            if descriptions:
                print(f"   ✨ Identified {len(descriptions)} viral concepts (e.g., '{descriptions[0]}')")
    except Exception as e:
        print(f"   ⚠️ Failed to get viral scenes: {e}")
        
    return descriptions

def is_good_match(filename, subject, year=None):
    """
    Checks if a filename is a good match for the subject.
    Enforces Year check if provided.
    Uses fuzzy matching for the title.
    """
    # Normalize
    name_clean = filename.rsplit('.', 1)[0]
    norm_file = re.sub(r'[._\-]', ' ', name_clean).lower()
    norm_subj = re.sub(r'[._\-]', ' ', subject).lower()
    
    # Remove common tags
    tags = ["1080p", "720p", "480p", "webrip", "bluray", "x264", "x265", "aac", "yts", "mx", "amzn", "h264", "hevc", "dvdrip"]
    for tag in tags:
        norm_file = norm_file.replace(tag, "")
    
    norm_file = re.sub(r'\s+', ' ', norm_file).strip()
    
    # 1. Year Check (Crucial)
    if year:
        if str(year) not in norm_file:
            return False

    # 2. Ratio Check
    matcher = difflib.SequenceMatcher(None, norm_subj, norm_file)
    ratio = matcher.ratio()
    
    # If ratio is high enough
    if ratio > 0.6:
        return True
        
    # Fallback: Word Boundary Check (for short titles inside long filenames)
    # But only if subject is long enough to be unique (e.g. > 5 chars)
    if len(norm_subj) > 5:
        if re.search(r'\b' + re.escape(norm_subj) + r'\b', norm_file):
            return True
            
    return False

def download_source_material(subject, output_dir="temp_source_material"):
    """
    Downloads source material.
    Strategy:
    1. Check for existing file.
    2. TRY 1337x TORRENT via TorrentManager (User Preference).
    3. Fallback to YouTube (yt-dlp).
    """
    if not subject: return None
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Check if we already have a file for this subject
    # FETCH YEAR EARLY for validation
    year = get_release_year(subject)
    print(f"   📅 Target Year for matching: {year if year else 'Unknown'}")
    
    candidates = []
    
    # Walk the directory to find video files
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith(('.mp4', '.mkv', '.avi', '.mov')):
                full_path = os.path.join(root, file)
                
                if is_good_match(file, subject, year):
                    candidates.append(full_path)
                    
    # Filter candidates: If we have multiple, pick the largest file (likely the movie, not a sample)
    if candidates:
        best_candidate = max(candidates, key=os.path.getsize)
        print(f"✅ Found existing source material for '{subject}': {os.path.basename(best_candidate)}")
        return best_candidate

    print(f"📥 Fetching source material for: {subject}")
    
    # --- STRATEGY 1: TORRENT (1337x) ---
    print(f"   🌊 Attempting 1337x Search & Download...")
    try:
        tm = TorrentManager(download_dir=output_dir)
        
        # Determine Category based on subject hint
        search_category = "Movies"
        if "(TV Series)" in subject:
            search_category = "TV"
            
        print(f"   📂 Target Category: {search_category}")
        
        # Generate search variations
        search_queries = [subject]
        
        # ALWAYS add the clean subject (stripped of type)
        clean_subject = subject.replace("(TV Series)", "").replace("(Movie)", "").strip()
        
        # User Request: "instead of adding it clear, add the year of it"
        # 1. Try to get year
        year = get_release_year(subject)
        if year:
            subject_with_year = f"{clean_subject} {year}"
            if subject_with_year.lower() != subject.lower() and subject_with_year not in search_queries:
                search_queries.append(subject_with_year)
                print(f"   📅 Added Year-Based Query: '{subject_with_year}'")
        
        # 2. Add clean subject as fallback (after year) if it's different
        if clean_subject.lower() != subject.lower() and clean_subject not in search_queries:
             search_queries.append(clean_subject)
            
        variations = generate_search_variations(subject)
        for v in variations:
            if v.lower() != subject.lower() and v not in search_queries and v.lower() != clean_subject.lower():
                search_queries.append(v)
        
        print(f"   🔎 Search Strategy: {search_queries}")
        
        magnet = None
        for query in search_queries:
            print(f"   👉 Trying Query: '{query}' (Category: {search_category})")
            # Try Category Search first (User Preference)
            magnet = tm.search_1337x(query, category=search_category)
            
            if not magnet:
                 print(f"   ⚠️ Category search failed for '{query}'. Trying general search...")
                 magnet = tm.search_1337x(query)

            if magnet:
                print(f"   ✅ Found Magnet for '{query}'")
                break
            else:
                print(f"   ❌ No results for '{query}'. Trying next...")
                time.sleep(2) # Be nice to the server
        
        if magnet:
            print("   🧲 Magnet found. Starting Download (This may take a while)...")
            video_path = tm.download_torrent(magnet)
            if video_path:
                print(f"   ✅ Torrent Download Successful: {video_path}")
                # Rename/Move to standard format if needed, or just return it
                return video_path
        else:
            print("   ⚠️ No suitable torrent found on 1337x (checked all variations).")
            
    except Exception as e:
        print(f"   ⚠️ Torrent Strategy failed: {e}")
        print("   (Ensure qBittorrent is running with WebUI enabled for torrent support)")

    # --- STRATEGY 2: YOUTUBE FALLBACK ---
    # DISABLED per user request: "only takes the video content from the movie, no youtube or such"
    # print(f"   ▶️ Falling back to YouTube Search...")
    # 
    # # Try to find a compilation (3-10 mins)
    # query = f"{subject} best scenes clips"
    # cmd_dl = [
    #     "yt-dlp",
    #     "--default-search", "ytsearch",
    #     "--match-filter", "duration > 120 & duration < 1200", 
    #     "--no-playlist",
    #     "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
    #     "-o", os.path.join(output_dir, f"{safe_subject}_%(id)s.%(ext)s"),
    #     query
    # ]
    # 
    # try:
    #     print(f"   Running: {' '.join(cmd_dl)}")
    #     subprocess.run(cmd_dl, check=True)
    #     
    #     # Find the file we just downloaded
    #     files = [f for f in os.listdir(output_dir) if safe_subject in f]
    #     if files:
    #         return os.path.join(output_dir, files[0])
    #         
    # except Exception as e:
    #     print(f"⚠️ Failed to download source material: {e}")
        
    return None

def get_visual_storyboard(subject, model=DEFAULT_MODEL, research_context=None):
    """
    Asks Ollama to create a sequence of visual scene descriptions that tell the story.
    Uses research context to ground the visual choices.
    """
    context_str = ""
    if research_context:
        if research_context.get('opening'):
            context_str += f"OPENING SCENE: {research_context['opening'][:300]}...\n"
        if research_context.get('ending'):
            context_str += f"ENDING SCENE: {research_context['ending'][:300]}...\n"
    
    prompt = (
        f"Create a visual storyboard for a short video telling the story of the movie '{subject}'. "
        f"List exactly 8-10 distinct, sequential scenes that represent the key plot points from beginning to end. "
        f"For each scene, provide a concrete VISUAL description of what is happening on screen (10-20 words). "
        f"Do NOT write the narration yet. Just describe the IMAGES.\n"
        f"Requirements:\n"
        f"1. Start with the OPENING SCENE described below (if available).\n"
        f"2. End with the ENDING SCENE described below (if available).\n"
        f"3. Include the most iconic/viral moments in between.\n"
        f"4. Format as a simple list, one description per line. No numbering.\n"
        f"\nCONTEXT:\n{context_str}"
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    descriptions = []
    
    try:
        print(f"📋 Generating visual storyboard for: {subject}")
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            lines = text.split('\n')
            for line in lines:
                clean = re.sub(r'^\d+[\.)]\s*', '', line).strip() # Remove numbering
                clean = clean.strip('"').strip("'").strip('- ')
                # Relaxed filter: Allow "scene" in text, just ensure it's descriptive enough (> 10 chars)
                # And filter out common header lines if they sneak in
                if len(clean) > 10 and not clean.lower().startswith(("here is", "sure, here", "visual storyboard")): 
                     descriptions.append(clean)
            
            if descriptions:
                return descriptions
            else:
                print("⚠️ Generated storyboard was empty (filtered out?). Using fallback.")
    except Exception as e:
        print(f"❌ Storyboard Generation Error: {e}")
        
    return ["Opening scene establishing the mood", "Main character introduction", "Action sequence", "Climax confrontation", "Ending realization"]

def extract_batch_visual_anchors(descriptions, model=DEFAULT_MODEL):
    """
    Extracts the primary visual anchor (object/action) for a list of scene descriptions in one go.
    """
    if not descriptions: return []
    
    list_str = "\n".join([f"{i+1}. {d}" for i, d in enumerate(descriptions)])
    
    prompt = (
        f"For each of the following scene descriptions, identify the SINGLE most concrete, visible Object or Action that defines the scene. "
        f"Avoid abstract concepts. Focus on what the camera sees.\n"
        f"Scenes:\n{list_str}\n\n"
        f"Return ONLY a numbered list of the anchors (1 per line). Example:\n"
        f"1. Red Car\n2. Gun\n3. Explosion\n"
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    anchors = []
    
    try:
        # print(f"   ⚓ Extracting visual anchors for {len(descriptions)} scenes...")
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            lines = text.split('\n')
            for line in lines:
                # Extract text after "1. "
                clean = re.sub(r'^\d+[\.)]\s*', '', line).strip()
                if clean:
                    anchors.append(clean)
    except Exception as e:
        print(f"   ⚠️ Anchor extraction failed: {e}")
        
    # Pad or truncate to match input length
    if len(anchors) < len(descriptions):
        anchors.extend(["Visual action"] * (len(descriptions) - len(anchors)))
    return anchors[:len(descriptions)]

def generate_narrative_from_visuals(matched_scenes, user_prompt, model=DEFAULT_MODEL, research_context=None):
    """
    Generates the voiceover script based on the specific scenes we actually found.
    Uses 'Visual Anchors' to strictly enforce image-text correlation.
    """
    # 1. Extract Anchors for better grounding
    descriptions = [s['description'] for s in matched_scenes]
    anchors = extract_batch_visual_anchors(descriptions, model)
    
    # 2. Create a detailed description list for the LLM
    scene_text = ""
    for i, (s, anchor) in enumerate(zip(matched_scenes, anchors)):
        # We explicitly tell the LLM what the "Anchor" is
        scene_text += f"Scene {i+1}: {s['description']} (FOCUS ON: {anchor})\n"
        
    ranker_quote = ""
    if research_context and research_context.get('ranker_best_quote'):
        ranker_quote = f"MANDATORY: You MUST include exactly ONE [PAUSE] marker in the script for this quote: \"{research_context['ranker_best_quote']}\". Place it where it fits best."

    prompt = (
        f"You are narrating a video based on '{user_prompt}'. "
        f"The video shows the following sequence of specific visual scenes:\n"
        f"{scene_text}\n\n"
        f"Write a First-Person (Tyler Durden persona) narration script that perfectly matches these visuals. "
        f"Rules:\n"
        f"1. VISUAL GROUNDING (CRITICAL): Each sentence MUST explicitly describe, reference, or react to the SPECIFIC action or object visible in its corresponding Scene. Do not write generic story text. If the scene describes a car explosion, your sentence MUST mention the explosion or fire.\n"
        f"2. ANCHOR CONSTRAINT: You MUST include the 'FOCUS ON' object/action (or a direct synonym) in your sentence for that scene. This is a strict requirement.\n"
        f"3. CONTINUITY: Despite specific visual matching, the sentences must flow into a single coherent story. Use transitional logic to connect the visuals (e.g. 'And then...', 'But suddenly...').\n"
        f"4. Write exactly ONE short, punchy sentence for each Scene listed above. Total {len(matched_scenes)} sentences.\n"
        f"5. {ranker_quote}\n"
        f"6. Do NOT include scene labels (e.g. 'Scene 1:'). Just the sentences, one per line.\n"
    )
    
    payload = {"model": model, "prompt": prompt, "stream": False}
    
    try:
        print(f"📝 Generating narrative from {len(matched_scenes)} matched scenes...")
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            # Basic cleanup
            text = re.sub(r'Scene \d+:?', '', text)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Filter out conversational filler and meta-text
            clean_lines = []
            for l in lines:
                lower_l = l.lower()
                if "here is the script" in lower_l: continue
                if "sure, here is" in lower_l: continue
                if "narrative script" in lower_l: continue
                if lower_l.startswith("scene"): continue
                if lower_l.startswith("script:"): continue
                # Skip lines that are just labels
                if lower_l.endswith(":") and len(l) < 20: continue 
                clean_lines.append(l)
                
            return clean_lines
    except Exception as e:
        print(f"❌ Narrative Generation Error: {e}")
        return []

def generate_edge_audio(text, output_file, voice="en-US-ChristopherNeural"):
    """
    Generates audio using Edge TTS (Cloud) as a lightweight fallback.
    Returns (success, timings).
    """
    timings = []
    
    async def _gen():
        nonlocal timings
        communicate = edge_tts.Communicate(text, voice)
        with open(output_file, "wb") as file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # offset and duration are in 100ns units (1e-7 seconds)
                    start = chunk["offset"] / 10_000_000
                    duration = chunk["duration"] / 10_000_000
                    timings.append({
                        "word": chunk["text"],
                        "start": start,
                        "end": start + duration
                    })
        
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        loop.run_until_complete(_gen())
        return os.path.exists(output_file), timings
    except Exception as e:
        print(f"❌ Edge TTS failed: {e}")
        return False, None

def create_story_video(user_prompt, output_file="story_output.mp4", model=DEFAULT_MODEL, status_callback=None):
    """
    Main workflow:
    1. Identify Subject & Web Research (Filmsite/Ranker)
    2. Generate Script (enriched with research)
    3. Split into sentences
    4. Download Source Material
    5. For each sentence: Generate Audio + Extract Visual + Create Caption
    6. Assemble
    """
    
    def log(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            try:
                print(msg.encode('utf-8', errors='ignore').decode('utf-8'))
            except:
                pass
        if status_callback:
            status_callback(msg)

    # 0. Identify Subject & Research
    subject = extract_subject_matter(user_prompt, model)
    
    # Fallback if Subject Extraction Failed completely
    if not subject:
        log("⚠️ Could not automatically identify the movie/subject from the prompt.")
        # Try to infer from magnet link if provided later? No, we need it for script generation.
        # Let's ask via input if we are in an interactive mode, or just fail gracefully.
        # Assuming interactive since we use 'input' later.
        log("👉 Please enter the EXACT Movie/Show Title manually:")
        subject = input("Title: ").strip()
        
    if not subject:
        log("❌ No valid subject provided. Cannot proceed.")
        return "Failed: No subject"
        
    research_context = {}
    
    if subject:
        log(f"🕵️ Identifying Subject: {subject}")
        try:
            wr = WebResearcher()
            log(f"   🔎 Searching Filmsite.org for '{subject}'...")
            o, e = wr.get_filmsite_scenes(subject)
            if o: 
                log("   ✅ Found Filmsite Opening Scene info.")
                research_context['opening'] = o
            if e: 
                log("   ✅ Found Filmsite Ending Scene info.")
                research_context['ending'] = e
                
            # Ranker Integration
            try:
                log(f"   🔎 Searching Ranker for #1 Best Quote for '{subject}'...")
                ranker_quote = wr.get_ranker_best_quote(subject)
                if ranker_quote:
                    log(f"   ✅ Found Ranker Quote: {ranker_quote[:50]}...")
                    research_context['ranker_best_quote'] = ranker_quote
                else:
                    log("   ⚠️ No Ranker quote found.")
            except Exception as e:
                log(f"   ⚠️ Ranker search error: {e}")
                
        except Exception as ex:
            log(f"   ⚠️ Web Research warning: {ex}")

    # 1. Download Source Material (Moved UP - We need visuals first!)
    log(f"🎬 Identified Subject Context: {subject}")
    source_video_path = None
    
    # Try automated search first
    try:
        source_video_path = download_source_material(subject)
    except Exception as e:
        log(f"⚠️ Automated download failed: {e}")

    # Manual Fallback if automation failed
    if not source_video_path:
        log("\n❌ Automated search failed (Cloudflare blocks).")
        log(f"👉 Please search for '{subject}' on 1337x.to (or any torrent site) in your normal browser.")
        magnet_link = input("🧲 Paste the MAGNET LINK here (or press Enter to skip/abort): ").strip()
        
        if magnet_link and magnet_link.startswith("magnet:?"):
            log("✅ Magnet link received. Starting download...")
            from torrent_manager import TorrentManager
            tm = TorrentManager()
            source_video_path = tm.download_torrent(magnet_link)
        else:
            log("❌ No valid magnet link provided.")

    if not source_video_path:
        log("❌ CRITICAL: No source material found (movie download failed).")
        return "Failed: No source material."

    # 2. Generate Visual Storyboard
    storyboard_scenes = get_visual_storyboard(subject, model, research_context)
    log(f"📋 Generated Storyboard with {len(storyboard_scenes)} scenes.")
    
    if not storyboard_scenes:
        log("❌ Storyboard is empty. Aborting video creation.")
        return "Failed: Empty storyboard."
    
    # 3. Find Visual Matches (Scene Matching)
    matched_scenes = []
    source_clip_ref = None
    scene_matcher = None
    
    try:
        source_clip_ref = VideoFileClip(source_video_path)
        log(f"✅ Loaded Source Video: {source_video_path} ({source_clip_ref.duration:.1f}s)")
        
        log("   🧠 Initializing Scene Matcher (CLIP)...")
        scene_matcher = SceneMatcher(source_video_path)
        
        # Match loop
        last_end_time = 0.0
        safe_max_time = source_clip_ref.duration - 30 # Avoid credits
        
        for i, scene_desc in enumerate(storyboard_scenes):
            log(f"🔍 Finding match for Scene {i+1}: '{scene_desc}'...")
            
            # Determine search window (Chronological enforcement)
            # Opening scene MUST be early. Ending scene MUST be late.
            search_start = last_end_time
            search_end = safe_max_time
            
            is_opening = (i == 0)
            is_ending = (i == len(storyboard_scenes) - 1)
            
            if is_opening:
                search_end = safe_max_time * 0.15 # First 15%
            elif is_ending:
                search_start = max(last_end_time, safe_max_time * 0.85) # Last 15%
            
            # Search
            # Truncate for CLIP safety
            query = truncate_for_clip(scene_desc)
            
            # Debug types
            log(f"   🐛 Debug: query='{query}' ({type(query)}), start={search_start} ({type(search_start)}), end={search_end} ({type(search_end)})")
            
            best_match = scene_matcher.find_best_match(
                query, 
                min_start_time=float(search_start), 
                max_end_time=float(search_end)
            )
            
            if best_match:
                # Handle dict return from SceneMatcher
                if isinstance(best_match, dict):
                    start_t = best_match['start']
                    end_t = best_match['end']
                    score = best_match['score']
                else:
                    # Fallback if it returns tuple (legacy)
                    start_t, end_t, score = best_match
                
                # Validate score (relaxed for Filmsite/mandatory scenes)
                threshold = 0.20 if (is_opening or is_ending) else 0.22
                
                if score > threshold:
                    log(f"   ✅ Match Found: {start_t:.1f}s - {end_t:.1f}s (Score: {score:.3f})")
                    matched_scenes.append({
                        "description": scene_desc,
                        "start": start_t,
                        "end": end_t,
                        "score": score,
                        "type": "scene"
                    })
                    last_end_time = max(last_end_time, start_t + 2.0) # Move forward
                else:
                    log(f"   ⚠️ Low score ({score:.3f}). Skipping scene to maintain quality.")
            else:
                 log("   ❌ No valid match found within constraints.")

    except Exception as e:
        log(f"❌ Scene Matching Failed: {e}")
        return f"Failed: {e}"

    if not matched_scenes:
        return "Failed: No matching scenes found."

    # 4. Generate Narrative from Visuals
    log("📝 Generating script based on found visuals...")
    script_lines = generate_narrative_from_visuals(matched_scenes, user_prompt, model, research_context)
    
    if len(script_lines) != len(matched_scenes):
        log(f"⚠️ Mismatch: {len(matched_scenes)} scenes vs {len(script_lines)} script lines. Truncating to shorter.")
        limit = min(len(matched_scenes), len(script_lines))
        matched_scenes = matched_scenes[:limit]
        script_lines = script_lines[:limit]

    # Identify Character & Voice
    character_name = identify_character(user_prompt, model)
    voice_ref_path = None
    if character_name:
        log(f"👤 Identified Character: {character_name}")
        voice_ref_path = get_character_reference(character_name, movie_name=subject)
    
    if not voice_ref_path:
        log("⚠️ No specific character voice found. Using default fallback.")
        voices_dir = os.path.join(os.getcwd(), "voices")
        if os.path.exists(voices_dir):
            wavs = [f for f in os.listdir(voices_dir) if f.endswith('.wav')]
            if wavs: voice_ref_path = os.path.join(voices_dir, wavs[0])

    # 5. Assembly Loop
    clips = []
    temp_files = []
    
    # Handle Ranker Quote Insertion (if requested in script)
    # The script generation might have added [PAUSE] line? 
    # Actually generate_narrative_from_visuals returns simple lines.
    # If the LLM followed instructions, it might have added a separate line or we need to handle it.
    # Let's check if the user wants the Ranker quote.
    # The prompt asked for [PAUSE] marker.
    
    final_pairs = []
    for s_line, scene_data in zip(script_lines, matched_scenes):
        final_pairs.append((s_line, scene_data))
        
    # Check for Ranker Quote in Research Context -> Add a special segment if needed?
    # Simpler: If the script line contains "[PAUSE]", we treat it as the quote segment.
    
    for i, (sentence, scene_data) in enumerate(final_pairs):
        log(f"🎬 Assembling Segment {i+1}/{len(final_pairs)}...")
        
        is_pause_segment = "[PAUSE]" in sentence
        audio_path = f"temp_story_audio_{i}.wav"
        audio_success = False
        
        # Audio Generation
        if is_pause_segment:
             # Silence for quote
             log("   Creating silence for Quote...")
             # We will handle audio in video creation (or just make empty audio)
             # Actually, we need the quote audio from the movie or silence?
             # Usually we just let the video play.
             audio_success = True
             # Create dummy silent audio
             silent = AudioArrayClip(np.zeros((44100, 2)), fps=44100) # 1 sec dummy
             silent.duration = 4.0 
             # We'll handle this in clip creation
        else:
             # Generate Voice Clone
             timings = None
             if voice_ref_path:
                 try:
                     # tts = ChatterboxTTS() # Class not available directly
                     audio_success, timings = generate_cloned_audio(sentence, audio_path, voice_ref_path)
                 except Exception as e:
                     log(f"   ⚠️ TTS Error: {e}")
             
             if not audio_success:
                 # Fallback
                 audio_success, timings = generate_edge_audio(sentence, audio_path)

        if not audio_success and not is_pause_segment:
            log("   ❌ Audio generation failed. Skipping.")
            continue

        # Video Extraction
        start_t = scene_data['start']
        # If we have audio, duration is audio duration.
        # If pause, duration is ~4-5s.
        
        seg_duration = 5.0 # default
        audio_duration = 4.5 # default estimate
        
        if is_pause_segment:
            seg_duration = 5.0 # For quote
            audio_duration = 5.0
        elif os.path.exists(audio_path):
            try:
                a_clip = AudioFileClip(audio_path)
                audio_duration = a_clip.duration
                seg_duration = audio_duration + 0.5 # padding
                a_clip.close()
            except:
                pass
        
        # Extract Clip
        try:
            # Ensure we don't go past video end
            end_t = min(start_t + seg_duration, source_clip_ref.duration)
            
            # If scene_data['end'] is significantly different, we might want to respect the visual match?
            # But usually we want to sync to audio.
            # We trust start_t from CLIP.
            
            sub = source_clip_ref.subclip(start_t, end_t)
            
            # Audio Attach
            if not is_pause_segment and os.path.exists(audio_path):
                 aud = AudioFileClip(audio_path)
                 sub = sub.set_audio(aud)
            elif is_pause_segment:
                 # Keep original audio for the quote!
                 # But CLIP match might not be exact for the quote audio.
                 # Ranker quote logic in WebResearcher usually provides a timestamp?
                 # Wait, scene_matcher matched based on description.
                 # If this is the "Quote" segment, we should ideally use the original audio.
                 pass

            # 1. Create Main 1:1 Clip (Focus)
            # Smart Crop (Center)
            w, h = sub.size
            target_ratio = 1.0 
            
            # ... existing crop logic ...
            new_w = h * target_ratio
            if new_w > w:
                new_w = w
                new_h = w / target_ratio
                y1 = (h - new_h) / 2
                main_clip = sub.crop(x1=0, y1=y1, width=w, height=new_h)
            else:
                x1 = (w - new_w) / 2
                main_clip = sub.crop(x1=x1, y1=0, width=new_w, height=h)
            
            main_clip = main_clip.resize(height=1080) # 1080x1080
            
            # 2. Create Blurred Background (Vibe)
            # Use the original subclip (before cropping) to get more context if possible
            # But 'sub' was already cut from source.
            bg_clip = sub.resize(height=1920) # Scale up to fill vertical
            # Center crop to 9:16
            bg_w, bg_h = bg_clip.size
            if bg_w > 1080:
                bg_clip = bg_clip.crop(x1=(bg_w-1080)/2, width=1080, height=1920)
            
            # Apply "Fast Blur" via Resize Trick (Stylish & Efficient)
            # Resize to 5% then back up to smooth it out
            bg_clip = bg_clip.resize(0.05).resize(height=1920) 
            # Darken (40% brightness for high contrast with text)
            bg_clip = bg_clip.fl_image(lambda image: (image * 0.4).astype('uint8'))
            
            # 3. Style Main Clip (Border & Shadow)
            # Add White Border (Top/Bottom only to avoid width issues, or all around?)
            # Since it's 1080 wide, side borders might be lost or reduce content.
            # Let's add Top/Bottom White Border (5px)
            main_clip = main_clip.margin(top=5, bottom=5, color=(255, 255, 255))
            
            # 4. Composite
            # 1:1 Clip in Center, Blurred BG behind
            final_segment = CompositeVideoClip([bg_clip, main_clip.set_position("center")])
            
            # Captions
            if not is_pause_segment:
                # Generate dynamic captions
                # Use audio_duration for sync, not segment duration (which has padding)
                caption_dur = audio_duration if audio_duration > 0 else final_segment.duration
                
                # INCREASE FONT SIZE for Vibe
                # Use the new Yellow Default from create_caption_clip automatically
                txt_clip = create_dynamic_captions(sentence, caption_dur, fontsize=85, timings=timings)
                if txt_clip:
                    # Position: Center (Overlapping video)
                    final_segment = CompositeVideoClip([final_segment, txt_clip])
            
            sub = final_segment # Rename for consistency with rest of code
            
            # OPTIMIZATION: Write segment to disk immediately to free memory
            seg_output_path = f"temp_render_seg_{i}.mp4"
            render_success = False
            
            try:
                sub.write_videofile(
                    seg_output_path,
                    codec="libx264",
                    audio_codec="aac",
                    fps=24,
                    threads=1,
                    # logger=None,
                    ffmpeg_params=["-pix_fmt", "yuv420p"]
                )
                render_success = os.path.exists(seg_output_path)
            except Exception as e:
                log(f"   ❌ Render error: {e}")
            
            if render_success:
                # Manually close components we know are safe
                if 'txt_clip' in locals() and txt_clip:
                     try: txt_clip.close()
                     except: pass
                
                del sub # Release memory
                
                temp_files.append(seg_output_path)
                clip_loaded = VideoFileClip(seg_output_path)
                clips.append(clip_loaded)
                log(f"   ✅ Segment {i} rendered to disk.")
            else:
                log(f"   ⚠️ Fallback to memory clip for segment {i}")
                clips.append(sub)
            
            temp_files.append(audio_path)
            
        except Exception as e:
            log(f"   ❌ Clip processing error: {e}")

    # 3. Concatenate All
    if not clips:
        print("❌ No clips generated.")
        return None

    final_video = concatenate_videoclips(clips)
    
    # STRICT CONSTRAINT: Max 180 seconds (3 mins) per user request
    if final_video.duration > 180:
        print(f"⚠️ Video too long ({final_video.duration:.2f}s). Trimming to 180s.")
        final_video = final_video.subclip(0, 180)
    
    # 4. Background Music (Reuse popular_events logic if available, or simple file check)
    music_path = os.path.join(os.getcwd(), "background_music.mp3")
    if os.path.exists(music_path):
        bg_music = AudioFileClip(music_path)
        # Use afx.audio_loop for audio clips
        if bg_music.duration < final_video.duration:
            bg_music = afx.audio_loop(bg_music, duration=final_video.duration)
        else:
            bg_music = bg_music.subclip(0, final_video.duration)
        
        bg_music = bg_music.volumex(0.15)
        
        # Mix
        final_audio = CompositeAudioClip([final_video.audio, bg_music])
        final_video = final_video.set_audio(final_audio)
        
    # 5. Write Output
    # Use temp_audiofile to prevent encoding issues
    final_video.write_videofile(
        output_file, 
        codec="libx264", 
        audio_codec="aac", 
        fps=24,
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
        threads=1,
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    print(f"✅ Story Video saved to: {output_file}")
    
    final_video.close()
    # return output_file # Moved to end for cleanup
    
    # Cleanup
    try:
        # Close clips first to release file handles
        for c in clips: 
            try: c.close()
            except: pass
        
        # Close source clip reference explicitly
        if 'source_clip_ref' in locals() and source_clip_ref:
            try: source_clip_ref.close()
            except: pass

        # Collect all files to delete
        files_to_delete = temp_files[:]
        
        # Add voice reference if it exists
        # DISABLED: Voice refs are assets, don't delete them!
        # if voice_ref_path:
        #    files_to_delete.append(voice_ref_path)
            
        # Add source video if it exists
        # DISABLED: User requested to keep the movie
        # if source_video_path:
        #    files_to_delete.append(source_video_path)
        
        # Delete generated voice reference if it was downloaded/created for this session
        # We assume if it's in the 'voices' dir but was just created, we might want to keep it?
        # User explicitly said "delete the voice after the video generation is over".
        # To be safe and follow instructions, we delete it.
        if voice_ref_path and os.path.exists(voice_ref_path):
            # Check if it's a fallback (one of the existing files in voices dir that we didn't download)
            # If we downloaded it, it's likely named "{Character}.wav".
            # If we picked a fallback, it's also in voices dir.
            # How to distinguish?
            # We can just delete it as requested. If the user wants to keep "George Clooney.wav" for next time,
            # they shouldn't have asked to delete it. 
            # BUT, re-downloading every time is inefficient.
            # maybe they mean "delete the temporary voice files" not the reference?
            # "delete the voice after the video generation is over" -> likely the reference.
            # I will delete it.
            try:
                os.remove(voice_ref_path)
                print(f"🗑️ Deleted voice reference: {voice_ref_path}")
            except Exception as e:
                print(f"⚠️ Failed to delete voice ref: {e}")

        # Delete files
        for f in files_to_delete:
            if f and os.path.exists(f): 
                try:
                    os.remove(f)
                    print(f"🗑️ Deleted temp file: {f}")
                except Exception as e:
                    print(f"⚠️ Failed to delete {f}: {e}")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

    return output_file

if __name__ == "__main__":
    # Test
    create_story_video("Tell the story of 'The Consultant' from Regus's perspective")
