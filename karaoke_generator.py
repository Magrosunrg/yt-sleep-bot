import sys
import os
import json
import random
import time
import subprocess
import shutil
import re
import difflib
from pathlib import Path

# MoviePy imports with proper fallback
try:
    from moviepy.editor import VideoFileClip, ImageClip, ColorClip, CompositeVideoClip, AudioFileClip, VideoClip, vfx, concatenate_audioclips
    from moviepy.audio.AudioClip import CompositeAudioClip
except ImportError:
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        from moviepy.video.VideoClip import VideoClip, ImageClip, ColorClip
        from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        from moviepy.audio.AudioClip import CompositeAudioClip
        from moviepy.audio.compositing.concatenate import concatenate_audioclips
        import moviepy.video.fx.all as vfx
    except ImportError:
        # Try direct import for MoviePy v2
        from moviepy import VideoFileClip, ImageClip, ColorClip, CompositeVideoClip, AudioFileClip, VideoClip, vfx, concatenate_audioclips
        from moviepy.audio.AudioClip import CompositeAudioClip

from script_generator import ScriptGenerator
from media_manager import MediaManager
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import syncedlyrics
import yt_dlp
import whisper

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "karaoke_song_history.json")

class KaraokeGenerator:
    def __init__(self):
        self.script_gen = ScriptGenerator(use_ollama=True)
        self.api_key = ""
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    self.api_key = json.load(f).get("pexels_key", "")
            except:
                pass
        self.media_mgr = MediaManager(self.api_key)
        self._current_song = None  # For manual song selection

    def set_song(self, title, artist):
        """Manually set a specific song instead of using AI selection."""
        self._current_song = {"title": title, "artist": artist}
        print(f"🎵 Manually set song: {title} by {artist}")

    def get_song(self):
        # If a song was manually set, use it
        if self._current_song:
            return self._current_song
        used_songs = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    used_songs = json.load(f)
            except:
                pass

        # Normalize used songs for comparison
        used_songs_lower = [s.lower() for s in used_songs]

        sys_prompt = "You are a Karaoke DJ. Your job is to pick the most popular, modern, and trending songs."
        genres = ["2020s Pop", "Viral Hits", "TikTok Trends", "Chart Toppers 2024", "Modern Pop", "New Releases", "Global Top 50"]
        genre = random.choice(genres)
        
        # Pass the last 30 songs to the prompt context to avoid immediate repetition suggestions
        user_prompt = f"Suggest ONE modern, trending, and universally popular song from the last 3 years (2022-2025) that is perfect for karaoke. Focus on {genre}. Ensure it is a well-known hit. Return JSON with 'title' and 'artist'. Do not use these: {', '.join(used_songs[-30:])}. Format: {{'title': 'Song Title', 'artist': 'Artist Name'}}"
        
        print(f"🎤 Requesting song suggestion ({genre})...")
        
        for _ in range(3):
            try:
                resp = self.script_gen._generate_ollama(sys_prompt, user_prompt)
                if isinstance(resp, list) and len(resp) > 0: resp = resp[0]
                if isinstance(resp, dict) and "title" in resp:
                    title = resp['title'].strip()
                    artist = resp['artist'].strip()
                    song_id = f"{title} - {artist}"
                    
                    # Robust check: exact match (case-insensitive)
                    if song_id.lower() not in used_songs_lower:
                        print(f"✅ Selected new song: {song_id}")
                        used_songs.append(song_id)
                        with open(HISTORY_FILE, "w") as f:
                            json.dump(used_songs, f)
                        return resp
                    else:
                        print(f"⚠️ Duplicate suggested: {song_id}. Retrying...")
            except Exception as e:
                print(f"Ollama Song Error: {e}")
                time.sleep(1)
                
        return {"title": "Amazing Grace", "artist": "Traditional"}

    def parse_lrc(self, lrc_str):
        """Parses LRC string into list of dicts with 'start' and 'text'."""
        lines = []
        pattern = re.compile(r'\[(\d+):(\d+\.?\d*)\](.*)')
        for line in lrc_str.split('\n'):
            match = pattern.match(line.strip())
            if match:
                minutes, seconds, text = match.groups()
                start_time = int(minutes) * 60 + float(seconds)
                text = text.strip()
                if text: # Skip empty lines
                    lines.append({"start": start_time, "text": text})
        
        # Sort just in case
        lines.sort(key=lambda x: x['start'])
        return lines

    def transcribe_lyrics(self, audio_path):
        """Uses OpenAI Whisper to transcribe lyrics with timestamps."""
        print(f"🎙️ Transcribing lyrics from audio (Whisper AI): {audio_path}...")
        try:
            # Use 'small' model for balance of speed/accuracy.
            # word_timestamps=True enables karaoke-style timing
            model = whisper.load_model("small")
            result = model.transcribe(audio_path, word_timestamps=True)
            segments = result['segments']
            
            lines = []
            for seg in segments:
                text = seg['text'].strip()
                if text:
                    # Extract words if available
                    words = []
                    if 'words' in seg:
                        for w in seg['words']:
                            words.append({
                                "word": w['word'],
                                "start": w['start'],
                                "end": w['end']
                            })
                            
                    lines.append({
                        "start": seg['start'],
                        "end": seg['end'],
                        "text": text,
                        "words": words
                    })
            
            if lines:
                print(f"✅ Whisper transcription successful ({len(lines)} lines).")
                return lines
        except Exception as e:
            print(f"⚠️ Whisper Error: {e}")
            return None

    def calculate_global_offset(self, correct_lines, whisper_lines):
        """Calculates time offset between LRC (correct_lines) and Whisper to fix intro silence."""
        print("⏱️ Calculating Global Offset between LRC and Audio...")
        
        # Flatten words to find anchor matches
        lrc_words = []
        for line in correct_lines:
            words = line['text'].split()
            for w in words:
                clean = re.sub(r'[^\w]', '', w.lower())
                if len(clean) > 2: # Ignore small words for anchoring
                    lrc_words.append({"word": clean, "start": line['start']})

        whisper_words = []
        for line in whisper_lines:
            if 'words' in line:
                for w in line['words']:
                    clean = re.sub(r'[^\w]', '', w['word'].lower())
                    if len(clean) > 2:
                        whisper_words.append({"word": clean, "start": w['start']})
        
        if not lrc_words or not whisper_words:
            return 0.0

        # Use SequenceMatcher to find longest contiguous match
        lrc_clean = [x['word'] for x in lrc_words]
        wh_clean = [x['word'] for x in whisper_words]
        
        matcher = difflib.SequenceMatcher(None, lrc_clean, wh_clean)
        match = matcher.find_longest_match(0, len(lrc_clean), 0, len(wh_clean))
        
        if match.size > 0:
            lrc_anchor = lrc_words[match.a]
            wh_anchor = whisper_words[match.b]
            offset = wh_anchor['start'] - lrc_anchor['start']
            print(f"⏱️ Detected Global Offset: {offset:.2f}s (LRC: {lrc_anchor['start']:.2f}, Audio: {wh_anchor['start']:.2f})")
            return offset
        
        return 0.0

    def align_lyrics(self, correct_lines, whisper_lines):
        """Aligns correct text with Whisper timestamps using Time-Windowed Matching."""
        print("🔄 Aligning Correct Lyrics with Whisper Timestamps (Constrained)...")
        
        # 0. Apply Global Offset Correction
        global_offset = self.calculate_global_offset(correct_lines, whisper_lines)
        if abs(global_offset) > 2.0:
            print(f"⚠️ Applying global offset of {global_offset:.2f}s to LRC timestamps before alignment.")
            for line in correct_lines:
                line['start'] += global_offset
                
        # 1. Flatten Whisper Lyrics into Words
        whisper_words_flat = []
        for line in whisper_lines:
            if 'words' in line:
                for w in line['words']:
                    whisper_words_flat.append({
                        "word": w['word'],
                        "clean": re.sub(r'[^\w]', '', w['word'].lower()),
                        "start": w['start'],
                        "end": w['end']
                    })
            else:
                dur = line['end'] - line['start']
                words = line['text'].split()
                if words:
                    w_dur = dur / len(words)
                    for i, w in enumerate(words):
                        whisper_words_flat.append({
                            "word": w,
                            "clean": re.sub(r'[^\w]', '', w.lower()),
                            "start": line['start'] + i * w_dur,
                            "end": line['start'] + (i + 1) * w_dur
                        })

        aligned_lines = []
        
        # 2. Process Line by Line
        for i, line in enumerate(correct_lines):
            line_words = line['text'].split()
            line_words_objs = []
            
            # Prepare objects for this line's words
            for w in line_words:
                line_words_objs.append({
                    "word": w,
                    "clean": re.sub(r'[^\w]', '', w.lower()),
                    "start": 0,
                    "end": 0,
                    "matched": False
                })
            
            # Determine Time Window
            lrc_start = line['start']
            
            # End is start of next line, or start + 5s default
            lrc_end = correct_lines[i+1]['start'] if i < len(correct_lines)-1 else lrc_start + 5.0
            
            # Search Window: [lrc_start - 1.0, lrc_end + 1.0]
            # We allow small drift, but enforce line boundaries roughly
            window_start = max(0, lrc_start - 1.0)
            window_end = lrc_end + 1.0
            
            # Find candidate Whisper words in this window
            candidates = []
            candidate_indices = [] # Keep track of original indices if needed
            
            for w_idx, w in enumerate(whisper_words_flat):
                # Check overlap: w_start < window_end AND w_end > window_start
                if w['start'] < window_end and w['end'] > window_start:
                    candidates.append(w)
                    candidate_indices.append(w_idx)
            
            # Perform Alignment on this subset
            if candidates and line_words_objs:
                c_clean = [x['clean'] for x in line_words_objs]
                w_clean = [x['clean'] for x in candidates]
                
                matcher = difflib.SequenceMatcher(None, c_clean, w_clean)
                
                for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                    if tag == 'equal':
                        count = min(i2-i1, j2-j1)
                        for k in range(count):
                            c_idx = i1 + k
                            w_cand_idx = j1 + k
                            
                            # Transfer timing
                            line_words_objs[c_idx]['start'] = candidates[w_cand_idx]['start']
                            line_words_objs[c_idx]['end'] = candidates[w_cand_idx]['end']
                            line_words_objs[c_idx]['matched'] = True
            
            # Interpolate Gaps (within the line)
            # Use found matches as anchors.
            # If no matches, use lrc_start/lrc_end distributed.
            
            # First, check if we have ANY matches
            has_matches = any(w['matched'] for w in line_words_objs)
            
            if not has_matches:
                # Fallback: Distribute evenly across [lrc_start, lrc_end]
                dur = lrc_end - lrc_start
                if dur <= 0: dur = 3.0 # Fallback duration
                w_dur = dur / len(line_words_objs)
                for k, w_obj in enumerate(line_words_objs):
                    w_obj['start'] = lrc_start + k * w_dur
                    w_obj['end'] = lrc_start + (k + 1) * w_dur
                    w_obj['matched'] = True # technically "matched" to fallback
            else:
                # Interpolate between matches
                last_end = lrc_start # Start interpolation from line start
                
                for k in range(len(line_words_objs)):
                    if line_words_objs[k]['matched']:
                        last_end = line_words_objs[k]['end']
                    else:
                        # Look ahead for next match
                        next_match = None
                        for m in range(k + 1, len(line_words_objs)):
                            if line_words_objs[m]['matched']:
                                next_match = line_words_objs[m]
                                break
                        
                        gap_start = last_end
                        gap_end = next_match['start'] if next_match else lrc_end # Use line end if no future match
                        
                        # Sanity check: if gap_end < gap_start (bad lrc timing?), fix it
                        if gap_end < gap_start: gap_end = gap_start + 0.5
                        
                        num_unmatched = (m - k) if next_match else (len(line_words_objs) - k)
                        
                        gap_dur = gap_end - gap_start
                        word_dur = gap_dur / num_unmatched if num_unmatched > 0 else 0
                        
                        line_words_objs[k]['start'] = gap_start
                        line_words_objs[k]['end'] = gap_start + word_dur
                        line_words_objs[k]['matched'] = True
                        last_end = line_words_objs[k]['end']

            # Construct the final line object
            aligned_lines.append({
                "text": line['text'],
                "start": line_words_objs[0]['start'] if line_words_objs else lrc_start,
                "end": line_words_objs[-1]['end'] if line_words_objs else lrc_end,
                "words": line_words_objs
            })
            
        # 3. Post-Process: Resolve Overlaps & Enforce Minimum Duration
        # Since we use a single-screen rolling display, Line N must finish before Line N+1 starts.
        print("🔧 Resolving overlaps and enforcing minimum duration...")
        MIN_DURATION = 1.2 # Minimum seconds a line must be visible
        
        for i in range(len(aligned_lines) - 1):
            current_line = aligned_lines[i]
            next_line = aligned_lines[i+1]
            
            # 1. Enforce Minimum Duration for Current Line
            # If current line is too short, extend it, potentially pushing next line
            if current_line['end'] - current_line['start'] < MIN_DURATION:
                current_line['end'] = current_line['start'] + MIN_DURATION
            
            # 2. Resolve Overlap (Push Next Line if needed)
            # If current line ends after next line starts
            if current_line['end'] > next_line['start']:
                overlap = current_line['end'] - next_line['start']
                
                # Decision: Push Next Line Start forward
                # This prioritizes readability of the current line.
                # Only exception: If pushing next line makes it overlap the one after that too much? 
                # The loop will handle that in the next iteration.
                
                next_line['start'] = current_line['end']
                
                # Ensure Next Line has valid end
                if next_line['end'] < next_line['start'] + 0.5:
                    next_line['end'] = next_line['start'] + 0.5
                
                # Re-adjust words for Next Line (shift them if they are now before start)
                # But wait, next line's words are based on audio.
                # If we shift the line start, we should probably keep the words relative?
                # No, just clamp the words to the new start.
                if 'words' in next_line:
                    for w in next_line['words']:
                        if w['start'] < next_line['start']: w['start'] = next_line['start']
                        if w['end'] < next_line['start']: w['end'] = next_line['start'] + 0.1

            # Clamp Words of Current Line (Standard cleanup)
            if 'words' in current_line:
                for w in current_line['words']:
                    if w['end'] > current_line['end']: w['end'] = current_line['end']
                    if w['start'] > current_line['end']: w['start'] = current_line['end']
             
        print(f"✅ Alignment complete. Generated {len(aligned_lines)} aligned lines.")
        return aligned_lines

    def _tag_speakers(self, lines, title, artist):
        """Uses LLM to tag each line with a speaker and gender."""
        print("👥 Analyzing lyrics for speaker identification...")
        
        # Prepare lyrics text
        lyrics_text = ""
        # Limit to first 60 lines to save context/time if song is huge, 
        # but usually we want full structure. Let's try full.
        for i, line in enumerate(lines):
            lyrics_text += f"Line {i}: {line['text']}\n"
            
        sys_prompt = "You are a Karaoke Music Expert. Analyze the lyrics to detect multiple singers (Duets, Features)."
        user_prompt = f"""
Song: {title} by {artist}

Lyrics:
{lyrics_text}

Task:
1. Identify the distinct speakers/singers. Determine their gender (Male/Female).
2. Assign a speaker_id to every line.
3. If it is a solo song, just use one speaker.
4. If it is a duet (e.g. Male/Female), accurately distinguish parts.

Return JSON ONLY:
{{
  "speakers": {{
    "s1": {{"gender": "male", "name": "Singer 1"}},
    "s2": {{"gender": "female", "name": "Singer 2"}}
  }},
  "line_assignments": [
    {{"line": 0, "speaker_id": "s1"}},
    {{"line": 1, "speaker_id": "s2"}}
    ... for all lines
  ]
}}
"""
        try:
            resp = self.script_gen._generate_ollama(sys_prompt, user_prompt)
            # Cleanup json if needed (Ollama sometimes adds markdown)
            if isinstance(resp, str):
                # Try to parse if it returned string
                try:
                    resp = json.loads(resp)
                except:
                    pass
            
            if isinstance(resp, dict) and "speakers" in resp and "line_assignments" in resp:
                speakers = resp["speakers"]
                assignments = {a["line"]: a["speaker_id"] for a in resp["line_assignments"] if "line" in a}
                
                # Tag lines
                for i, line in enumerate(lines):
                    sid = assignments.get(i)
                    if sid and sid in speakers:
                        line["speaker_id"] = sid
                        line["gender"] = speakers[sid].get("gender", "unknown").lower()
                    else:
                        # Default to first speaker
                        first_sid = list(speakers.keys())[0] if speakers else "s1"
                        line["speaker_id"] = first_sid
                        line["gender"] = speakers.get(first_sid, {}).get("gender", "unknown").lower()
                
                print(f"✅ Speaker identification successful. Found {len(speakers)} speakers.")
                return speakers
                
        except Exception as e:
            print(f"⚠️ Speaker identification failed: {e}")
            
        # Fallback: All one speaker
        return {"s1": {"gender": "unknown", "name": "Singer"}}

    def get_lyrics(self, title, artist, audio_path_for_transcription=None):
        """Fetches lyrics. Combines Correct Text (SyncedLyrics) with Perfect Timing (Whisper)."""
        print(f"📝 Fetching lyrics for {title} - {artist}...")
        
        correct_lyrics_lines = None
        whisper_lines = None

        # 1. Fetch Correct Text (SyncedLyrics)
        try:
            print(f"🔍 Searching syncedlyrics (LRC) for Correct Text...")
            lrc = syncedlyrics.search(f"{title} {artist}")
            if lrc:
                correct_lyrics_lines = self.parse_lrc(lrc)
                if correct_lyrics_lines:
                    print(f"✅ Found correct lyrics text ({len(correct_lyrics_lines)} lines).")
        except Exception as e:
            print(f"⚠️ SyncedLyrics search failed: {e}")

        # 2. Fetch Perfect Timing (Whisper)
        if audio_path_for_transcription and os.path.exists(audio_path_for_transcription):
            print("🎙️ Running Whisper for Word-Level Timing...")
            whisper_lines = self.transcribe_lyrics(audio_path_for_transcription)
        
        final_result = None
        
        # 3. Combine / Fallback Logic
        if correct_lyrics_lines and whisper_lines:
            # BEST CASE: We have both. Align them.
            aligned = self.align_lyrics(correct_lyrics_lines, whisper_lines)
            final_result = {"type": "synced", "lines": aligned}
            
        elif whisper_lines:
            # Fallback: Only Whisper (Timing good, Text might be wrong)
            print("⚠️ Could not find official lyrics. Using raw Whisper transcription (Text may vary).")
            final_result = {"type": "synced", "lines": whisper_lines}
            
        elif correct_lyrics_lines:
            # Fallback: Only SyncedLyrics (Text good, Timing might be drift)
            print("⚠️ Could not transcribe audio. Using LRC timing (May have drift).")
            # Generate fake word timings for wipe effect
            for line in correct_lyrics_lines:
                words = line['text'].split()
                dur = 3.0 # Estimate
                if len(words) > 0:
                    w_dur = dur / len(words)
                    line['words'] = []
                    for i, w in enumerate(words):
                        line['words'].append({
                            "word": w,
                            "start": line['start'] + i*w_dur,
                            "end": line['start'] + (i+1)*w_dur
                        })
            final_result = {"type": "synced", "lines": correct_lyrics_lines}

        if final_result:
            # Perform Speaker Detection
            self._tag_speakers(final_result["lines"], title, artist)
            return final_result

        # 4. Total Fallback to Ollama
        print("⚠️ No transcription or synced lyrics available. Falling back to Ollama...")
        sys_prompt = "You are a helpful Karaoke Assistant. Output ONLY valid JSON."
        user_prompt = f"Provide the full lyrics for '{title}' by '{artist}'. Return JSON with key 'lines' (list of strings). No headers."
        
        for _ in range(2):
            try:
                resp = self.script_gen._generate_ollama(sys_prompt, user_prompt)
                if isinstance(resp, dict) and "lines" in resp:
                    return {"type": "unsynced", "lines": resp["lines"]}
            except:
                pass
                
        return {"type": "unsynced", "lines": ["Lyrics not found", "Hum along!"]}

    def download_audio(self, query, output_base="temp_audio"):
        """Downloads audio from YouTube."""
        print(f"🔍 Searching YouTube for: {query}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_base}.%(ext)s',
            'default_search': 'ytsearch',
            'noplaylist': True,
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        # Remove existing
        if os.path.exists(f"{output_base}.mp3"):
            os.remove(f"{output_base}.mp3")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(query, download=True)
                if 'entries' in info:
                    info = info['entries'][0]
                return f"{output_base}.mp3", info['title']
            except Exception as e:
                print(f"YT-DLP Error: {e}")
                return None, None

    def separate_vocals(self, input_file):
        """Uses Demucs to separate vocals."""
        print("🎧 Separating vocals (this may take a while)...")
        try:
            # Use python -m demucs to be safe
            cmd = [sys.executable, "-m", "demucs.separate", "-n", "htdemucs", "--two-stems=vocals", input_file, "-o", "separated_temp"]
            
            subprocess.run(cmd, check=True)
            
            # Find the output
            # Structure: separated_temp/htdemucs/{track_name}/no_vocals.wav
            filename = Path(input_file).stem
            search_path = Path("separated_temp/htdemucs")
            
            # Find the folder (might be slugified)
            found_file = None
            for root, dirs, files in os.walk(search_path):
                if "no_vocals.wav" in files:
                    found_file = os.path.join(root, "no_vocals.wav")
                    break
            
            if found_file:
                return found_file
            else:
                print("⚠️ Demucs finished but output not found.")
                return input_file
                
        except Exception as e:
            print(f"⚠️ Vocal separation failed: {e}")
            return input_file # Fallback to original

    def get_sample_rate(self, file_path):
        """Uses ffprobe to get the sample rate of an audio file."""
        try:
            cmd = [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=sample_rate", "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            rate = int(result.stdout.strip())
            return rate
        except Exception as e:
            print(f"⚠️ Could not detect sample rate: {e}. Defaulting to 44100.")
            return 44100

    def apply_copyright_protection(self, input_file, speed_factor=1.05):
        """
        Applies 'Nightcore-lite' effect: Increases Pitch and Tempo by speed_factor.
        This is the most effective way to evade Content ID without destroying audio quality.
        Uses ffmpeg 'asetrate'.
        """
        print(f"🛡️ Applying Copyright Protection (Speed/Pitch x{speed_factor})...")
        output_file = input_file.replace(".mp3", "_protected.mp3").replace(".wav", "_protected.wav")
        
        rate = self.get_sample_rate(input_file)
        new_rate = int(rate * speed_factor)
        
        # asetrate changes playback rate (Pitch + Tempo)
        # aresample restores the sample rate metadata so players play it correctly
        filter_str = f"asetrate={new_rate},aresample={rate}"
        
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", input_file, "-filter:a", filter_str, output_file
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(output_file):
                print(f"✅ Audio protection applied: {output_file}")
                return output_file
        except Exception as e:
            print(f"⚠️ Audio protection failed: {e}")
            
        return input_file

    def _make_text_img_core(self, txt, size=110, color="white", highlight=False):
        """Core function that returns image and text bounds."""
        # Create larger canvas for shadows/glow
        img = Image.new('RGBA', (1920, 1080), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            font_path = "arialbd.ttf" # Use Bold font for readability
            if not os.path.exists(font_path):
                font_path = "C:/Windows/Fonts/arialbd.ttf"
            font = ImageFont.truetype(font_path, size)
        except:
            font = ImageFont.load_default()
        
        # Word wrapping (basic)
        max_width = 1800 # Wider margin
        
        # Respect explicit newlines
        raw_lines = txt.split('\n')
        lines = []
        
        for raw_line in raw_lines:
            words = raw_line.split(' ')
            current_line = []
            
            for word in words:
                current_line.append(word)
                bbox = draw.textbbox((0, 0), " ".join(current_line), font=font)
                if bbox[2] - bbox[0] > max_width:
                    current_line.pop()
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
        
        total_h = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            h = bbox[3] - bbox[1] + 20
            line_heights.append(h)
            total_h += h
        
        y = (1080 - total_h) / 2
        
        text_color = color
        
        # Draw background box for better readability
        box_padding = 20
        # Calculate actual max width of lines
        actual_max_w = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            if (bbox[2] - bbox[0]) > actual_max_w: actual_max_w = bbox[2] - bbox[0]
            
        box_x1 = int((1920 - actual_max_w) / 2 - box_padding)
        box_x2 = int((1920 + actual_max_w) / 2 + box_padding)
        box_y1 = int(y - box_padding)
        box_y2 = int(y + total_h + box_padding)
        
        # Semi-transparent black box
        draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(0, 0, 0, 100))

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            x = (1920 - w) / 2
            
            # Heavy Stroke (Black Outline)
            stroke_width = 4
            for off_x in range(-stroke_width, stroke_width+1):
                for off_y in range(-stroke_width, stroke_width+1):
                     draw.text((x+off_x, y+off_y), line, font=font, fill="black")
            
            # Text
            draw.text((x, y), line, font=font, fill=text_color)
            y += line_heights[i]
            
        return np.array(img), (box_x1, box_x2)

    def make_text_img(self, txt, size=80, color="white", highlight=False):
        img, _ = self._make_text_img_core(txt, size, color, highlight)
        return img

    def _make_multi_line_img(self, lines, active_idx=0, size=60, active_color="cyan", done_color="cyan", future_color="white", line_colors=None):
        """Generates an image with multiple lines, highlighting the active one."""
        img = Image.new('RGBA', (1920, 1080), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        
        try:
            font_path = "arial.ttf"
            if not os.path.exists(font_path):
                font_path = "C:/Windows/Fonts/arial.ttf"
            font = ImageFont.truetype(font_path, size)
        except:
            font = ImageFont.load_default()

        # Calculate heights and layout
        line_heights = []
        total_h = 0
        max_w = 0
        
        # Measure all lines
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            # Ensure safe width for 1920p (with padding)
            if w > 1800:
                # Force scale down font for this batch if it's too wide
                # Or just accept it (for now, assume reasonable length)
                pass
            h = bbox[3] - bbox[1] + 25 # Increased padding
            if w > max_w: max_w = w
            line_heights.append(h)
            total_h += h
            
        y = (1080 - total_h) / 2
        
        # Background Box
        box_padding = 40
        box_x1 = int((1920 - max_w) / 2 - box_padding)
        box_x2 = int((1920 + max_w) / 2 + box_padding)
        box_y1 = int(y - box_padding)
        box_y2 = int(y + total_h + box_padding)
        
        # Semi-transparent black box
        draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(0, 0, 0, 140))
        
        active_bounds = (0, 0)
        
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            x = (1920 - w) / 2
            
            # Determine Color
            if line_colors:
                fill_color = line_colors[i]
                if i == active_idx:
                    active_bounds = (x, x + w)
            else:
                fill_color = future_color
                if i < active_idx:
                    fill_color = done_color
                elif i == active_idx:
                    fill_color = active_color
                    active_bounds = (x, x + w)
            
            # Heavy Stroke (Black Outline)
            stroke_width = 4
            for off_x in range(-stroke_width, stroke_width+1):
                for off_y in range(-stroke_width, stroke_width+1):
                     draw.text((x+off_x, y+off_y), line, font=font, fill="black")
            
            # Text
            draw.text((x, y), line, font=font, fill=fill_color)
            y += line_heights[i]
            
        return np.array(img), active_bounds

    def create_rolling_wipe_clip(self, lines_group, active_idx, duration, start_time, word_timings=None, line_colors=None, total_duration=None):
        """Creates a wipe clip for a group of lines. Supports word-level timing."""
        
        # Use total_duration for the clip length if provided, else default to wipe duration
        clip_duration = total_duration if total_duration else duration

        # Prepare colors if provided
        colors_inactive = None
        colors_active = None
        
        if line_colors:
            colors_active = list(line_colors)
            colors_inactive = list(line_colors)
            # Inactive state: Current line should be white (not yet sung)
            colors_inactive[active_idx] = "white"
        
        # 1. Inactive State
        img_inactive, bounds = self._make_multi_line_img(lines_group, active_idx, size=60, 
                                                         active_color="white", done_color="cyan", future_color="white",
                                                         line_colors=colors_inactive)
        
        # 2. Active State
        img_active, _ = self._make_multi_line_img(lines_group, active_idx, size=60, 
                                                  active_color="cyan", done_color="cyan", future_color="white",
                                                  line_colors=colors_active)
        
        x1, x2 = bounds
        
        # Pre-calculate word spans if timings are available
        word_spans = []
        if word_timings:
            try:
                font_path = "arial.ttf"
                if not os.path.exists(font_path): font_path = "C:/Windows/Fonts/arial.ttf"
                font = ImageFont.truetype(font_path, 60)
                draw = ImageDraw.Draw(Image.new('L', (1,1)))
                
                # Improved Logic: Match Whisper words to actual Display Text to account for punctuation/spaces
                full_line_text = lines_group[active_idx]
                full_line_lower = full_line_text.lower()
                search_start_idx = 0
                last_measured_width = 0
                cumulative_text_fallback = ""
                
                last_span_end_time = 0.0
                last_span_x_end = 0.0

                for w_data in word_timings:
                    word_str = w_data['word']
                    w_start = w_data['start'] - start_time
                    w_end = w_data['end'] - start_time
                    
                    clean_word = word_str.strip()
                    
                    match_idx = -1
                    if clean_word:
                        # Search for word in the remaining part of the line
                        match_idx = full_line_lower.find(clean_word.lower(), search_start_idx)
                    
                    # If found and not skipping too much text (e.g. < 15 chars), accept it
                    if match_idx != -1 and (match_idx - search_start_idx) < 15:
                        
                        # Calculate Text Width UP TO this word (to catch skipped text/spaces)
                        text_before_word = full_line_text[:match_idx]
                        bbox_before = draw.textbbox((0, 0), text_before_word, font=font)
                        x_start_actual = bbox_before[2] - bbox_before[0]
                        
                        # Calculate Text Width INCLUDING this word
                        end_char_idx = match_idx + len(clean_word)
                        measured_text = full_line_text[:end_char_idx] 
                        
                        bbox = draw.textbbox((0, 0), measured_text, font=font)
                        current_total_w = bbox[2] - bbox[0]
                        
                        search_start_idx = end_char_idx
                        cumulative_text_fallback = measured_text
                        
                        target_x_start = x1 + x_start_actual
                        target_x_end = x1 + current_total_w
                        
                    else:
                        # Fallback: Just accumulate the Whisper word
                        cumulative_text_fallback += word_str
                        bbox = draw.textbbox((0, 0), cumulative_text_fallback, font=font)
                        current_total_w = bbox[2] - bbox[0]
                        
                        target_x_end = x1 + current_total_w
                        target_x_start = x1 + last_measured_width # Fallback uses accumulation

                    # --- GAP FILLING LOGIC ---
                    # If we skipped visual text (x_start > last_x_end), we need to wipe it.
                    # We usually do this during the silence between the last word and this one.
                    # But if audio is contiguous, we do it instantly (jump).
                    
                    if target_x_start > (x1 + last_span_x_end) + 2: # +2px tolerance
                        # We have a visual gap (e.g. space or skipped word)
                        # Create a "Gap Span" that covers the time from last_end to w_start
                        
                        gap_start_time = last_span_end_time
                        gap_end_time = w_start
                        
                        # Ensure monotonic time
                        if gap_end_time < gap_start_time: gap_end_time = gap_start_time
                        
                        # Add Gap Span
                        word_spans.append({
                            'start': gap_start_time,
                            'end': gap_end_time,
                            'x_start': x1 + last_span_x_end,
                            'x_end': target_x_start,
                            'type': 'gap'
                        })
                    
                    # Add Word Span
                    word_spans.append({
                        'start': w_start,
                        'end': w_end,
                        'x_start': target_x_start,
                        'x_end': target_x_end,
                        'type': 'word'
                    })
                    
                    last_measured_width = current_total_w
                    
                    # Update tracking for next iteration
                    # Note: last_measured_width is relative to 0. 
                    # last_span_x_end should be relative to 0 too (without x1)
                    last_span_x_end = current_total_w
                    last_span_end_time = w_end

            except:
                pass

        # Create a constant mask from the inactive image (since text position doesn't change)
        mask_data = img_inactive[:,:,3] / 255.0
        mask_clip = ImageClip(mask_data, ismask=True, duration=clip_duration)

        def make_frame_rgb(t):
            wipe_x = x1
            
            if word_spans:
                # Find which span t is in
                found_active = False
                for span in word_spans:
                    if t < span['start']:
                        # In silence before this word
                        # Stay at previous word end (which is this span's start_x)
                        wipe_x = span['x_start']
                        found_active = True
                        break
                    
                    if span['start'] <= t <= span['end']:
                        # Inside word - interpolate
                        dur = span['end'] - span['start']
                        if dur > 0:
                            p = (t - span['start']) / dur
                            wipe_x = int(span['x_start'] + (span['x_end'] - span['x_start']) * p)
                        else:
                            wipe_x = span['x_end']
                        found_active = True
                        break
                    
                    # Past this word, ensure we hold at its end
                    wipe_x = span['x_end']
                
                # If loop finishes and not found_active, we are past the last word -> keep max wipe
                pass
            else:
                # Linear fallback
                progress = t / duration if duration > 0 else 1
                if progress > 1: progress = 1
                wipe_x = int(x1 + (x2 - x1) * progress)
            
            # Draw
            frame = img_inactive.copy()
            wipe_x = int(wipe_x)
            if wipe_x > 0:
                if wipe_x > frame.shape[1]: wipe_x = frame.shape[1]
                frame[:, :wipe_x] = img_active[:, :wipe_x]
            
            return frame[:,:,:3] # Return RGB only

        return VideoClip(make_frame_rgb, duration=clip_duration).set_mask(mask_clip).set_start(start_time).set_position("center")

    def create_wipe_clip(self, txt, duration, start_time):
        """Creates a VideoClip with a karaoke wipe effect."""
        # 1. Generate Inactive (Future) Image - White
        img_inactive, bounds = self._make_text_img_core(txt, 80, "white")
        
        # 2. Generate Active (Past) Image - Blue (Cyan)
        img_active, _ = self._make_text_img_core(txt, 80, "cyan") # User requested blue-ish
        
        x1, x2 = bounds
        
        # 3. Define the frame generator
        def make_frame(t):
            # Progress 0..1
            progress = t / duration if duration > 0 else 1
            if progress > 1: progress = 1
            
            # Calculate wipe position
            # Wipe moves from x1 to x2
            wipe_x = int(x1 + (x2 - x1) * progress)
            
            # Start with inactive base
            frame = img_inactive.copy()
            
            # Apply active part (slice)
            # Ensure indices are valid
            if wipe_x > 0:
                frame[:, :wipe_x] = img_active[:, :wipe_x]
                
            return frame

        # Return VideoClip
        return VideoClip(make_frame, duration=duration).set_start(start_time).set_position("center")


    def generate_thumbnail(self, title, artist, output_path="thumbnail.jpg"):
        """Generates a viral-style thumbnail with MASSIVE text and High Contrast."""
        print("🖼️ Generating Viral Thumbnail...")
        img = Image.new('RGB', (1280, 720), color=(10, 10, 10)) # Dark Grey Background
        draw = ImageDraw.Draw(img)
        
        # Load Fonts
        try:
            font_path = "impact.ttf" 
            if not os.path.exists(font_path): font_path = "C:/Windows/Fonts/impact.ttf"
            if not os.path.exists(font_path): font_path = "C:/Windows/Fonts/arialbd.ttf"
            
            title_font_size = 140
            artist_font_size = 80
            badge_font_size = 70
            
            title_font = ImageFont.truetype(font_path, title_font_size)
            artist_font = ImageFont.truetype(font_path, artist_font_size)
            badge_font = ImageFont.truetype(font_path, badge_font_size)
        except:
            title_font = ImageFont.load_default()
            artist_font = ImageFont.load_default()
            badge_font = ImageFont.load_default()
            
        # 1. Background Pattern (Subtle Stripes)
        for i in range(0, 1280, 40):
            draw.line([(i, 0), (i, 720)], fill=(20, 20, 20), width=2)

        # 2. Top Banner: "OFFICIAL KARAOKE" (Yellow)
        draw.rectangle([0, 0, 1280, 140], fill="#FFD700")
        draw.text((640, 70), "KARAOKE VERSION", font=badge_font, fill="black", anchor="mm")
        
        # 3. Center: Song Title (Massive, White with Red Glow/Stroke)
        # Handle Multi-line
        text = title.upper()
        lines = []
        if len(text) > 12:
            words = text.split()
            mid = len(words)//2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            lines = [text]
            
        y_start = 300 if len(lines) == 1 else 250
        line_height = 130
        
        for i, line in enumerate(lines):
            y = y_start + (i * line_height)
            # Thick Red Stroke
            stroke_width = 8
            for adj_x in range(-stroke_width, stroke_width+1):
                for adj_y in range(-stroke_width, stroke_width+1):
                    draw.text((640+adj_x, y+adj_y), line, font=title_font, fill="#FF0000", anchor="mm")
            # White Text
            draw.text((640, y), line, font=title_font, fill="white", anchor="mm")

        # 4. Bottom Info: Artist & Badges
        # Artist Name (Cyan)
        draw.text((640, 500), f"by {artist}", font=artist_font, fill="#00FFFF", anchor="mm")
        
        # 5. Viral Badges (Left & Right)
        # Left: "LYRICS" (Red Box)
        draw.rectangle([50, 580, 350, 680], fill="#FF0000", outline="white", width=4)
        draw.text((200, 630), "LYRICS", font=badge_font, fill="white", anchor="mm")
        
        # Right: "LOWER KEY" or "HD AUDIO" (Green Box)
        draw.rectangle([930, 580, 1230, 680], fill="#00FF00", outline="white", width=4)
        draw.text((1080, 630), "HD AUDIO", font=badge_font, fill="black", anchor="mm")
        
        # 6. Border (Neon Purple)
        draw.rectangle([0, 0, 1279, 719], outline="#9900FF", width=15)
        
        img.save(output_path)
        print(f"✅ Viral Thumbnail saved to {output_path}")
        return output_path

    def create_countdown_clip(self, duration=3.0, start_time=0):
        """Creates a 3-2-1 countdown clip."""
        clips = []
        # 3... 2... 1...
        for i in range(3, 0, -1):
            txt_img = self.make_text_img(str(i), size=200, color="yellow")
            clip = ImageClip(txt_img).set_duration(1.0).set_start(start_time + (3-i)).set_position("center")
            clips.append(clip)
        return clips

    def create_video(self, output_path):
        song = self.get_song()
        title = song.get("title", "Unknown")
        artist = song.get("artist", "Unknown")
        print(f"🎤 Selected Song: {title} by {artist}")
        
        # 1. Get Audio (Single Source + Separation for Perfect Sync)
        print("🔍 Searching for audio source...")
        audio_file = None
        vocals_file = None
        
        # Always use Official Audio as the single source of truth.
        # This ensures the instrumental and the lyrics (transcribed from vocals) share the EXACT same timeline.
        # We then use Demucs to split them. This solves both "vocal leakage" and "sync issues".
        orig_path, _ = self.download_audio(f"{title} {artist} Official Audio", "temp_original")
        
        if orig_path and os.path.exists(orig_path):
            print("🎧 Processing audio for karaoke (Vocal Separation)...")
            # separate_vocals returns path to 'no_vocals.wav'
            audio_file = self.separate_vocals(orig_path)
            
            if "no_vocals.wav" in audio_file and os.path.exists(audio_file):
                print("✅ Vocal separation successful.")
                # The vocals file should be in the same directory
                possible_vocals = audio_file.replace("no_vocals.wav", "vocals.wav")
                if os.path.exists(possible_vocals):
                    vocals_file = possible_vocals
                    print("✅ Found isolated vocals for transcription.")
                else:
                    print("⚠️ Isolated vocals not found, using original for transcription.")
                    vocals_file = orig_path
            else:
                print("⚠️ Separation failed or returned original. Vocals may remain.")
                vocals_file = orig_path
                audio_file = orig_path
        
        if not audio_file or not os.path.exists(audio_file):
            print("❌ Failed to prepare audio.")
            return None

        # 2. Get Lyrics (Pass vocals_file for transcription)
        # We pass vocals_file so get_lyrics prioritizes transcribing it.
        lyrics_data = self.get_lyrics(title, artist, audio_path_for_transcription=vocals_file)
        
        # ADDED: Intro Duration Logic
        INTRO_DURATION = 15.0
        
        # NEW: Audio Trimming Logic
        # If lyrics start very late (e.g. > 20s), trim the audio intro so vocals start closer to INTRO_DURATION
        if lyrics_data["type"] == "synced" and lyrics_data["lines"]:
            first_line_start = lyrics_data["lines"][0]['start']
            
            # If vocals start more than 20s in, trim it down so they start at ~5s
            # (giving 5s of instrumental before vocals, plus 15s INTRO_DURATION = 20s total wait for viewer)
            if first_line_start > 20.0:
                trim_amount = first_line_start - 5.0
                print(f"✂️ Detected long intro ({first_line_start:.2f}s). Trimming {trim_amount:.2f}s from audio...")
                
                # Trim Audio File using ffmpeg for precision
                trimmed_audio = "trimmed_audio.wav"
                try:
                    subprocess.run([
                        "ffmpeg", "-y", "-ss", str(trim_amount), "-i", audio_file, 
                        "-c", "copy", trimmed_audio
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    if os.path.exists(trimmed_audio):
                        audio_file = trimmed_audio
                        # Update Lyric Timestamps
                        print("⏱️ Shifting lyric timestamps after trim...")
                        for line in lyrics_data["lines"]:
                            line["start"] = max(0, line["start"] - trim_amount)
                            line["end"] = max(0, line["end"] - trim_amount)
                            if "words" in line:
                                for w in line["words"]:
                                    w["start"] = max(0, w["start"] - trim_amount)
                                    w["end"] = max(0, w["end"] - trim_amount)
                    else:
                        print("⚠️ Trimming failed, file not created.")
                except Exception as e:
                    print(f"⚠️ Trimming failed: {e}")

        # NEW: Apply Copyright Protection (Speed/Pitch Shift)
        # We do this AFTER trimming but BEFORE shifting for intro.
        # This changes the DURATION of the audio, so we must scale timestamps.
        SPEED_FACTOR = 1.05 # 5% faster
        
        protected_audio = self.apply_copyright_protection(audio_file, speed_factor=SPEED_FACTOR)
        if protected_audio != audio_file:
            audio_file = protected_audio
            print(f"⏱️ Scaling lyric timestamps by {SPEED_FACTOR} (Copyright Protection)...")
            
            # Divide all timestamps by speed factor (since audio is faster, events happen sooner)
            if lyrics_data["lines"]:
                for line in lyrics_data["lines"]:
                    line["start"] /= SPEED_FACTOR
                    line["end"] /= SPEED_FACTOR
                    if "words" in line:
                        for w in line["words"]:
                            w["start"] /= SPEED_FACTOR
                            w["end"] /= SPEED_FACTOR

        # Shift Lyrics if synced
        if lyrics_data["type"] == "synced":
            print(f"⏱️ Shifting lyrics by {INTRO_DURATION}s for intro...")
            for line in lyrics_data["lines"]:
                line["start"] += INTRO_DURATION
                line["end"] += INTRO_DURATION
                if "words" in line:
                    for w in line["words"]:
                        w["start"] += INTRO_DURATION
                        w["end"] += INTRO_DURATION
        
        # 3. Get Visuals
        bg_query = f"neon {random.choice(['lights', 'tunnel', 'retro', 'stage'])} loop"
        bg_data = self.media_mgr.search_video(bg_query, orientation="landscape")
        bg_clip = None
        if bg_data:
            bg_file = "temp_karaoke_bg.mp4"
            if self.media_mgr.download_file(bg_data['url'], bg_file):
                try:
                    bg_clip = VideoFileClip(bg_file).without_audio().resize(newsize=(1920, 1080))
                except:
                    pass
        if not bg_clip:
            bg_clip = ColorClip(size=(1920, 1080), color=(0, 0, 30), duration=10)

        # 4. Build Clips
        clips = []
        
        # --- DYNAMIC RETENTION INTRO ---
        # 0s - 5s: SONG TITLE (Massive)
        # 5s - 9s: ARTIST (Medium)
        # 9s - 12s: GET READY (Pulse)
        # 12s - 15s: COUNTDOWN (3..2..1)
        
        intro_dur_title = 5.0
        intro_dur_artist = 4.0
        intro_dur_ready = 3.0
        
        # 1. Title Clip (Massive)
        title_img = self.make_text_img(title.upper(), 130, "yellow")
        clips.append(ImageClip(title_img).set_duration(intro_dur_title).set_start(0).set_position("center"))
        
        # 2. Artist Clip
        artist_img = self.make_text_img(f"by {artist}", 90, "cyan")
        clips.append(ImageClip(artist_img).set_duration(intro_dur_artist).set_start(intro_dur_title).set_position("center"))
        
        # 3. Get Ready
        ready_img = self.make_text_img("GET READY TO SING!", 100, "white")
        clips.append(ImageClip(ready_img).set_duration(intro_dur_ready).set_start(intro_dur_title + intro_dur_artist).set_position("center"))
        
        # Intro Progress Bar (Singing Starts in...)
        # A small bar that fills up during the 15s intro
        def make_intro_bar_core(t):
            bar_w = int(600 * (t / INTRO_DURATION))
            img = Image.new('RGBA', (600, 20), (50, 50, 50, 200))
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, bar_w, 20], fill="lime")
            return np.array(img)
            
        def make_intro_bar_rgb(t):
            return make_intro_bar_core(t)[:,:,:3]

        def make_intro_bar_mask(t):
            return make_intro_bar_core(t)[:,:,3] / 255.0
            
        intro_bar_mask = VideoClip(make_intro_bar_mask, duration=INTRO_DURATION, ismask=True)
        intro_bar = VideoClip(make_intro_bar_rgb, duration=INTRO_DURATION).set_mask(intro_bar_mask).set_position(("center", 800))
        clips.append(intro_bar)
        
        # Countdown (Last 3 seconds of Intro)
        countdown_clips = self.create_countdown_clip(start_time=INTRO_DURATION - 3.0)
        clips.extend(countdown_clips)
        
        current_time = INTRO_DURATION
        
        if lyrics_data["type"] == "synced":
            lines = lyrics_data["lines"]
            
            # --- Speaker Color Logic ---
            speaker_ids = set()
            speaker_genders = {}
            
            for line in lines:
                sid = line.get("speaker_id", "s1")
                gen = line.get("gender", "unknown")
                speaker_ids.add(sid)
                speaker_genders[sid] = gen
            
            # Sort speakers for consistency
            sorted_speakers = sorted(list(speaker_ids))
            
            # Determine Color Map
            color_map = {}
            
            # Check demographics
            has_male = any("male" in g for g in speaker_genders.values() if g != "female")
            has_female = any("female" in g for g in speaker_genders.values())
            
            males = [s for s in sorted_speakers if "male" in speaker_genders[s] and "female" not in speaker_genders[s]]
            females = [s for s in sorted_speakers if "female" in speaker_genders[s]]
            others = [s for s in sorted_speakers if s not in males and s not in females]
            
            # Assign Colors
            # Strategy:
            # If Male & Female: Male->Blue, Female->Pink
            # If Multiple Males: M1->Blue, M2->Cyan
            # If Multiple Females: F1->Pink, F2->Purple
            
            # Males
            if len(males) == 1:
                color_map[males[0]] = "#00BFFF" # Deep Sky Blue
            elif len(males) > 1:
                palette = ["#00BFFF", "#00FFFF", "#1E90FF", "#4682B4"]
                for i, s in enumerate(males):
                    color_map[s] = palette[i % len(palette)]
            
            # Females
            if len(females) == 1:
                color_map[females[0]] = "#FF69B4" # Hot Pink
            elif len(females) > 1:
                palette = ["#FF69B4", "#FF1493", "#DA70D6", "#FF00FF"]
                for i, s in enumerate(females):
                    color_map[s] = palette[i % len(palette)]
            
            # Others (Unknown)
            other_palette = ["#00FF00", "#FFFF00", "#FFA500"] # Green, Yellow, Orange
            for i, s in enumerate(others):
                # If solo and unknown, default to Cyan
                if len(sorted_speakers) == 1:
                    color_map[s] = "cyan"
                else:
                    color_map[s] = other_palette[i % len(other_palette)]
            
            print(f"🎨 Speaker Colors: {color_map}")
            
            # Process in Groups of 3 (Pages)
            # 1. Chunk lines into pages of 3
            # 2. For each page, display all lines in that page, highlighting one by one.
            # 3. Transition to next page occurs naturally when last line of page finishes.
            
            for i in range(0, len(lines), 3):
                # Define Page Content
                page_lines = lines[i : i+3]
                page_text_lines = [l["text"] for l in page_lines]
                
                # Determine colors for this page
                page_colors = []
                for l in page_lines:
                    sid = l.get("speaker_id", "s1")
                    page_colors.append(color_map.get(sid, "white"))
                
                # Iterate through lines within this page
                for j, line in enumerate(page_lines):
                    txt = line["text"]
                    start = line["start"]
                    end = line["end"]
                    duration = end - start
                    
                    # Safety cap
                    if duration > 15: duration = 15
                    if duration < 0.1: duration = 0.1
                    
                    word_timings = line.get("words", None)
                    
                    # Calculate total_duration to fill gap to next line/page
                    total_duration = duration
                    
                    if j < len(page_lines) - 1:
                        # Gap to next line in same page
                        next_start = page_lines[j+1]["start"]
                        gap = next_start - end
                        if gap > 0:
                            total_duration += gap
                    else:
                        # Last line of page. Gap to start of NEXT page?
                        next_page_idx = i + 3
                        if next_page_idx < len(lines):
                            next_page_start = lines[next_page_idx]["start"]
                            gap = next_page_start - end
                            if gap > 0:
                                total_duration += gap
                    
                    # Create Clip for this line (j is index within page)
                    # We pass the WHOLE page text, but highlight index j
                    clip = self.create_rolling_wipe_clip(page_text_lines, j, duration, start, 
                                                         word_timings=word_timings,
                                                         line_colors=page_colors,
                                                         total_duration=total_duration)
                    clips.append(clip)
                
        else:
            # Unsynced fallback
            lines = lyrics_data["lines"]
            
            # Estimate audio duration to spread lyrics
            try:
                temp_audio = AudioFileClip(audio_file)
                audio_dur = temp_audio.duration
                temp_audio.close()
            except:
                audio_dur = 180

            # Calculate chunk duration
            num_chunks = (len(lines) + 2) // 3
            if num_chunks > 0:
                chunk_dur = audio_dur / num_chunks
            else:
                chunk_dur = 6
            
            if chunk_dur < 4: chunk_dur = 4
            
            for i in range(0, len(lines), 3):
                chunk = "\n".join(lines[i:i+3])
                img = self.make_text_img(chunk, 80, "white")
                txt_clip = ImageClip(img).set_start(current_time).set_duration(chunk_dur).set_position("center")
                clips.append(txt_clip)
                current_time += chunk_dur

        # Load Audio
        audio_clip = AudioFileClip(audio_file).set_start(INTRO_DURATION)
        total_dur = audio_clip.duration + INTRO_DURATION
        
        # Ensure Audio is properly composited with silence at start
        # CompositeAudioClip respects the start time of its components
        final_audio = CompositeAudioClip([audio_clip])
        
        # Loop BG
        final_bg = bg_clip.loop(duration=total_dur)
        
        # Progress Bar (Red line at bottom)
        progress_bar = ColorClip(size=(1920, 15), color=(255, 0, 0)).set_duration(total_dur)
        progress_bar = progress_bar.set_position(lambda t: (-1920 + (1920 * t / total_dur), 1065))
        
        # Call to Action (End Screen Overlay) - Last 10 seconds
        cta_img = self.make_text_img("SUBSCRIBE FOR MORE KARAOKE!", size=90, color="yellow")
        cta_clip = ImageClip(cta_img).set_duration(10).set_start(total_dur - 10).set_position(("center", 200)) # Top area
        
        # Composite
        final = CompositeVideoClip([final_bg] + clips + [progress_bar, cta_clip])
        final = final.set_audio(final_audio)
        
        print(f"💾 Rendering to {output_path}...")
        try:
            final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", ffmpeg_params=["-pix_fmt", "yuv420p"])
        finally:
            # Cleanup resources to prevent WinError 6
            try:
                final.close()
                audio_clip.close()
                final_audio.close()
                if bg_clip: bg_clip.close()
            except:
                pass
        
        # Cleanup Files
        try:
            if os.path.exists("separated_temp"):
                shutil.rmtree("separated_temp")
            if os.path.exists("temp_audio.mp3"): os.remove("temp_audio.mp3")
            if os.path.exists("temp_original.mp3"): os.remove("temp_original.mp3")
            if os.path.exists("temp_instrumental.mp3"): os.remove("temp_instrumental.mp3")
            if os.path.exists("temp_karaoke_bg.mp4"): os.remove("temp_karaoke_bg.mp4")
        except:
            pass
            
        # Metadata
        # Generate Thumbnail
        thumb_path = self.generate_thumbnail(title, artist)
        
        return {
            "title": f"🎤 [KARAOKE] {title} - {artist} | Lyrics + Instrumental (Lower Key)",
            "description": f"Sing along to {title} by {artist}!\n\n🎤 Best Karaoke Version with Lyrics\n🎶 Instrumental + Vocal Guide\n🔥 Trending Song {random.choice(['2024', '2025'])}\n\n#karaoke #{artist.replace(' ','')} #lyrics #{title.replace(' ','')} #singalong",
            "tags": ["karaoke", "lyrics", "music", artist, title, "instrumental", "sing along", "karaoke version", "clean lyrics"],
            "thumbnail": thumb_path
        }

def create_karaoke_video(output_path):
    gen = KaraokeGenerator()
    return gen.create_video(output_path)

if __name__ == "__main__":
    create_karaoke_video("test_karaoke_wipe.mp4")
