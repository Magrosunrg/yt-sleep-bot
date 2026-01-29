import os
import random
import requests
import re
import numpy as np
import scipy.io.wavfile as wavfile
import edge_tts
import asyncio
from media_manager import MediaManager
from ai_visual_generator import AIVisualGenerator

# MoviePy imports with fallback
try:
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, vfx, concatenate_audioclips, CompositeAudioClip, ImageClip
    import moviepy.audio.fx.all as afx
except ImportError:
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.video.VideoClip import ImageClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    from moviepy.video.compositing.concatenate import concatenate_videoclips
    from moviepy.audio.compositing.concatenate import concatenate_audioclips
    from moviepy.audio.AudioClip import CompositeAudioClip
    import moviepy.video.fx.all as vfx
    import moviepy.audio.fx.all as afx

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"

import sys
import subprocess
import gc
import time

class LongVideoManager:
    def __init__(self):
        self.media_mgr = MediaManager()
        # self.ai_gen = AIVisualGenerator() # Removed to run in subprocess
        self.brown_noise_file = "assets/brown_noise_loop.wav"
        self._ensure_brown_noise()
        self.grid_bg_file = "assets/grid_bg.png"
        self._ensure_grid_background()

    def _ensure_brown_noise(self):
        """Generates a brown noise file if it doesn't exist."""
        if not os.path.exists("assets"):
            os.makedirs("assets")
        
        if not os.path.exists(self.brown_noise_file):
            print("🔊 Generating Brown Noise...")
            duration = 10  # 10 seconds loop
            sample_rate = 44100
            samples = int(duration * sample_rate)
            
            # Brown noise: integration of white noise
            white = np.random.standard_normal(samples)
            brown = np.cumsum(white)
            
            # Normalize to -1 to 1
            brown /= np.max(np.abs(brown))
            
            # Write to file
            wavfile.write(self.brown_noise_file, sample_rate, (brown * 32767).astype(np.int16))

    def generate_calm_script(self, topic, num_facts=5):
        """Generates a structured list of script segments."""
        # Refined prompt to match "Sleepy Science Channel" style
        
        prompt = (
            f"Write a deep, narrative sleep script about '{topic}' for the 'Night Lab Stories' channel.\n"
            f"Style Guide:\n"
            f"- Begin with 'Hello there and welcome to Night Lab Stories. Tonight we're going to drift into...'\n"
            f"- The tone should be 'academic yet poetic', soothing, and philosophical. Like a gentle documentary.\n"
            f"- Structure the content as a continuous narrative journey, not just a list of facts.\n"
            f"- Focus on mysteries, deep time, vast scales, and unanswered questions.\n"
            f"- Use phrases like 'We still don't know...', 'The mystery remains...', 'Drift into the unknown...'\n"
            f"- End with a transition into silence or a final thought on the beauty of the unknown.\n\n"
            f"Formatting:\n"
            f"- Return the script as distinct blocks/paragraphs separated by '|||'.\n"
            f"- Ensure there are at least {num_facts} substantial sections (Intro ||| Section 1 ||| Section 2 ... ||| Outro).\n"
            f"- Do not use headers like 'Section 1:', just the raw narration text."
        )
        
        payload = {"model": DEFAULT_MODEL, "prompt": prompt, "stream": False}
        try:
            r = requests.post(OLLAMA_URL, json=payload)
            if r.status_code == 200:
                text = r.json().get("response", "").strip()
                # Split by delimiter
                parts = [p.strip() for p in text.split("|||") if p.strip()]
                return parts
        except Exception as e:
            print(f"Script Gen Error: {e}")
            return [
                "Close your eyes ... and soften your body ...",
                f"The ocean is deep ... and calm ... {topic} is wonderful ...",
                "Sleep now ..."
            ]

    def generate_relaxing_facts_script(self, topic, min_duration=6600):
        """
        Generates a list of relaxing facts until the estimated duration exceeds min_duration.
        Default min_duration = 6600s (1h 50m).
        """
        print(f"📚 Generating relaxing facts about {topic} to fill ~{min_duration/60:.1f} minutes...")
        
        ordered_facts = []
        
        # Intro
        intro = (
            f"Hello there. Welcome to a special session of Night Lab Stories. "
            f"Tonight, we have prepared a collection of the most relaxing facts about {topic} "
            f"to help you drift off into a deep sleep. Let go of the day, close your eyes, "
            f"and let these truths wash over you."
        )
        ordered_facts.append(intro)
        ordered_facts.append("[PAUSE_3]")
        
        # Estimate duration tracking
        # Avg speaking rate ~130 wpm. 
        # Duration = (words / 130) * 60 + pauses
        current_est_duration = 0.0
        
        # Calculate initial duration
        w_count = len(intro.split())
        current_est_duration += (w_count / 130.0) * 60.0 + 3.0 # +3 for pause
        
        # Sub-topic generator loop
        iteration = 0
        existing_facts_hashes = set()
        
        while current_est_duration < min_duration:
            iteration += 1
            needed_mins = (min_duration - current_est_duration) / 60.0
            print(f"   ⏱️ Current Est: {current_est_duration/60:.1f}m. Target: {min_duration/60:.1f}m. Needed: {needed_mins:.1f}m")
            
            # 1. Get a fresh sub-topic
            sub_prompt = (
                f"Give me ONE distinct, soothing sub-topic related to '{topic}' that you haven't used yet. "
                f"Examples: specific phenomena, history, colors, sounds, vastness. "
                f"Just the sub-topic name."
            )
            try:
                r = requests.post(OLLAMA_URL, json={"model": DEFAULT_MODEL, "prompt": sub_prompt, "stream": False})
                if r.status_code == 200:
                    sub_topic = r.json().get("response", "").strip().replace('"', '')
                else:
                    sub_topic = f"{topic} Aspect {iteration}"
            except:
                sub_topic = f"{topic} Part {iteration}"
                
            print(f"   🔍 Generating batch for sub-topic: {sub_topic}...")
            
            # 2. Generate batch of 5 detailed facts (approx 2-3 mins of content including pauses)
            prompt = (
                f"Write 5 distinct, soothing, paragraph-length facts about '{sub_topic}' (related to {topic}).\n"
                f"Each fact should be 3-4 sentences long, rich with description.\n"
                f"Style: Soft, poetic, avoiding hard 'P'/'T'/'K' sounds (plosives). Use a warm voice.\n"
                f"Format: Separate each fact with '|||'. Do not use numbers or intro/outro text."
            )
            
            try:
                r = requests.post(OLLAMA_URL, json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False})
                if r.status_code == 200:
                    text = r.json().get("response", "").strip()
                    parts = [p.strip() for p in text.split("|||") if len(p.strip()) > 20]
                    
                    for p in parts:
                        # Uniqueness check
                        norm = re.sub(r'[^\w\s]', '', p).lower()
                        # Check against hash set (first 50 chars is usually enough to detect dupes)
                        h = hash(norm[:100])
                        
                        if h not in existing_facts_hashes:
                            existing_facts_hashes.add(h)
                            ordered_facts.append(p)
                            ordered_facts.append("[PAUSE_3]")
                            
                            # Update duration estimate
                            wc = len(p.split())
                            dur = (wc / 130.0) * 60.0 + 3.0 # +3s pause
                            current_est_duration += dur
                            
            except Exception as e:
                print(f"   ❌ Batch Error: {e}")
                time.sleep(1)
                
            # Break if we're looping too much (safety)
            if iteration > 100: 
                print("   ⚠️ Max iterations reached. Stopping generation.")
                break
                
        # Outro
        outro = (
            f"We have journeyed far through the world of {topic}. "
            f"The world is full of wonder, and now it is time for you to rest. "
            f"Goodnight."
        )
        ordered_facts.append(outro)
        
        return ordered_facts

    def parse_custom_script(self, text):
        """Parses a raw text script into segments, preserving [PAUSE_N] tags."""
        # Normalize newlines
        text = text.replace("\r\n", "\n")
        
        # Split by [PAUSE_N] tags, keeping them
        # Pattern: [PAUSE_10] or [PAUSE_5] etc.
        parts = re.split(r'(\[PAUSE_\d+\])', text)
        
        segments = []
        for p in parts:
            p = p.strip()
            if not p: continue
            
            # If it's a pause tag, add it directly
            if re.match(r'^\[PAUSE_\d+\]$', p):
                segments.append(p)
            else:
                # Regular text processing
                if "|||" in p:
                    sub_parts = [sp.strip() for sp in p.split("|||") if sp.strip()]
                    segments.extend(sub_parts)
                else:
                    # Split by double newlines if no explicit separators
                    sub_parts = [sp.strip() for sp in p.split("\n\n") if sp.strip()]
                    if len(sub_parts) <= 1:
                         # Fallback to newline splitting if long enough
                         sub_parts = [sp.strip() for sp in p.split("\n") if len(sp.strip()) > 50]
                         if not sub_parts: sub_parts = [p] # Just take the chunk
                    segments.extend(sub_parts)
                    
        return segments


    async def generate_audio_segments(self, segments, output_dir="temp_audio_segs"):
        """Generates audio files for each segment."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Check for Voice Cloning Sample
        voice_sample = os.path.join("voices", "morgan_freeman_sample.mp3")
        use_cloning = False
        if os.path.exists(voice_sample):
            print(f"🎙️ Found Voice Sample: {voice_sample}, attempting cloning...")
            try:
                # Add src to sys.path to ensure we can import
                sys.path.append(os.path.dirname(__file__))
                from tts_chatterbox import generate_cloned_audio
                use_cloning = True
            except ImportError:
                print("⚠️ Chatterbox module not found, falling back to Edge TTS.")
        
        files = []
        for i, text in enumerate(segments):
            # Check for [PAUSE_N] tag
            if re.match(r'^\[PAUSE_\d+\]$', text):
                # Just add the tag as a string to the files list
                files.append(text)
                continue
                
            out_path = os.path.join(output_dir, f"seg_{i}.mp3")
            success = False
            
            if use_cloning:
                try:
                    # Run synchronous cloning in thread to avoid blocking async loop too much
                    # (Though here we are just awaiting the loop, so simple call is fine for now)
                    res = generate_cloned_audio(text, out_path, voice_sample)
                    if isinstance(res, tuple): success = res[0]
                    else: success = res
                except Exception as e:
                    print(f"   ❌ Cloning failed for seg {i}: {e}")
            
            if not success:
                if use_cloning: print("   ⚠️ Fallback to Edge TTS for this segment.")
                communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate="-20%", pitch="-15Hz")
                await communicate.save(out_path)
                
            files.append(out_path)
        return files

    def _ensure_grid_background(self):
        """Generates a 1920x1080 grid background."""
        if not os.path.exists("assets"):
            os.makedirs("assets")
        
        if not os.path.exists(self.grid_bg_file):
            print("🎨 Generating Grid Background...")
            try:
                from PIL import Image, ImageDraw
                w, h = 1920, 1080
                # Dark grey background (almost black)
                img = Image.new("RGB", (w, h), "#101010") 
                draw = ImageDraw.Draw(img)
                
                # Draw grid
                step = 100
                # Thin grey lines
                line_color = "#303030" 
                
                for x in range(0, w, step):
                    draw.line([(x, 0), (x, h)], fill=line_color, width=2)
                
                for y in range(0, h, step):
                    draw.line([(0, y), (w, y)], fill=line_color, width=2)
                    
                img.save(self.grid_bg_file)
            except ImportError:
                print("⚠️ PIL not found, skipping grid generation.")

    def generate_ai_images(self, topic, segments):
        """Generates AI images for each script segment (via subprocess)."""
        images = []
        unique_images = []
        MAX_UNIQUE_IMAGES = 5 # Limit to prevent memory exhaustion/long wait
        
        print(f"🎨 Generating AI images for topic: {topic} (Max Unique: {MAX_UNIQUE_IMAGES})...")
        
        # Ensure output dir
        out_dir = "temp_ai_visuals"
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        script_path = os.path.join(os.path.dirname(__file__), "ai_visual_generator.py")
            
        for i, seg in enumerate(segments):
            # Reuse images if we exceed max unique limit
            if i >= MAX_UNIQUE_IMAGES:
                images.append(unique_images[i % MAX_UNIQUE_IMAGES])
                continue

            path = os.path.join(out_dir, f"visual_{i}.png")
            
            if not os.path.exists(path):
                prompt_topic = f"{topic} illustration part {i}"
                if i == 0: prompt_topic = f"{topic} gentle introduction"
                elif i == len(segments)-1: prompt_topic = f"{topic} peaceful conclusion"
                
                print(f"   🤖 Generating image {i+1}/{min(len(segments), MAX_UNIQUE_IMAGES)}: {prompt_topic}")
                
                try:
                    # Force garbage collection before subprocess
                    gc.collect()
                    time.sleep(1) 
                    
                    # Run generation in separate process to manage VRAM
                    subprocess.run(
                        [sys.executable, script_path, "--topic", prompt_topic, "--output", path],
                        check=True
                    )
                    
                    if os.path.exists(path):
                        unique_images.append(path)
                        images.append(path)
                    else:
                        print("   ⚠️ AI generation failed (no file), using fallback.")
                        fallback = unique_images[-1] if unique_images else self.grid_bg_file
                        unique_images.append(fallback)
                        images.append(fallback)
                except Exception as e:
                    print(f"   ❌ Subprocess Error: {e}")
                    fallback = unique_images[-1] if unique_images else self.grid_bg_file
                    unique_images.append(fallback)
                    images.append(fallback)
            else:
                unique_images.append(path)
                images.append(path)
                
        return images

    def get_visuals(self, topic, min_duration):
        # Legacy method, kept for compatibility if needed, but we override functionality
        pass

    def apply_sleep_effects(self, clip):
        """Applies Dimmer (Brightness -30%) and Saturation -20%."""
        # 1. Brightness: multiply by 0.7
        clip = clip.fx(vfx.colorx, 0.7)
        
        # 2. Saturation: -20% (0.8 factor)
        def reduce_saturation(im):
            # im is (H, W, 3) numpy array
            # Simple RGB to Gray approximation
            gray = im.mean(axis=2, keepdims=True)
            # Interpolate between color and gray
            return im * 0.8 + gray * 0.2

        clip = clip.fl_image(reduce_saturation)
        return clip

    def generate_long_animated_background(self, topic):
        """Generates an animated AI background loop for the topic."""
        print(f"🎬 Generating animated AI background for: {topic}...")
        
        cache_dir = "assets/backgrounds"
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).strip("_")
        cache_file = os.path.join(cache_dir, f"ai_bg_{safe_topic}.mp4")
        
        if os.path.exists(cache_file):
            print(f"   ✅ Found cached AI background: {cache_file}")
            return cache_file
            
        # Call AI Generator via subprocess
        script_path = os.path.join(os.path.dirname(__file__), "ai_visual_generator.py")
        
        try:
            # Force GC
            gc.collect()
            
            print("   ⏳ Running AI generation (this may take 30-60s)...")
            subprocess.run(
                [sys.executable, script_path, "--topic", topic, "--output", cache_file, "--mode", "video"],
                check=True
            )
            
            if os.path.exists(cache_file):
                print(f"   ✅ Generated AI background: {cache_file}")
                return cache_file
            else:
                print("   ❌ AI generation failed (no file produced).")
                return None
                
        except Exception as e:
            print(f"   ❌ Subprocess Error: {e}")
            return None

    def search_long_background(self, topic, min_duration=60, target_duration=7200):
        """Searches and downloads a long background video (YouTube) for the topic."""
        print(f"🎥 Searching for background video: {topic}...")
        
        # Search queries to try
        queries = [
            f"{topic} 4k cinematic nature drone no music",
            f"{topic} real footage 4k loop no music",
            f"{topic} ambience visual only",
            f"{topic} documentary footage no voice"
        ]
        
        import yt_dlp
        
        video_path = None
        
        # Create a cache directory
        cache_dir = "assets/backgrounds"
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        # Sanitize topic for filename
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).strip("_")
        cache_file = os.path.join(cache_dir, f"bg_{safe_topic}.mp4")
        
        if os.path.exists(cache_file):
            print(f"   ✅ Found cached background: {cache_file}")
            return cache_file
        
        for q in queries:
            try:
                print(f"   🔍 Trying query: {q}")
                
                # We need a download range callback to limit size
                # Limit to target_duration + 5 mins
                limit_seconds = target_duration + 300
                
                def download_range_func(info, ydl):
                    dur = info.get('duration', 0)
                    if dur > limit_seconds:
                        return [{'start_time': 0, 'end_time': limit_seconds}]
                    return None # Download all
                
                ydl_opts = {
                    'default_search': 'ytsearch1:',
                    'noplaylist': True,
                    'quiet': True,
                    'format': 'bestvideo[height<=1080][ext=mp4]/best[height<=1080][ext=mp4]', 
                    'outtmpl': cache_file,
                    'download_ranges': download_range_func
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(q, download=False)
                    if 'entries' in info: info = info['entries'][0]
                    
                    dur = info.get('duration', 0)
                    if dur > min_duration:
                        print(f"   ✅ Found candidate ({dur}s): {info.get('title')}")
                        # Download
                        ydl.download([info['webpage_url']])
                        
                        if os.path.exists(cache_file):
                            video_path = cache_file
                            break
                    else:
                        print(f"   ⚠️ Video too short ({dur}s), skipping.")
                        
            except Exception as e:
                print(f"   ❌ Search failed for '{q}': {e}")
                
            if video_path: break
            
        return video_path

    def create_long_video(self, topic, num_facts=15, output_file="sleep_video.mp4", outro_duration=7200, custom_script=None, progress_callback=None, use_ai_visuals=False):
        # Interpret outro_duration as Total Target Duration for "Facts Throughout" mode
        target_duration = outro_duration 
        print(f"🌙 Starting Sleep Video Generation: {topic} (Target: {target_duration}s)")
        if progress_callback: progress_callback(5)
        
        is_relaxing_facts_mode = False
        
        # 1. Script (List of segments)
        if custom_script:
            print("📜 Using Custom Script provided by user.")
            segments = self.parse_custom_script(custom_script)
        else:
            # Decide between "Narrative" (Sleepy Science Channel) and "Facts List"
            # If num_facts is high (> 20), assume user wants "100 Relaxing Facts" style
            if num_facts > 20:
                print(f"   ℹ️ High fact count ({num_facts}) detected. Switching to 'Relaxing Facts List' mode.")
                # Pass target_duration to ensure we generate enough content
                segments = self.generate_relaxing_facts_script(topic, min_duration=target_duration)
                is_relaxing_facts_mode = True
            else:
                # Narrative Style
                # Ensure we have enough segments for 2 hours if num_facts is small
                if num_facts < 10 and target_duration > 3600:
                    num_facts = 15
                    print(f"   ℹ️ Increased num_facts to {num_facts} to fill duration.")
                    
                segments = self.generate_calm_script(topic, num_facts)
        
        print(f"📜 Script generated: {len(segments)} segments.")
        if progress_callback: progress_callback(15)
        
        # 2. Audio Segments
        audio_dir = "temp_audio_segs"
        audio_files = asyncio.run(self.generate_audio_segments(segments, audio_dir))
        print(f"🗣️ Audio segments generated: {len(audio_files)}")
        if progress_callback: progress_callback(35)
        
        # 3. Build Audio Track
        audio_clips = []
        current_time = 0
        
        if custom_script or is_relaxing_facts_mode:
             # Natural flow: Stack clips with explicit or default gaps
             print(f"   ℹ️ Constructing timeline with natural flow...")
                 
             for af in audio_files:
                 # Check for PAUSE tag
                 if isinstance(af, str) and af.startswith("[PAUSE_"):
                     try:
                         pause_dur = int(af.replace("[PAUSE_", "").replace("]", ""))
                         current_time += float(pause_dur)
                     except:
                         current_time += 2.0
                 else:
                     # Audio File
                     if os.path.exists(af):
                         try:
                             clip = AudioFileClip(af).set_start(current_time)
                             audio_clips.append(clip)
                             current_time += clip.duration
                             
                             # Add small breath gap for custom scripts (if not using explicit pauses everywhere)
                             if not is_relaxing_facts_mode:
                                 current_time += 0.5
                         except Exception as e:
                             print(f"   ⚠️ Error loading clip {af}: {e}")
             
             # Calculate script duration
             script_duration = current_time
             print(f"   ⏱️  Script Content Duration: {script_duration:.2f}s")
             
             # If script is longer than target (unlikely for sleep videos but possible), extend target
             if script_duration > target_duration:
                 target_duration = script_duration + 10.0
                 print(f"   ℹ️  Script is longer than requested duration. Extended to {target_duration:.2f}s")
             else:
                 print(f"   ℹ️  Video will continue with ambience until {target_duration}s (Ambience: {(target_duration - script_duration):.2f}s)")
             
             # Interval for visuals logic (if falling back to AI images)
             interval = target_duration / (len(audio_files) if len(audio_files) > 0 else 1)

        else:
            # Distributed flow: Space out evenly over target_duration
            active_duration = target_duration * 0.95
            interval = active_duration / len(audio_files)
            
            # Verify interval is sufficient to prevent overlap
            max_clip_dur = 0
            for af in audio_files:
                try:
                    d = AudioFileClip(af).duration
                    if d > max_clip_dur: max_clip_dur = d
                except: pass
                
            if interval < max_clip_dur + 1:
                print(f"⚠️ Interval {interval:.2f}s too short for max clip {max_clip_dur:.2f}s. Adjusting to avoid overlap.")
                interval = max_clip_dur + 2
                # If we had to expand interval, we must expand target_duration
                min_req_duration = interval * len(audio_files)
                if min_req_duration > target_duration:
                     target_duration = min_req_duration + 10
                     print(f"   ℹ️  Expanded target_duration to {target_duration:.2f}s to fit audio.")
            
            for af in audio_files:
                clip = AudioFileClip(af).set_start(current_time)
                audio_clips.append(clip)
                current_time += interval
            
        # Add Brown Noise Background
        brown_noise = AudioFileClip(self.brown_noise_file).fx(afx.audio_loop, duration=target_duration).volumex(0.15)
        
        # Combine Voice + Brown Noise
        # Ensure we don't accidentally mix in previous audio tracks
        final_audio = CompositeAudioClip(audio_clips + [brown_noise]).set_duration(target_duration)
        
        # 4. Visuals (Animated Realistic Video - AI Generated)
        bg_video_path = None
        visual_clips = []
        temp_bg_clips = []
        file_paths = [] # Initialize here for scope access
        
        if use_ai_visuals:
            print("🤖 AI Mode: Generating synced Ken Burns visuals...")
            
            # Create temp dir
            ai_vis_dir = "temp_ai_visuals"
            if not os.path.exists(ai_vis_dir):
                os.makedirs(ai_vis_dir)
                
            script_path = os.path.join(os.path.dirname(__file__), "ai_visual_generator.py")
            
            # Iterate through segments to generate synced visuals
            i = 0
            while i < len(segments):
                seg_text = segments[i]
                
                # Check if current segment is a pause (shouldn't happen if we consume them, but safety)
                if isinstance(seg_text, str) and re.match(r'^\[PAUSE_\d+\]$', seg_text):
                    i += 1
                    continue
                
                # Get Audio Duration
                af = audio_files[i]
                try:
                    # Quick probe
                    temp_audioclip = AudioFileClip(af)
                    dur = temp_audioclip.duration
                    temp_audioclip.close()
                except:
                    dur = 5.0
                    
                # Calculate total visual duration (Audio + Gap + Following Pauses)
                gap = 0.5 if not is_relaxing_facts_mode else 0
                total_dur = dur + gap
                
                # Look ahead for pauses
                j = i + 1
                while j < len(segments):
                    next_seg = segments[j]
                    if isinstance(next_seg, str) and re.match(r'^\[PAUSE_\d+\]$', next_seg):
                        try:
                            p_dur = int(next_seg.replace("[PAUSE_", "").replace("]", ""))
                            total_dur += p_dur
                        except:
                            total_dur += 2.0
                        j += 1
                    else:
                        break
                
                # Generate Ken Burns Video
                # Sanitize filename
                safe_name = "".join([c if c.isalnum() else "_" for c in seg_text[:20]])
                out_path = os.path.join(ai_vis_dir, f"kb_{i}_{safe_name}.mp4")
                
                print(f"   🎬 Generating Visual for segment {i} ({total_dur:.1f}s): {seg_text[:40]}...")
                
                try:
                    # Force GC
                    gc.collect()
                    
                    cmd = [
                        sys.executable, script_path,
                        "--topic", seg_text,
                        "--output", out_path,
                        "--mode", "ken_burns",
                        "--duration", str(total_dur)
                    ]
                    
                    subprocess.run(cmd, check=True)
                    
                    if os.path.exists(out_path):
                        vc = VideoFileClip(out_path)
                        visual_clips.append(vc)
                        file_paths.append(out_path)
                    else:
                        print("   ❌ AI Gen Failed (No Output). Using fallback.")
                        raise Exception("No output")
                        
                except Exception as e:
                    print(f"   ⚠️ Visual Gen Error: {e}. Using Grid Fallback.")
                    # Fallback: Grid Image
                    # We need to generate a static image or use grid
                    # Just use grid for now to save complexity
                    fallback_clip = ImageClip(self.grid_bg_file).set_duration(total_dur)
                    visual_clips.append(fallback_clip)
                
                # Advance index
                i = j

        else:
            # Default: Try YouTube first for high quality real footage
            print("🎥 Standard Mode: Searching for background video on YouTube...")
            bg_video_path = self.search_long_background(topic, min_duration=60)
            
            if not bg_video_path:
                 print("   ⚠️ YouTube search failed/empty. Fallback to AI generation.")
                 # Since we removed the old loop generator, we fallback to grid or we could use the new logic?
                 # But standard mode usually implies ONE background.
                 # Let's fallback to the new logic if YouTube fails? 
                 # Or just use grid.
                 # User said "make ONLY the collab version to have an ai video maker"
                 # So standard mode should probably just use grid if YT fails.
                 pass
        
        if bg_video_path and os.path.exists(bg_video_path):
            print(f"   ✅ Using background video: {bg_video_path}")
            try:
                # Load video
                bg_clip = VideoFileClip(bg_video_path)
                # Remove audio from bg
                bg_clip = bg_clip.without_audio()
                
                # Loop to fill duration
                # We can just use loop() but for very long videos, looping a 10min clip 12 times is fine.
                # However, VideoFileClip(path).loop(duration=X) is efficient.
                
                # Resize/Crop to ensure 1920x1080
                if bg_clip.h != 1080 or bg_clip.w != 1920:
                    print(f"   ℹ️ Resizing background from {bg_clip.w}x{bg_clip.h} to 1920x1080...")
                    # First resize by height
                    bg_clip = bg_clip.resize(height=1080)
                    # Then crop center width
                    if bg_clip.w > 1920:
                        x_center = bg_clip.w / 2
                        bg_clip = bg_clip.crop(x1=int(x_center - 960), width=1920, height=1080)
                    elif bg_clip.w < 1920:
                        # If width is less than 1920 (e.g. 4:3), we might need to blur/pad?
                        # Or just resize width to 1920 (stretches) -> User probably prefers crop if possible.
                        # For sleep videos, stretching nature might look bad.
                        # Let's resize to cover 1920 width, then crop height?
                        bg_clip = bg_clip.resize(width=1920)
                        y_center = bg_clip.h / 2
                        bg_clip = bg_clip.crop(y1=int(y_center - 540), width=1920, height=1080)
                
                # Double check dimensions are even
                if bg_clip.w % 2 != 0: bg_clip = bg_clip.crop(x1=0, width=bg_clip.w-1)
                if bg_clip.h % 2 != 0: bg_clip = bg_clip.crop(y1=0, height=bg_clip.h-1)
                
                final_bg = bg_clip.fx(vfx.loop, duration=target_duration)
                visual_clips = [final_bg]
                temp_bg_clips.append(bg_clip) # Keep ref to close later
                
            except Exception as e:
                print(f"   ❌ Failed to process background video: {e}")
                bg_video_path = None # Fallback
        
        if not visual_clips:
            print("   ⚠️ No video found or processing failed. Falling back to AI/Grid visuals.")
            # Fallback to AI Images (Grid Style)
            ai_images = self.generate_ai_images(topic, segments)
            
            # ... (Original AI Image Logic) ...
            for i in range(len(audio_files)):
                img_path = ai_images[i] if i < len(ai_images) else ai_images[-1]
                bg = ImageClip(self.grid_bg_file).set_duration(interval)
                fg = ImageClip(img_path).resize(height=800).set_position("center").set_duration(interval)
                comp = CompositeVideoClip([bg, fg]).set_duration(interval)
                if i > 0: comp = comp.crossfadein(1.0)
                visual_clips.append(comp)
                
            # Outro for fallback
            remaining = target_duration - (len(visual_clips) * interval)
            if remaining > 0:
                last_img = ai_images[-1]
                bg = ImageClip(self.grid_bg_file).set_duration(remaining)
                fg = ImageClip(last_img).resize(height=800).set_position("center").set_duration(remaining)
                comp = CompositeVideoClip([bg, fg]).set_duration(remaining).crossfadein(1.0)
                visual_clips.append(comp)

        if len(visual_clips) == 1:
            final_video = visual_clips[0]
        else:
            final_video = concatenate_videoclips(visual_clips, method="compose")
            
        final_video = final_video.set_audio(final_audio)
        
        # Apply Sleep Effects (Dimmer + Saturation)
        # OPTIMIZATION: We skip Python-based effects (slow) and use FFmpeg filters (fast)
        # print("💤 Applying Sleep Effects (Dimmer & Saturation)...")
        # final_video = self.apply_sleep_effects(final_video)
        
        # FINAL DIMENSION SAFETY CHECK
        # Ensure even dimensions for yuv420p
        if final_video.w % 2 != 0 or final_video.h % 2 != 0:
            print(f"⚠️ Odd output dimensions detected ({final_video.w}x{final_video.h}). Fixing...")
            new_w = final_video.w if final_video.w % 2 == 0 else final_video.w - 1
            new_h = final_video.h if final_video.h % 2 == 0 else final_video.h - 1
            final_video = final_video.crop(x1=0, y1=0, width=new_w, height=new_h)
            print(f"   ✅ Fixed dimensions: {final_video.w}x{final_video.h}")
        
        # Track files for cleanup
        # Don't delete cached backgrounds in assets/backgrounds
        if bg_video_path and "assets/backgrounds" not in bg_video_path.replace("\\", "/"):
             file_paths.append(bg_video_path)
             
        # file_paths.extend(ai_images) # Only if fallback used, but variable scope issue.
        # We can just check temp dir cleanup at end.
        
        # 5. Render
        print(f"💾 Rendering video ({target_duration}s @ 24fps)...")
        # We must use 'fast' preset and maybe lower resolution if 2 hours is too big?
        # 1080p 2 hours is huge. But user wants 4k nature visuals? 
        # I'll stick to 1080p.
        
        try:
            final_video.write_videofile(
                output_file, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac",
                threads=4,
                preset="ultrafast", # Speed up long render
                # Optimized Sleep Effects: Contrast 0.7 (dimmer), Saturation 0.8
                ffmpeg_params=["-pix_fmt", "yuv420p", "-vf", "eq=contrast=0.7:saturation=0.8"] 
            )
            if progress_callback: progress_callback(100)
        except Exception as e:
            print(f"❌ Render Error: {e}")
        finally:
            # Explicitly close clips to release file handles
            try:
                final_video.close()
                if final_audio: final_audio.close()
                if brown_noise: brown_noise.close()
                for c in audio_clips: c.close()
                for c in visual_clips: c.close()
            except:
                pass
        
        # Cleanup
        import shutil
        # Wait a bit for file handles to release
        import time
        time.sleep(1)
        
        if os.path.exists(audio_dir):
            try:
                shutil.rmtree(audio_dir)
            except Exception as e:
                print(f"⚠️ Cleanup Warning: Could not remove {audio_dir}: {e}")
                
        if os.path.exists("temp_ai_visuals"):
            try:
                shutil.rmtree("temp_ai_visuals")
            except Exception as e:
                print(f"⚠️ Cleanup Warning: Could not remove temp_ai_visuals: {e}")
                
        for p in file_paths:
            try: os.remove(p)
            except: pass
            
        return output_file

if __name__ == "__main__":
    mgr = LongVideoManager()
    mgr.create_long_video("Deep Ocean", num_facts=3, output_file="test_sleep.mp4")
