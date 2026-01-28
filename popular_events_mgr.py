import os
import subprocess
import json
import requests
import asyncio
import edge_tts
# import nest_asyncio
import random
import textwrap
from PIL import Image, ImageDraw, ImageFont
import numpy as np
# import tts_manager  # Removed as user requested no Kokoro

# MoviePy imports with proper fallback
try:
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip, ColorClip, vfx, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip
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
    except ImportError:
        # MoviePy v2
        from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip, ColorClip, vfx, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip

# nest_asyncio.apply()

# Constants
# VOICE = "en-US-ChristopherNeural"  # Removed
OLLAMA_URL = "http://localhost:11434/api/chat"

def get_ffmpeg_path() -> str:
    local = os.path.join(os.getcwd(), "ffmpeg.exe")
    return os.path.abspath(local) if os.path.isfile(local) else "ffmpeg"

def search_and_download_event(topic, output_dir="temp_events"):
    """
    Searches for a popular short video about the topic and downloads it.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"🔍 Searching for popular shorts about: {topic}")
    
    # Construct yt-dlp command to search and download the first result
    # We target shorts by adding "shorts" to query and filtering duration
    # Search for more candidates (50) to increase chance of passing filters
    search_query = f"ytsearch50:{topic} shorts"
    
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")
    
    def run_search(query):
        cmd_meta = [
            "yt-dlp",
            "--dump-json",
            "--default-search", "ytsearch",
            "--match-filter", "duration < 90", # Ensure it's short
            "--no-playlist",
            query
        ]
        try:
            # Check output might fail if no matches found, so we catch it
            result = subprocess.check_output(cmd_meta, encoding="utf-8", errors="ignore")
            lines = result.strip().splitlines()
            return lines
        except Exception as e:
            print(f"⚠️ Search failed for query '{query}': {e}")
            return []

    # 1. Get Metadata first
    print(f"🔎 Attempting search with query: {search_query}")
    lines = run_search(search_query)
    
    # Fallback: try searching without "shorts" keyword if first attempt fails
    if not lines:
        print(f"⚠️ No results for '{search_query}'. Retrying without 'shorts' keyword...")
        fallback_query = f"ytsearch50:{topic}"
        lines = run_search(fallback_query)

    if not lines:
        print(f"⚠️ No short videos found for topic: {topic}")
        return None, None, None

    # Take the first valid result
    metadata = json.loads(lines[0])
    video_id = metadata.get("id")
    title = metadata.get("title")
    desc = metadata.get("description")
    webpage_url = metadata.get("webpage_url")
    
    print(f"✅ Found Video: {title}")
    
    # 2. Download Video
    video_filename = os.path.join(output_dir, f"{video_id}.mp4")
    
    if os.path.exists(video_filename):
        print("Video already exists, skipping download.")
        return video_filename, title, desc
        
    cmd_dl = [
        "yt-dlp",
        "-o", output_template,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--match-filter", "duration < 90",
        "--no-playlist",
        webpage_url
    ]
    
    try:
        subprocess.run(cmd_dl, check=True)
        
        # Find the file (extension might vary slightly but we forced mp4 mostly)
        # If yt-dlp merged formats, it might be .mp4
        if not os.path.exists(video_filename):
            # Check directory for the file
            for f in os.listdir(output_dir):
                if f.startswith(video_id):
                    video_filename = os.path.join(output_dir, f)
                    break
                    
        return video_filename, title, desc
        
    except Exception as e:
        print(f"❌ Error finding/downloading video: {e}")
        return None, None, None

def generate_commentary(topic, title, desc, model="llama3"):
    """
    Generates a realistic male commentary using Ollama.
    """
    print(f"🧠 Generating commentary for '{title}'...")
    
    system_prompt = (
        "You are a charismatic, realistic male commentator for a viral video channel. "
        "Your job is to give a short, energetic, and engaging commentary on an event. "
        "Sound natural, maybe a bit opinionated or excited, like a real person reacting to news. "
        "Do not start with 'Ladies and gentlemen' or 'Welcome back'. Jump straight into the commentary. "
        "Keep it under 60 words."
    )
    
    user_prompt = (
        f"Topic: {topic}\n"
        f"Video Title: {title}\n"
        f"Video Context: {desc[:200]}...\n\n"
        "Write the commentary script now. Just the spoken text."
    )
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }
    
    try:
        print(f"   Waiting for Ollama commentary generation (Timeout: 30m)...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=1800)
        response.raise_for_status()
        result = response.json()
        text = result.get("message", {}).get("content", "")
        print(f"📝 Commentary: {text}")
        return text
    except Exception as e:
        print(f"❌ Ollama Error: {e}")
        return f"Check this out! {title} is absolutely crazy. You have to see this."

def generate_viral_topic(model="llama3"):
    """
    Asks Ollama to suggest a popular, timeless, or trending viral video topic search query.
    """
    print("🧠 Generating viral topic...")
    
    system_prompt = (
        "You are a social media trend analyst. "
        "Suggest ONE specific, catchy search query for finding a viral short video on YouTube. "
        "The topic should be likely to return high-energy, interesting clips (e.g., 'Met Gala Highlights', 'Crazy Parkour Fails', 'Cute Cat Moments', 'Street Food India'). "
        "Do not include quotes. Output ONLY the search query string."
    )
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Give me a search query for a viral video."}
        ],
        "stream": False
    }
    
    try:
        print(f"   Waiting for Ollama viral topic (Timeout: 30m)...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=1800)
        response.raise_for_status()
        result = response.json()
        text = result.get("message", {}).get("content", "").strip().replace('"', '')
        print(f"🎲 AI Suggestion: {text}")
        return text
    except Exception as e:
        print(f"❌ Topic Generation Error: {e}")
        return "Funny Cat Fails"

def generate_audio(text, output_file="commentary_audio.mp3"):
    """
    Generates audio using Edge TTS (Fallback).
    """
    try:
        voice = "en-US-ChristopherNeural"
        communicate = edge_tts.Communicate(text, voice)
        asyncio.run(communicate.save(output_file))
        return output_file
    except Exception as e:
        print(f"⚠️ TTS Generation failed: {e}")
        return None

def create_caption_clip(text, duration, fontsize=80, font="impact.ttf", size=(1080, 1920), uppercase=True, color="#FFD700", stroke_width=10):
    """Creates an ImageClip with text overlay using PIL (Impact Meme Style)."""
    if uppercase:
        text = text.upper()

    # Create transparent image
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Load font
    try:
        # Try Impact first (Windows default for memes)
        font_obj = ImageFont.truetype("impact.ttf", fontsize)
    except:
        try:
            # Fallback to Arial Bold if Impact missing
            font_obj = ImageFont.truetype("arialbd.ttf", fontsize)
        except:
            font_obj = ImageFont.load_default()

    # Text wrapping
    margin = 100
    width = size[0] - 2 * margin
    
    # Impact is condensed, so we can fit more chars. Adjust width param if needed.
    lines = textwrap.wrap(text, width=20) 
    
    # Calculate text height
    total_height = 0
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        h = bbox[3] - bbox[1]
        line_heights.append(h)
        total_height += h + 20 # Spacing

    # Draw text centered vertically and horizontally
    y = (size[1] - total_height) / 2
    
    for line, h in zip(lines, line_heights):
        # Center horizontally
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        w = bbox[2] - bbox[0]
        x = (size[0] - w) / 2
        
        # Meme Style: Strong Black Outline + Drop Shadow
        
        # Draw Shadow (Hard offset)
        shadow_offset = 8
        draw.text((x + shadow_offset, y + shadow_offset), line, font=font_obj, fill="black", stroke_width=stroke_width, stroke_fill="black")
        
        # Draw Main Text with Stroke
        draw.text((x, y), line, font=font_obj, fill=color, stroke_width=stroke_width, stroke_fill="black")
        
        y += h + 20

    return ImageClip(np.array(img)).set_duration(duration)

def create_reaction_video(video_path, commentary_text, output_path="final_reaction.mp4"):
    """
    Creates a Faceless Commentary Video:
    - Original Video (Visuals)
    - Commentary Audio (Voiceover)
    - Background Music
    - Captions (Text Overlay)
    """
    print("🎬 Editing final video...")
    
    temp_files = []
    
    try:
        # 1. Load Original Video
        original_clip = VideoFileClip(video_path)
        
        # Resize/Crop logic
        w, h = original_clip.size
        target_ratio = 9/16
        if w > h:
            new_w = h * target_ratio
            original_clip = original_clip.crop(x1=w/2 - new_w/2, x2=w/2 + new_w/2)
            original_clip = original_clip.resize(newsize=(1080, 1920))
        else:
            if w != 1080:
                original_clip = original_clip.resize(width=1080)
                # Ensure height is even
                w, h = original_clip.size
                if h % 2 != 0:
                    h_new = h - 1
                    original_clip = original_clip.crop(y1=0, y2=h_new)

        
        # 2. Generate Audio & Captions Segment by Segment
        # Split text by sentence for better syncing
        import re
        sentences = re.split(r'(?<=[.!?]) +', commentary_text)
        sentences = [s for s in sentences if s.strip()]
        
        audio_clips = []
        caption_clips = []
        
        for i, sentence in enumerate(sentences):
            if not sentence.strip(): continue
            
            # Generate Audio
            seg_audio_path = f"temp_seg_{i}.wav"
            if generate_audio(sentence, seg_audio_path):
                temp_files.append(seg_audio_path)
                seg_audio = AudioFileClip(seg_audio_path)
                audio_clips.append(seg_audio)
                
                # Generate Caption
                # Position text in lower third or center
                caption_clip = create_caption_clip(sentence, seg_audio.duration, fontsize=70)
                caption_clips.append(caption_clip)
            else:
                print(f"⚠️ Skipping sentence due to audio generation failure: {sentence}")
            
        # Concatenate Audio
        final_voice = concatenate_audioclips(audio_clips)
        
        # Concatenate Captions (VideoClips)
        final_captions = concatenate_videoclips(caption_clips)
        
        # --- NEW LOGIC: DELAY COMMENTARY ---
        # "Let the video play first"
        intro_duration = 5.0  # 5 seconds of original video only
        
        # Adjust video duration
        total_duration = intro_duration + final_voice.duration
        
        # STRICT CONSTRAINT: Max 60 seconds (safe 59s)
        if total_duration > 59:
            print(f"⚠️ Video too long ({total_duration:.2f}s). Trimming to 59s.")
            total_duration = 59.0
            
        # 3. Assemble Visuals
        if original_clip.duration < total_duration:
            # Loop video
            loops = int(total_duration / original_clip.duration) + 1
            visual_clip = concatenate_videoclips([original_clip] * loops)
            visual_clip = visual_clip.subclip(0, total_duration)
        else:
            visual_clip = original_clip.subclip(0, total_duration)
            
        # 4. Background Music
        bg_music = None
        music_path = os.path.join(os.getcwd(), "background_music.mp3")
        
        if os.path.exists(music_path):
            try:
                bg_music = AudioFileClip(music_path)
                
                # BG Music starts at intro_duration
                bg_duration = total_duration - intro_duration
                if bg_duration > 0:
                     if bg_music.duration < bg_duration:
                         bg_music = vfx.loop(bg_music, duration=bg_duration + 1)
                     else:
                         bg_music = bg_music.subclip(0, bg_duration)
                     
                     bg_music = bg_music.volumex(0.15).set_start(intro_duration)
                     print("🎵 Background music added.")
                else:
                    bg_music = None
            except Exception as e:
                print(f"⚠️ Could not load background music: {e}")
                bg_music = None
        else:
             print("⚠️ No 'background_music.mp3' found in current directory. Skipping music.")
        
        # 5. Assemble Final Video with Delays
        
        # Shift Captions
        final_captions = final_captions.set_start(intro_duration).set_position("center")
        
        # Shift Voice
        final_voice = final_voice.set_start(intro_duration)
        
        # Overlay Captions
        final_video = CompositeVideoClip([visual_clip, final_captions])
        
        # Mix Audio
        # 0-5s: Original Audio (100%)
        # 5s-End: Original Audio (10%) + Voice (100%) + BG (15%)
        
        audios = []
        
        # Original Audio Split
        original_audio = visual_clip.audio
        if original_audio:
            if total_duration > intro_duration:
                # Part 1: Intro (Full Volume)
                part1 = original_audio.subclip(0, intro_duration)
                
                # Part 2: Commentary Section (Low Volume)
                part2 = original_audio.subclip(intro_duration, total_duration).volumex(0.1)
                
                # Recombine
                mixed_original = concatenate_audioclips([part1, part2])
                audios.append(mixed_original)
            else:
                audios.append(original_audio)
        
        # Add Voice & BG
        audios.append(final_voice)
        if bg_music:
            audios.append(bg_music)
            
        final_audio = CompositeAudioClip(audios)
        
        # Force duration to avoid floating point errors extending beyond video
        final_audio = final_audio.set_duration(total_duration)
        final_video = final_video.set_audio(final_audio).set_duration(total_duration)
        
        final_video.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac", 
            fps=24,
            temp_audiofile="temp-audio-event.m4a",
            remove_temp=True,
            threads=1,
            ffmpeg_params=["-pix_fmt", "yuv420p"]
        )
        print(f"✅ Video saved to: {output_path}")
        final_video.close()
        return output_path
        
    except Exception as e:
        print(f"❌ Editing Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        try:
            original_clip.close()
            for clip in audio_clips: clip.close()
            # Clean up temp files
            for f in temp_files:
                if os.path.exists(f): os.remove(f)
        except:
            pass

def process_event_video(topic, output_file="final_output.mp4", model="llama3"):
    # 1. Search & Download
    v_path, title, desc = search_and_download_event(topic)
    if not v_path:
        return "Failed to download video."
        
    # 2. Generate Commentary
    commentary = generate_commentary(topic, title, desc, model)
    
    # 3. Edit Video (Now handles audio generation internally for syncing)
    out_path = create_reaction_video(v_path, commentary, output_file)
    
    return out_path
