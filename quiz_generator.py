import os
import random
import time
import re
import textwrap
import tempfile
import subprocess
import shutil
import requests
import html
import wave
import struct
import math
from script_generator import ScriptGenerator
from PIL import Image, ImageDraw, ImageFont
# MoviePy imports with proper submodule paths
try:
    # Try MoviePy 2.x import style first
    from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_audioclips, vfx
except ImportError:
    # Fallback to MoviePy 1.x import style
    try:
        from moviepy.video.VideoClip import ImageClip
        from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
        from moviepy.video.compositing.concatenate import concatenate_videoclips
        from moviepy.audio.AudioClip import CompositeAudioClip
        from moviepy.audio.compositing.CompositeAudioClip import CompositeAudioClip
        from moviepy.audio.compositing.concatenate import concatenate_audioclips
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        from moviepy.video.fx import vfx
    except ImportError:
        # Final fallback - try direct import
        try:
            from moviepy import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_audioclips, vfx
        except ImportError:
            # If all imports fail, provide helpful error
            raise ImportError("Could not import MoviePy components. Please check your MoviePy installation.")
from tiktok_voice import tts, Voice
from tts_chatterbox import generate_cloned_audio
from duckduckgo_search import DDGS

# Default colors
BG_COLOR_PINK = (255, 192, 203) # Pink
BG_COLOR_BLUE = (137, 207, 240) # Baby Blue
GRID_COLOR = (255, 220, 230)
TEXT_COLOR = (255, 255, 0) # Yellow
STROKE_COLOR = (0, 0, 0)   # Black

def get_ffmpeg_path() -> str:
    """Return local ffmpeg.exe if present, otherwise use ffmpeg from PATH."""
    local = os.path.join(os.getcwd(), "ffmpeg.exe")
    return os.path.abspath(local) if os.path.isfile(local) else "ffmpeg"

def post_process_audio(input_path: str) -> bool:
    """Apply gentle FFmpeg filters to smooth and calm the voice."""
    try:
        ffmpeg = get_ffmpeg_path()
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_calm{ext or '.mp3'}"

        filter_chain = (
            "acompressor=ratio=2:threshold=-18dB:attack=10:release=250:makeup=1.5,"
            "equalizer=f=6000:t=h:w=250:g=-4,"
            "highpass=f=60,"
            "loudnorm=I=-20:LRA=7:TP=-2.0"
        )

        cmd = [
            ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error",
            "-y", "-i", input_path,
            "-af", filter_chain,
            "-c:a", "libmp3lame", "-b:a", "160k",
            output_path
        ]

        subprocess.run(cmd, check=True)

        try:
            os.replace(output_path, input_path)
        except Exception:
            shutil.copyfile(output_path, input_path)
            os.remove(output_path)

        return True
    except Exception as e:
        print(f"⚠️ FFmpeg post-process failed: {e}")
        return False

def download_image_from_ddg(query, filename):
    """Downloads an image from DuckDuckGo."""
    print(f"🔍 Searching image for: {query}")
    try:
        # Use DDGS context manager
        with DDGS() as ddgs:
            # Fetch 1 image
            results = list(ddgs.images(query, max_results=1))
            if results:
                image_url = results[0]['image']
                # Download
                response = requests.get(image_url, stream=True, timeout=10)
                if response.status_code == 200:
                    with open(filename, 'wb') as f:
                        response.raw.decode_content = True
                        shutil.copyfileobj(response.raw, f)
                    return filename
    except Exception as e:
        print(f"⚠️ Image Download Failed for '{query}': {e}")
    return None

def generate_audio(text, filename, voice=Voice.FEMALE_EMOTIONAL, reference_audio=None):
    """Generates TTS audio using TikTok Voice and applies post-processing. Supports cloning if reference provided."""
    
    # 0. Try Cloning first if reference provided
    if reference_audio and os.path.exists(reference_audio):
        try:
            if os.path.exists(filename):
                try: os.remove(filename)
                except: pass
                
            print(f"🎙️ Attempting voice cloning using {reference_audio}...")
            if generate_cloned_audio(text, filename, reference_audio):
                # Post-process cloned audio too? Maybe yes to normalize loudness
                if post_process_audio(filename):
                    return filename
                return filename
            else:
                print("⚠️ Cloning failed. Falling back to TikTok TTS.")
        except Exception as e:
            print(f"⚠️ Cloning Error: {e}")

    for attempt in range(3):
        try:
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
            
            tts(text, voice, filename)
            
            # 1. Check if file exists and has size
            if not os.path.exists(filename) or os.path.getsize(filename) < 100:
                print(f"⚠️ TTS attempt {attempt+1} failed: Invalid file size ({filename}).")
                time.sleep(1.5)
                continue
                
            # 2. Check for text error content in file (TikTok API sometimes writes error as text)
            try:
                with open(filename, 'rb') as f:
                    header = f.read(10)
                    # MP3 sync word is usually 0xFFE0 (first 11 bits set). ID3 tag starts with 'ID3'.
                    # Error text usually starts with "{" or "<".
                    if header.startswith(b'{') or header.startswith(b'<') or b'error' in header.lower():
                        print(f"⚠️ TTS attempt {attempt+1} failed: File contains error text.")
                        time.sleep(1.5)
                        continue
            except Exception:
                pass

            # 3. Post-process
            if post_process_audio(filename):
                return filename
            else:
                # If post-process failed but file exists, it might be bad.
                # We retry to be safe.
                print(f"⚠️ Post-processing failed for {filename}. Retrying...")
                time.sleep(1.5)
                continue
                
        except Exception as e:
            print(f"❌ TTS Error (Attempt {attempt+1}): {e}")
            time.sleep(1.5)
            
    print(f"❌ All TTS attempts failed for text: {text[:20]}...")
    return None

USED_QUESTIONS_FILE = "used_quiz_questions.txt"
USED_LONG_QUESTIONS_FILE = "used_long_quiz_questions.txt"

def load_used_questions(file_path=USED_QUESTIONS_FILE):
    if not os.path.exists(file_path):
        return set()
    with open(file_path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def normalize_question_text(text):
    """Normalize text for consistent comparison."""
    return text.replace("\n", " ").strip()

def save_used_questions(new_questions, file_path=USED_QUESTIONS_FILE):
    """Append new questions to the file."""
    with open(file_path, "a", encoding="utf-8") as f:
        for q in new_questions:
            clean_q = normalize_question_text(q)
            if clean_q:
                f.write(clean_q + "\n")

def fetch_questions_from_api(amount=20):
    """Fetch questions from Open Trivia DB: Mostly Easy, 1 Hard."""
    questions = []
    used_qs = load_used_questions(USED_QUESTIONS_FILE)
    
    # Phrases that imply multiple choice options are being read or displayed
    forbidden_phrases = [
        "which of these", "which of the following", "which one", 
        "following options", "select the", "choose the"
    ]

    def process_results(results, limit=None):
        valid = []
        for item in results:
            q_raw = html.unescape(item['question'])
            a = html.unescape(item['correct_answer'])
            
            q_norm = normalize_question_text(q_raw)
            
            # Check if used
            if q_norm in used_qs:
                continue
            
            # Check for forbidden phrases
            q_lower = q_norm.lower()
            if any(phrase in q_lower for phrase in forbidden_phrases):
                continue
                
            valid.append({'q': q_norm, 'a': a})
            if limit and len(valid) >= limit:
                break
        return valid

    try:
        # 1. Fetch EASY questions
        # We fetch significantly more to account for duplicates and filtering
        easy_qs = []
        attempts = 0
        while len(easy_qs) < amount and attempts < 3:
            url_easy = f"https://opentdb.com/api.php?amount=50&category=9&type=multiple&difficulty=easy"
            try:
                resp_easy = requests.get(url_easy, timeout=10)
                if resp_easy.status_code == 200:
                    data_easy = resp_easy.json()
                    if data_easy['response_code'] == 0:
                        new_easy = process_results(data_easy['results'])
                        # Add only unique ones not already in easy_qs
                        for q in new_easy:
                            if not any(eq['q'] == q['q'] for eq in easy_qs):
                                easy_qs.append(q)
            except Exception as e:
                print(f"⚠️ API Fetch attempt {attempts+1} failed: {e}")
            
            attempts += 1
            time.sleep(1.0) # Be polite

        # 2. Fetch HARD questions (Fetch a few)
        hard_qs = []
        url_hard = f"https://opentdb.com/api.php?amount=10&category=9&type=multiple&difficulty=hard"
        try:
            resp_hard = requests.get(url_hard, timeout=10)
            if resp_hard.status_code == 200:
                data_hard = resp_hard.json()
                if data_hard['response_code'] == 0:
                    hard_qs = process_results(data_hard['results'], limit=1)
        except Exception:
            pass

        # 3. Combine: [Easy, Easy, Easy, Hard, Easy...]
        # We place the hard question at index 3 (4th question) if possible, 
        # so it appears towards the end of a typical 4-5 question video.
        
        final_list = []
        # Add up to 3 easy
        final_list.extend(easy_qs[:3])
        # Add 1 hard (if available)
        if hard_qs:
            final_list.extend(hard_qs)
        # Add remaining easy
        final_list.extend(easy_qs[3:])
        
        # Check if we have enough
        if len(final_list) < amount:
            try:
                print(f"⚠️ API only returned {len(final_list)}/{amount}. Filling with Llama (Local AI)...")
                gen = ScriptGenerator(use_ollama=True)
                needed = amount - len(final_list)
                # Request a few more just in case
                llama_qs = gen.generate_quiz_questions(amount=needed + 2)
                if llama_qs:
                     final_list.extend(llama_qs)
            except Exception as e:
                print(f"⚠️ Llama fill failed: {e}")
        
        return final_list[:amount]

    except Exception as e:
        print(f"⚠️ Failed to fetch questions from API: {e}")
        # Fallback questions (Llama)
        try:
            print("⚠️ Using Llama fallback...")
            gen = ScriptGenerator(use_ollama=True)
            
            # Chunked generation
            llama_qs_total = []
            chunk_size = 5
            
            while len(llama_qs_total) < amount:
                batch_size = min(chunk_size, amount - len(llama_qs_total))
                print(f"   Generating batch of {batch_size} questions...")
                batch_qs = gen.generate_quiz_questions(amount=batch_size)
                if batch_qs:
                    llama_qs_total.extend(batch_qs)
                else:
                    break
            
            if llama_qs_total:
                return llama_qs_total
        except Exception as e2:
            print(f"⚠️ Llama fallback also failed: {e2}")

        # Hardcoded fallback if Llama fails or returns empty
        return [
            {"q": "What is the capital of France?", "a": "Paris"},
            {"q": "Who painted the Mona Lisa?", "a": "Leonardo da Vinci"},
            {"q": "What is the largest planet in our solar system?", "a": "Jupiter"},
            {"q": "What is the chemical symbol for Gold?", "a": "Au"},
            {"q": "Which continent is the Sahara Desert located in?", "a": "Africa"}
        ]

def fetch_long_questions_from_api(amount=20):
    """Fetch Multiple Choice questions for long video mode."""
    used_qs = load_used_questions(USED_LONG_QUESTIONS_FILE)
    final_questions = []
    
    # We want a mix of difficulties, maybe mostly medium/hard for long videos?
    # User said "more engaging", "4 choices", "10 seconds thinking".
    # Let's try to get a mix.
    
    attempts = 0
    while len(final_questions) < amount and attempts < 5:
        # Fetch 50 at a time
        url = f"https://opentdb.com/api.php?amount=50&type=multiple" 
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data['response_code'] == 0:
                    for item in data['results']:
                        q_raw = html.unescape(item['question'])
                        q_norm = normalize_question_text(q_raw)
                        
                        if q_norm in used_qs:
                            continue
                        
                        # Check if already in current batch
                        if any(fq['q'] == q_norm for fq in final_questions):
                            continue

                        correct = html.unescape(item['correct_answer'])
                        incorrect = [html.unescape(ans) for ans in item['incorrect_answers']]
                        
                        # Combine options and shuffle
                        options = incorrect + [correct]
                        random.shuffle(options)
                        
                        # Find new index of correct answer
                        correct_idx = options.index(correct)
                        
                        final_questions.append({
                            'q': q_norm,
                            'a': correct,
                            'options': options,
                            'correct_idx': correct_idx,
                            'difficulty': item['difficulty']
                        })
                        
                        if len(final_questions) >= amount:
                            break
            
        except Exception as e:
            print(f"⚠️ Long API Fetch attempt {attempts+1} failed: {e}")
            
        attempts += 1
        time.sleep(1.0)
        
    return final_questions

def create_landscape_slide(text, options=None, correct_idx=None, width=1920, height=1080, type="question", show_answer=False):
    """Creates a landscape 16:9 slide with options."""
    img = create_background(width, height) # We'll need to update create_background to handle size or just use Image.new here
    
    # Override create_background logic for landscape if needed, but the existing one takes w,h
    # Re-drawing background to be safe as the existing one draws grid based on hardcoded step maybe?
    # Existing create_background uses BG_COLOR and draws grid.
    
    draw = ImageDraw.Draw(img)
    
    # Fonts
    try:
        font_large = ImageFont.truetype("arialbd.ttf", 90)
        font_option = ImageFont.truetype("arial.ttf", 60)
        font_header = ImageFont.truetype("arialbd.ttf", 120)
    except IOError:
        font_large = ImageFont.load_default()
        font_option = ImageFont.load_default()
        font_header = ImageFont.load_default()

    # Draw Title/Question
    # Split text into lines
    lines = textwrap.wrap(text, width=40)
    y_text = 150
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_large)
        text_w = bbox[2] - bbox[0]
        x_text = (width - text_w) // 2
        draw_text_with_outline(draw, (x_text, y_text), line, font_large, TEXT_COLOR, STROKE_COLOR, 3)
        y_text += bbox[3] - bbox[1] + 20

    # Draw Options
    if options:
        y_start = 500
        # 2x2 Grid or List? List is easier to read.
        # Let's do a 2x2 grid for "engaging" look or centered list.
        # 4 options.
        
        # Option Box Config
        box_w = 800
        box_h = 100
        margin_x = 100
        margin_y = 50
        
        # Coordinates for 2 columns
        # Col 1: X = width/2 - box_w - margin_x/2
        # Col 2: X = width/2 + margin_x/2
        
        positions = [
            (width//2 - box_w - 20, y_start),          # Top Left
            (width//2 + 20, y_start),                  # Top Right
            (width//2 - box_w - 20, y_start + box_h + 30), # Bottom Left
            (width//2 + 20, y_start + box_h + 30)      # Bottom Right
        ]
        
        labels = ["A", "B", "C", "D"]
        
        for i, option in enumerate(options):
            if i >= 4: break
            
            x, y = positions[i]
            
            # Determine Color
            fill_color = (255, 255, 255) # White box
            text_col = (0, 0, 0)
            
            if show_answer and i == correct_idx:
                fill_color = (0, 255, 0) # Green for correct
            
            # Draw Box
            draw.rectangle([x, y, x+box_w, y+box_h], fill=fill_color, outline=(0,0,0), width=4)
            
            # Draw Text
            opt_text = f"{labels[i]}. {option}"
            bbox = draw.textbbox((0, 0), opt_text, font=font_option)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            
            # Center text in box
            tx = x + (box_w - tw) // 2
            ty = y + (box_h - th) // 2
            
            draw.text((tx, ty), opt_text, font=font_option, fill=text_col)

    # Save
    fd, filename = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(filename)
    return filename

def generate_beep_wav(filename, duration=0.1, freq=1000):
    """Generate a sine wave beep using standard library."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1) # mono
        obj.setsampwidth(2) # 2 bytes (16 bit)
        obj.setframerate(sample_rate)
        
        data = []
        for i in range(n_samples):
            value = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * freq * i / sample_rate))
            data.append(struct.pack('<h', value))
            
        obj.writeframes(b''.join(data))
    return filename

def generate_whoosh_wav(filename, duration=0.5):
    """Generate a white noise whoosh."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1)
        obj.setsampwidth(2)
        obj.setframerate(sample_rate)
        data = []
        for i in range(n_samples):
            # Simple white noise with envelope
            noise = random.uniform(-1, 1)
            # Envelope: fade in, fade out
            t = i / n_samples
            envelope = 4 * t * (1 - t) # Parabolic
            value = int(32767.0 * 0.3 * noise * envelope)
            data.append(struct.pack('<h', value))
        obj.writeframes(b''.join(data))
    return filename

def generate_ding_wav(filename, duration=1.0, freq=2000):
    """Generate a high pitch ding with decay."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1)
        obj.setsampwidth(2)
        obj.setframerate(sample_rate)
        data = []
        for i in range(n_samples):
            t = i / sample_rate
            # Exponential decay
            envelope = math.exp(-5 * t)
            value = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * freq * t) * envelope)
            data.append(struct.pack('<h', value))
        obj.writeframes(b''.join(data))
    return filename

def create_countdown_slide(base_img_path, number):
    """Overlay a large number on the existing slide."""
    with Image.open(base_img_path) as img:
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        try:
            font = ImageFont.truetype("arialbd.ttf", 300)
        except:
            font = ImageFont.load_default()
            
        text = str(number)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (width - text_w) // 2
        y = (height - text_h) // 2
        
        # Stroke (Black)
        stroke_width = 8
        for adj in range(-stroke_width, stroke_width+1):
            for adj2 in range(-stroke_width, stroke_width+1):
                draw.text((x+adj, y+adj2), text, font=font, fill=(0,0,0))
        
        # Fill (White)
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
        
        fd, filename = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(filename)
        return filename

def generate_ding_wav(filename, duration=0.5, freq=800):
    """Generate a 'ding' sound (sine wave with decay)."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1)
        obj.setsampwidth(2)
        obj.setframerate(sample_rate)
        
        data = []
        for i in range(n_samples):
            t = i / sample_rate
            # Decay envelope: e^(-5t)
            envelope = math.exp(-5 * t)
            value = int(32767.0 * 0.5 * envelope * math.sin(2.0 * math.pi * freq * t))
            data.append(struct.pack('<h', value))
            
        obj.writeframes(b''.join(data))
    return filename

def generate_whoosh_wav(filename, duration=0.3):
    """Generate a 'whoosh' sound (white noise with rise/fall envelope)."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1)
        obj.setsampwidth(2)
        obj.setframerate(sample_rate)
        
        data = []
        for i in range(n_samples):
            t = i / duration
            # Rise and fall envelope (sine squared)
            envelope = math.sin(math.pi * t) ** 2
            # White noise
            noise = random.uniform(-1, 1)
            value = int(32767.0 * 0.3 * envelope * noise)
            data.append(struct.pack('<h', value))
            
        obj.writeframes(b''.join(data))
    return filename

def strip_emojis(text):
    """Removes emojis and cleans text."""
    # Remove specific emojis
    remove_list = ["❤️", "🔥", "🧠", "😱", "🍔", "🏆", "🤔", "🍕", "👫", "💄", "🎮", "💅", "👗", "👠", "👛", "⚽", "🍺"]
    for char in remove_list:
        text = text.replace(char, "")
    return text.strip()

def draw_heart(draw, x, y, size, color=(255, 0, 0)):
    """Draws a smooth heart shape using parametric equation."""
    # Parametric heart formula
    # x = 16 * sin(t)^3
    # y = 13 * cos(t) - 5 * cos(2*t) - 2 * cos(3*t) - cos(4*t)
    
    scale = size / 35.0
    points = []
    steps = 100
    
    for i in range(steps):
        t = (i / steps) * 2 * math.pi
        
        # Calculate raw coords
        raw_x = 16 * math.pow(math.sin(t), 3)
        raw_y = 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)
        
        # Transform to screen coords (Flip Y because screen Y is down)
        px = x + raw_x * scale
        py = y - raw_y * scale
        
        points.append((px, py))
        
    draw.polygon(points, fill=color, outline=(0,0,0), width=4)

def draw_fire(draw, x, y, size):
    """Draws a flame shape."""
    color_outer = (255, 69, 0)
    color_inner = (255, 255, 0)
    
    # Outer Flame
    draw.ellipse([x - size//2, y, x + size//2, y + size], fill=color_outer)
    draw.polygon([(x - size//2, y + size//2), (x + size//2, y + size//2), (x, y - size//2)], fill=color_outer)
    
    # Inner Flame
    s = size // 2
    draw.ellipse([x - s//2, y + s//2, x + s//2, y + s + s//2], fill=color_inner)
    draw.polygon([(x - s//2, y + s), (x + s//2, y + s), (x, y)], fill=color_inner)

def draw_star(draw, x, y, size, color=(255, 215, 0)):
    """Draws a star."""
    points = []
    for i in range(10):
        angle = i * 36 * math.pi / 180 - math.pi / 2
        r = size if i % 2 == 0 else size * 0.4
        px = x + r * math.cos(angle)
        py = y + r * math.sin(angle)
        points.append((px, py))
    draw.polygon(points, fill=color, outline=(0,0,0), width=3)

def create_background(width=1080, height=1920, theme_color=None):
    """Creates a gradient background with grid."""
    
    if theme_color:
        top_color = theme_color
        # Create a complementary bottom color (shift hue or darken)
        # Simple darken: 0.7x
        bottom_color = (int(theme_color[0]*0.7), int(theme_color[1]*0.7), int(theme_color[2]*0.7))
        # Or shift towards purple/blue for aesthetic?
        # If blue (137, 207, 240) -> Darker Blue
        # If pink (255, 192, 203) -> Darker Pink/Red
    else:
        # Default Gradient: Pink to Purple
        top_color = (255, 105, 180) # Hot Pink
        bottom_color = (147, 112, 219) # Medium Purple
    
    img = Image.new('RGB', (width, height), top_color)
    draw = ImageDraw.Draw(img)
    
    # Draw Gradient
    for y in range(height):
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * y / height)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * y / height)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Draw grid (white with low opacity? PIL doesn't support alpha on RGB draw easily without composition)
    # We'll just use a light color for grid lines
    grid_color = (255, 255, 255)
    
    step = 100
    # Draw thicker, more sparse grid for "modern" look
    for x in range(0, width, step):
        width_line = 1 if x % 200 != 0 else 3
        draw.line([(x, 0), (x, height)], fill=grid_color, width=width_line)
    for y in range(0, height, step):
        width_line = 1 if y % 200 != 0 else 3
        draw.line([(0, y), (width, y)], fill=grid_color, width=width_line)
        
    return img

def draw_text_with_outline(draw, position, text, font, fill_color, outline_color, outline_width=2):
    x, y = position
    # Draw outline
    for adj in range(-outline_width, outline_width+1):
        for adj2 in range(-outline_width, outline_width+1):
            draw.text((x+adj, y+adj2), text, font=font, fill=outline_color)
    # Draw text
    draw.text((x, y), text, font=font, fill=fill_color)

def create_slide(text, subtext=None, width=1080, height=1920, type="question", theme_color=None, image_path=None):
    """Creates a slide image."""
    img = create_background(width, height, theme_color=theme_color)
    draw = ImageDraw.Draw(img)
    
    # Detect icons BEFORE stripping
    show_heart = "❤️" in text or "COUPLES" in text.upper() or "PARTNER" in text.upper()
    show_fire = "🔥" in text or "HARD" in text.upper() or "TEST" in text.upper()
    show_star = "🌟" in text or "WIN" in text.upper()
    
    # Clean text
    text = strip_emojis(text)
    if subtext:
        subtext = strip_emojis(subtext)
    
    # Load fonts (try to find a bold font)
    try:
        font_large = ImageFont.truetype("arialbd.ttf", 80)
        font_small = ImageFont.truetype("arial.ttf", 50)
        font_level = ImageFont.truetype("arialbd.ttf", 60)
    except IOError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_level = ImageFont.load_default()

    # Draw Title/Question
    # Increase width for wrapping to avoid too many short lines
    lines = textwrap.wrap(text, width=25)
    
    # Layout adjustments
    y_text = 400 # Default start
    if image_path:
        y_text = 150 # Move text up significantly if image present
    
    # Draw Icons if detected (Above text)
    icon_y = y_text - 120
    icon_size = 100
    if show_heart:
        draw_heart(draw, width//2, icon_y, icon_size)
    elif show_fire:
        draw_fire(draw, width//2, icon_y, icon_size)
    elif show_star:
        draw_star(draw, width//2, icon_y, icon_size)

    # Draw Text
    for line in lines:
        # Get text size (bbox)
        bbox = draw.textbbox((0, 0), line, font=font_large)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        x_text = (width - text_w) // 2
        draw_text_with_outline(draw, (x_text, y_text), line, font_large, TEXT_COLOR, STROKE_COLOR, 5)
        y_text += text_h + 20

    # Draw Image if provided
    if image_path and os.path.exists(image_path):
        try:
            with Image.open(image_path) as q_img:
                q_img = q_img.convert("RGBA")
                
                # Resize to fit max width/height
                max_w = 800
                max_h = 600
                
                # Calculate aspect ratio
                ratio = min(max_w / q_img.width, max_h / q_img.height)
                new_size = (int(q_img.width * ratio), int(q_img.height * ratio))
                q_img = q_img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Center horizontally
                img_x = (width - new_size[0]) // 2
                # Place below text (y_text is currently at end of text)
                img_y = y_text + 50
                
                # Draw border/shadow
                shadow = Image.new('RGBA', (new_size[0]+20, new_size[1]+20), (0,0,0,100))
                img.paste(shadow, (img_x-10, img_y+10), shadow)
                
                # Paste image (handle transparency)
                img.paste(q_img, (img_x, img_y), q_img)
                
                # Update y_text to be below image for subtext
                y_text = img_y + new_size[1] + 50
        except Exception as e:
            print(f"⚠️ Failed to load image {image_path}: {e}")

    # Draw Subtext/Answer if present
    if subtext:
        # If no image, add some padding
        if not image_path:
            y_text += 100
            
        bbox = draw.textbbox((0, 0), subtext, font=font_small)
        text_w = bbox[2] - bbox[0]
        x_text = (width - text_w) // 2
        draw_text_with_outline(draw, (x_text, y_text), subtext, font_small, (255, 255, 255), STROKE_COLOR, 4)

    # Draw Level (Bottom)
    level_text = "Level: HARD"
    bbox = draw.textbbox((0, 0), level_text, font=font_level)
    text_w = bbox[2] - bbox[0]
    draw_text_with_outline(draw, ((width - text_w) // 2, height - 200), level_text, font_level, (255, 0, 0), STROKE_COLOR, 2)
    
    # Save to temp file
    fd, filename = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(filename)
    return filename

# Funny replacements dictionary
FUNNY_REPLACEMENTS = {
    "shakespeare": "Cockspear",
    "france": "Pants",
    "paris": "Penis",
    "uranus": "Your Anus",
    "six": "Sex",
    "cucumber": "Cucum-bear",
    "beach": "Bitch",
    "sheet": "Shit",
    "happiness": "Penis",
    "peace": "Piss",
    "pianist": "Penis",
    "cocktail": "Cock-tail",
    "dickens": "Dick-ins",
    "virginia": "Vagina",
    "banana": "Boner-na",
    "ball": "Ball-sack",
}

def get_potential_replacements(text, q_idx):
    """Scan text for replacement candidates (Dict or Heuristic)."""
    candidates = []
    words = text.split()
    for i, word in enumerate(words):
        clean = word.lower().strip(",.!?")
        
        # 1. Dictionary Check
        if clean in FUNNY_REPLACEMENTS:
            candidates.append({
                'q_idx': q_idx, 
                'word_idx': i, 
                'original': word,
                'replacement': word.replace(clean, FUNNY_REPLACEMENTS[clean], 1) if clean in word else FUNNY_REPLACEMENTS[clean]
            })
            continue
            
        # 2. Heuristic Checks (The "Unlimited" Logic)
        
        # Ends with 'nal' -> '-anal' (e.g. final -> fin-anal)
        if clean.endswith("nal") and len(clean) > 3:
            rep = word.replace("nal", "-anal")
            candidates.append({'q_idx': q_idx, 'word_idx': i, 'original': word, 'replacement': rep})
            continue
        
        # Contains 'ass' (e.g. class -> cl-ass)
        if "ass" in clean and clean != "ass" and len(clean) > 3:
            rep = word.replace("ass", "-ass")
            candidates.append({'q_idx': q_idx, 'word_idx': i, 'original': word, 'replacement': rep})
            continue
            
        # Starts with 'con' -> 'cunt' (e.g. contact -> cunt-act)
        if clean.startswith("con") and len(clean) > 3:
            rep = word.replace("con", "cunt", 1)
            candidates.append({'q_idx': q_idx, 'word_idx': i, 'original': word, 'replacement': rep})
            continue
            
        # Starts with 'pen' -> 'penis' (e.g. pencil -> penis-il)
        if clean.startswith("pen") and len(clean) > 3:
            rep = word.replace("pen", "penis", 1)
            candidates.append({'q_idx': q_idx, 'word_idx': i, 'original': word, 'replacement': rep})
            continue

        # Ends with 'cock' -> '-cock' (e.g. peacock -> pea-cock)
        if clean.endswith("cock") and len(clean) > 4:
            rep = word.replace("cock", "-cock")
            candidates.append({'q_idx': q_idx, 'word_idx': i, 'original': word, 'replacement': rep})
            continue

    return candidates

def apply_replacement(text, word_idx, replacement):
    """Apply the replacement to the specific word index."""
    words = text.split()
    if 0 <= word_idx < len(words):
        words[word_idx] = replacement
    return " ".join(words)

def generate_youtube_metadata_ai(target_gender, is_couples, questions=None, category="general"):
    """
    Generates a viral YouTube title and description using Ollama.
    """
    title = ""
    desc = ""
    
    try:
        # Check if Ollama is available via ScriptGenerator
        gen = ScriptGenerator(use_ollama=True)
        gen.ensure_service_running()
        
        system_prompt = (
            "You are a viral YouTube Shorts marketing expert. "
            "Your goal is to create high-CTR (Click Through Rate) titles and descriptions."
        )
        
        target_audience = "Boyfriend" if target_gender == "male" else "Girlfriend"
        quiz_type = "Couples Quiz" if is_couples else "General Knowledge Quiz"
        
        if category != "general":
            quiz_type = f"{category.title()} {quiz_type}"
        
        q_context = ""
        if questions:
            # Add a few questions for context to make the title unique
            sample_qs = [q['q'] for q in questions[:3]]
            q_context = "The video contains these specific questions:\n- " + "\n- ".join(sample_qs)

        user_prompt = f"""
        Generate a UNIQUE and VIRAL YouTube Shorts title and description for a {quiz_type} video.
        
        Context:
        - Target Audience: {target_audience} (The viewer should tag/ask their {target_audience})
        - Video Style: Fast-paced, fun, engaging, viral.
        - Category: {category.upper()} (Make sure the title reflects this vibe!)
        - {q_context}
        
        Requirements:
        1. Title: Short, punchy, clickbait (e.g., "99% Fail This!", "Test Your BF!", "Can He Answer This?"). Max 60 chars. Do NOT use emojis in the title. Make it specific to the questions if possible.
        2. Description: 2-3 sentences challenging the viewer. Include 5-8 viral hashtags.
        3. Output Format strictly as follows:
           TITLE: <title>
           DESCRIPTION: <description>
        """
        
        import requests
        url = f"{gen.ollama_url}/api/chat"
        payload = {
            "model": gen.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            content = response.json().get("message", {}).get("content", "").strip()
            
            lines = content.split('\n')
            for line in lines:
                if line.strip().upper().startswith("TITLE:"):
                    title = line.strip()[6:].strip()
                elif line.strip().upper().startswith("DESCRIPTION:"):
                    desc = line.strip()[12:].strip()
            
            # If description spans multiple lines after the marker
            if "DESCRIPTION:" in content:
                desc_part = content.split("DESCRIPTION:")[1].strip()
                desc = desc_part
            
    except Exception as e:
        print(f"⚠️ Metadata Generation Failed: {e}")
        
    # Fallback if AI fails or returns empty
    if not title or not desc:
        if is_couples:
            if target_gender == "male":
                 title = "COUPLES QUIZ: Test Your Boyfriend!"
                 desc = "Ask your boyfriend these questions and see if he knows you! 💄\n\n#couplesquiz #boyfriendtest #relationshipgoals #quiz"
            else:
                 title = "COUPLES QUIZ: Test Your Girlfriend!"
                 desc = "Ask your girlfriend these questions and see if she knows you! ⚽\n\n#couplesquiz #girlfriendtest #relationshipgoals #quiz"
        else:
             title = "General Knowledge Quiz Challenge!"
             desc = "Can you answer these questions? Comment your score! 👇\n\n#quiz #trivia #knowledge"
             
    return title, desc

def generate_quiz_video(questions=None, output_path="quiz_output.mp4", auto_mode=False):
    """
    questions: list of dict {'q': 'Question?', 'a': 'Answer'}
    auto_mode: If True, fetches questions automatically and fits them into 30-58s duration.
    """
    clips = []
    temp_files = []
    final_questions_used = []

    try:
        # Generate Common SFX
        whoosh_file = f"temp_whoosh_{random.randint(0,1000)}.wav"
        generate_whoosh_wav(whoosh_file)
        temp_files.append(whoosh_file)
        whoosh_audio = AudioFileClip(whoosh_file)

        ding_file = f"temp_ding_{random.randint(0,1000)}.wav"
        generate_ding_wav(ding_file)
        temp_files.append(ding_file)
        ding_audio = AudioFileClip(ding_file)

        # Determine Video Theme/Gender
        # Randomly decide if this video is for Him or Her
        target_gender = random.choice(["male", "female"])
        
        # Determine Quiz Category (Diversity Request)
        # Weights: General (40%), Deep (20%), Spicy (20%), Funny (10%), Hard (10%)
        categories = ["general", "deep", "spicy", "funny", "hard"]
        weights = [0.4, 0.2, 0.2, 0.1, 0.1]
        target_category = random.choices(categories, weights=weights, k=1)[0]
        
        print(f"DEBUG: Generating {target_category.upper()} quiz for {target_gender}")
        
        current_theme_color = BG_COLOR_PINK
        current_voice_ref = None
        
        # Intro
        if target_gender == "male":
            # Stakes for Him
            male_stakes = [
                "he buys you a new mascara",
                "he takes you to Sephora",
                "he buys you flowers",
                "he takes you to dinner",
                "he owes you a massage"
            ]
            stake = random.choice(male_stakes)
            
            # Special Intro for Special Categories
            cat_text = ""
            if target_category != "general":
                cat_text = f"{target_category.upper()} EDITION!\n"
                
            intro_text = f"COUPLES QUIZ! ❤️\n{cat_text}with Ariana Grande\nIf he fails:\n{stake.replace('he ', '').title()}! 💄"
            
            # Special Audio for Special Categories
            audio_cat_text = ""
            if target_category != "general":
                audio_cat_text = f"{target_category} Edition! "
                
            intro_audio_text = f"Couples Quiz {audio_cat_text}with Ariana Grande! If he gets one wrong, {stake}!"
            

            current_theme_color = BG_COLOR_PINK
            # Try to find Ariana Grande reference
            possible_paths = [
                os.path.join("assets", "ariana_grande.mp3"),
                os.path.join("assets", "ariana_grande.wav"),
                os.path.join("voices", "ariana_grande.mp3"),
                os.path.join("voices", "ariana_grande.wav")
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    current_voice_ref = p
                    break
        else:
            # Stakes for Her
            female_stakes = [
                "she buys you a new game",
                "she lets you play with the boys",
                "she cooks your favorite meal",
                "she owes you a massage",
                "she pays for dinner"
            ]
            stake = random.choice(female_stakes)
            
            # Special Intro for Special Categories
            cat_text = ""
            if target_category != "general":
                cat_text = f"{target_category.upper()} EDITION!\n"
            
            intro_text = f"COUPLES QUIZ! ❤️\n{cat_text}with Keanu Reeves\nIf she fails:\n{stake.replace('she ', '').title()}! 🎮"
            
            # Special Audio for Special Categories
            audio_cat_text = ""
            if target_category != "general":
                audio_cat_text = f"{target_category} Edition! "
                
            intro_audio_text = f"Couples Quiz {audio_cat_text}with Keanu Reeves! If she gets one wrong, {stake}!"
            
            current_theme_color = BG_COLOR_BLUE
            # Try to find Keanu Reeves reference
            possible_paths = [
                os.path.join("assets", "keanu_reeves.mp3"),
                os.path.join("assets", "keanu_reeves.wav"),
                os.path.join("voices", "keanu_reeves.mp3"),
                os.path.join("voices", "keanu_reeves.wav")
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    current_voice_ref = p
                    break
            
        intro_img = create_slide(intro_text, type="intro", theme_color=current_theme_color)
        temp_files.append(intro_img)
        
        # Faster Intro Audio
        intro_audio_path = generate_audio(intro_audio_text, f"temp_intro_{random.randint(0,1000)}.mp3", reference_audio=current_voice_ref)
        intro_duration = 1.5
        
        if intro_audio_path:
            temp_files.append(intro_audio_path)
            intro_audio = AudioFileClip(intro_audio_path)
            intro_duration = intro_audio.duration + 0.1 # Reduced buffer for snappiness
            # Add Zoom Effect (Disabled)
            intro_clip = ImageClip(intro_img).set_duration(intro_duration).set_audio(intro_audio)
            # intro_clip = intro_clip.resize(lambda t: 1 + 0.05*t)
            clips.append(intro_clip)
        else:
            clips.append(ImageClip(intro_img).set_duration(intro_duration))

        current_duration = intro_duration
        
        # Prepare source questions
        source_questions = []
        if auto_mode:
            # Check if this is a "Couples Quiz" based on the intro text
            is_couples = "COUPLES" in intro_text.upper()
            
            if is_couples:
                 print(f"DEBUG: Detected Couples Quiz mode. Generating custom questions for {target_gender}...")
                 try:
                     gen = ScriptGenerator(use_ollama=True)
                     # INVERT GENDER: If target is male (He is taking quiz), questions should be about HER (female).
                     # If target is female (She is taking quiz), questions should be about HIM (male).
                     question_subject = "female" if target_gender == "male" else "male"
                     source_questions = gen.generate_couple_questions(amount=5, gender=question_subject, category=target_category)
                 except Exception as e:
                     print(f"⚠️ Failed to generate couple questions: {e}")
                     # Fallback to API if generation fails
                     source_questions = fetch_questions_from_api(10)
            else:
                source_questions = fetch_questions_from_api(10) # Reduced from 30 to 10
        elif questions:
            source_questions = questions
        
        print(f"DEBUG: Auto Mode: {auto_mode}, Source Questions: {len(source_questions)}")

        # --- PRE-SCAN FOR FUNNY REPLACEMENTS (Pick exactly ONE) ---
        all_candidates = []
        for idx, q_data in enumerate(source_questions):
            # Scan Answer Text
            cands = get_potential_replacements(q_data['a'], idx)
            all_candidates.extend(cands)
        
        target_replacement = None
        if all_candidates:
            target_replacement = random.choice(all_candidates)
            print(f"DEBUG: Selected funny replacement: {target_replacement['original']} -> {target_replacement['replacement']} in Q{target_replacement['q_idx']+1}")
        else:
            print("DEBUG: No funny replacement candidates found in this batch.")

        # Instantiate generator if needed for image keywords
        if 'gen' not in locals() or gen is None:
             try:
                 gen = ScriptGenerator(use_ollama=True)
             except:
                 gen = None

        for i, q in enumerate(source_questions):
            # Check if we are approaching the limit (auto_mode only)
            if auto_mode and current_duration >= 30:
                 # User requested 25-40s. Stopping around 30s ensures we stay in range.
                 print(f"DEBUG: Reached duration limit {current_duration}s. Stopping.")
                 break
            
            # --- Fetch Image ---
            q_image_path = None
            search_term = None
            
            # 1. Try to get search term from Gen (LLM/Heuristic)
            if gen:
                try:
                    search_term = gen.extract_image_search_term(q['q'])
                except Exception as e:
                    print(f"⚠️ Failed to extract keyword: {e}")
            
            # 2. Fallback Heuristic if no search term
            if not search_term:
                 # Remove common words, take longest remaining
                 words = q['q'].split()
                 clean_words = [w.strip("?,.!\"'").lower() for w in words if len(w) > 3]
                 # Filter common stop words (keep nouns like color, movie, song)
                 stop_words = ["what", "where", "when", "which", "does", "this", "that", "have", "make", "like", "love", "prefer", "would", "could", "should"]
                 meaningful = [w for w in clean_words if w not in stop_words]
                 if meaningful:
                     # Prefer nouns if possible (this is a simple length heuristic though)
                     search_term = max(meaningful, key=len)
                 else:
                     # If literally nothing (e.g. "What is it?"), try generic
                     search_term = "abstract art"
            
            print(f"🖼️  Image Search Term: {search_term}")
            
            if search_term:
                # Add delay to avoid rate limiting
                if i > 0:
                    time.sleep(1.0)
                    
                # Try downloading
                q_image_path = download_image_from_ddg(search_term, f"temp_q_img_{i}_{random.randint(0,1000)}.jpg")
                
                # Retry with simpler term if failed
                if not q_image_path:
                     print(f"⚠️ Image download failed for '{search_term}'. Retrying with 'minimalist {search_term}'...")
                     time.sleep(1.0)
                     q_image_path = download_image_from_ddg(f"minimalist {search_term}", f"temp_q_img_{i}_{random.randint(0,1000)}.jpg")

                if q_image_path:
                    temp_files.append(q_image_path)
                else:
                    # Final fallback to ensure an image exists
                    print("⚠️ All image downloads failed. Using generic fallback.")
                    time.sleep(1.0)
                    q_image_path = download_image_from_ddg("aesthetic background", f"temp_q_img_{i}_fallback_{random.randint(0,1000)}.jpg")
                    if q_image_path:
                        temp_files.append(q_image_path)

            # --- Question ---
            # Remove "Q1:" prefix for cleaner look
            q_text_display = q['q']
            q_text_spoken = f"Question {i+1}. {q['q']}"
            
            q_img = create_slide(q_text_display, theme_color=current_theme_color, image_path=q_image_path)
            temp_files.append(q_img)
            
            q_audio_path = generate_audio(q_text_spoken, f"temp_q{i}_{random.randint(0,1000)}.mp3", reference_audio=current_voice_ref)
            q_dur = 5.0
            q_clip = None
            
            if q_audio_path:
                temp_files.append(q_audio_path)
                q_tts_audio = AudioFileClip(q_audio_path)
                q_dur = q_tts_audio.duration + 0.2 # Reduced from 0.5
                
                # Composite TTS + Whoosh
                # Whoosh at start (0.0), TTS at 0.1 (Reduced from 0.2)
                q_final_audio = CompositeAudioClip([
                    whoosh_audio.set_start(0),
                    q_tts_audio.set_start(0.1)
                ])
                
                q_clip = ImageClip(q_img).set_duration(q_dur).set_audio(q_final_audio)
            else:
                q_clip = ImageClip(q_img).set_duration(q_dur).set_audio(whoosh_audio)
            
            # --- Thinking Time (2s) ---
            thinking_clips = []
            thinking_dur = 0.0
            for countdown in range(2, 0, -1):
                # Visual: Number overlay
                count_img = create_countdown_slide(q_img, countdown)
                temp_files.append(count_img)
                
                # Audio: Beep (0.15s beep)
                beep_file = f"temp_beep_{countdown}_{random.randint(0,1000)}.wav"
                generate_beep_wav(beep_file, duration=0.15, freq=800 if countdown > 1 else 1200) # Higher pitch on 1
                temp_files.append(beep_file)
                
                beep_audio = AudioFileClip(beep_file)
                count_clip = ImageClip(count_img).set_duration(1.0).set_audio(beep_audio)
                thinking_clips.append(count_clip)
                thinking_dur += 1.0

            # --- Answer ---
            # If Couples Quiz, SKIP the answer (User Request: "you do NOT have to give answers to these ones")
            if auto_mode and is_couples:
                print(f"DEBUG: Skipping answer for Question {i+1} (Couples Quiz Mode)")
                
                # Add Question and Thinking Clips (which were previously skipped by 'continue')
                clips.append(q_clip)
                clips.extend(thinking_clips)
                current_duration += q_dur + thinking_dur

                # Add a transition/pause before next question
                # User requested "wait atleast 2-3 seconds between questions"
                # Thinking time is 2s. We add 1.5s transition -> Total ~3.5s wait.
                
                ding_file = f"temp_ding_transition_{random.randint(0,1000)}.wav"
                generate_ding_wav(ding_file, duration=0.5, freq=1200) # Higher pitch ding
                temp_files.append(ding_file)
                ding_audio = AudioFileClip(ding_file)
                
                # Keep showing the question image
                transition_clip = ImageClip(q_img).set_duration(1.5).set_audio(ding_audio)
                clips.append(transition_clip)
                current_duration += 1.5
                
                # Skip the rest of answer logic
                final_questions_used.append(q)
                continue

            a_text_display = f"Answer:\n{q['a']}"
            
            # Funny spoken answer logic
            a_text_spoken_raw = f"The answer is {q['a']}"
            
            # Apply replacement if this is the chosen question
            if target_replacement and target_replacement['q_idx'] == i:
                modified_ans = apply_replacement(q['a'], target_replacement['word_idx'], target_replacement['replacement'])
                a_text_spoken = f"The answer is {modified_ans}"
            else:
                a_text_spoken = a_text_spoken_raw
            
            a_img = create_slide(q_text_display, subtext=a_text_display, theme_color=current_theme_color)
            temp_files.append(a_img)
            
            a_audio_path = generate_audio(a_text_spoken, f"temp_a{i}_{random.randint(0,1000)}.mp3", reference_audio=current_voice_ref)
            a_dur = 3.0
            a_clip = None
            
            if a_audio_path:
                temp_files.append(a_audio_path)
                a_tts_audio = AudioFileClip(a_audio_path)
                a_dur = a_tts_audio.duration + 0.5
                
                # Composite TTS + Ding
                # Ding at start (0.0), TTS at 0.1
                a_final_audio = CompositeAudioClip([
                    ding_audio.set_start(0),
                    a_tts_audio.set_start(0.2)
                ])

                a_clip = ImageClip(a_img).set_duration(a_dur).set_audio(a_final_audio)
            else:
                a_clip = ImageClip(a_img).set_duration(a_dur).set_audio(ding_audio)

            # Check Total Duration BEFORE adding to main list
            segment_duration = q_dur + thinking_dur + a_dur
            if auto_mode:
                if current_duration + segment_duration > 45:
                    print(f"DEBUG: Skipping question {i+1} as it would exceed 45s (Total: {current_duration + segment_duration})")
                    break
            
            # Add to main list
            clips.append(q_clip)
            clips.extend(thinking_clips)
            clips.append(a_clip)
            current_duration += segment_duration
            final_questions_used.append(q)
            
            # If manual mode, we just process all provided questions.
            # If auto mode, we continue loop until break conditions met.

        # Verify Minimum Duration (Auto Mode)
        if auto_mode and current_duration < 30:
            print(f"WARNING: Video duration {current_duration}s is less than 30s. Fetched questions might be too short or few.")

        # NO OUTRO - Loop effect (User requested viral style)
        # We just end on the last answer.

        # Concatenate
        final_video = concatenate_videoclips(clips, method="compose")
        
        # Add Background Music (Funny Audio)
        bg_music_path = os.path.join("assets", "funny_bg.mp3")
        if os.path.exists(bg_music_path):
            try:
                print(f"Adding background music from {bg_music_path}")
                bg_music = AudioFileClip(bg_music_path)
                
                # Loop logic: concatenate self until long enough
                if bg_music.duration < final_video.duration:
                    loop_count = int(final_video.duration / bg_music.duration) + 2
                    bg_clips = [bg_music] * loop_count
                    bg_music = concatenate_audioclips(bg_clips)
                
                # Trim to video length
                bg_music = bg_music.subclipped(0, final_video.duration)
                
                # Lower volume (20%)
                bg_music = bg_music.volumex(0.20)
                
                # Composite
                final_audio = CompositeAudioClip([final_video.audio, bg_music])
                final_video.audio = final_audio
            except Exception as e:
                print(f"⚠️ Failed to add background music: {e}")
        else:
            print(f"ℹ️ No background music found at {bg_music_path}. Skipping.")
        
        # Export
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", ffmpeg_params=["-pix_fmt", "yuv420p"])
        
        # --- Generate YouTube Title & Metadata ---
        is_couples_check = "COUPLES" in intro_text.upper()
        yt_title, yt_desc = generate_youtube_metadata_ai(target_gender, is_couples_check, questions=final_questions_used, category=target_category)
            
        # Save Metadata
        base_name = os.path.splitext(output_path)[0]
        meta_path = f"{base_name}_meta.txt"
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(f"TITLE: {yt_title}\n")
            f.write(f"DESCRIPTION: {yt_desc}\n")
            
        print(f"\n📝 Generated YouTube Metadata ({meta_path}):")
        print(f"   Title: {yt_title}")
        
        # Save used questions for future runs
        save_used_questions([q['q'] for q in final_questions_used])
        
        return final_questions_used
        
    finally:
        # Cleanup
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

def generate_long_quiz_video(output_path="long_quiz_output.mp4"):
    """
    Generates a 15-25 minute landscape quiz video with 4 choices and 10s thinking time.
    """
    clips = []
    temp_files = []
    final_questions_used = []
    
    # Target duration: ~20 mins (1200s). Range 15-25 mins (900-1500s).
    TARGET_DURATION_MIN = 900
    
    try:
        # Intro
        intro_text = "Ultimate General Knowledge Quiz!\n\nCan you get them all right?"
        intro_img = create_landscape_slide(intro_text, type="intro")
        temp_files.append(intro_img)
        
        intro_audio_path = generate_audio("Welcome to the Ultimate General Knowledge Quiz! Can you answer these questions correctly?", f"temp_intro_long_{random.randint(0,1000)}.mp3")
        
        intro_duration = 3.0
        if intro_audio_path:
            temp_files.append(intro_audio_path)
            intro_audio = AudioFileClip(intro_audio_path)
            intro_duration = intro_audio.duration + 0.5
            clips.append(ImageClip(intro_img).set_duration(intro_duration).set_audio(intro_audio))
        else:
            clips.append(ImageClip(intro_img).set_duration(intro_duration))

        current_duration = intro_duration
        
        # Loop until duration is met
        while current_duration < TARGET_DURATION_MIN:
            # Fetch batch of questions
            batch_size = 5
            print(f"Fetching more questions... Current Duration: {current_duration}s")
            questions = fetch_long_questions_from_api(batch_size)
            
            if not questions:
                print("⚠️ No more questions available or API failed!")
                if current_duration < 60: # If we have almost nothing, stop.
                     break
                else: # If we have some content, finish up.
                     break
                
            for i, q in enumerate(questions):
                if current_duration >= TARGET_DURATION_MIN:
                    break
                
                # --- Question Slide ---
                # Show question + options
                q_text_display = f"{q['q']}"
                q_text_spoken = f"{q['q']}" # Just read question
                
                # Create slide with options (no answer highlighted)
                q_img = create_landscape_slide(q_text_display, options=q['options'])
                temp_files.append(q_img)
                
                q_audio_path = generate_audio(q_text_spoken, f"temp_qlong_{random.randint(0,1000)}.mp3")
                q_dur = 5.0
                q_clip = None
                
                if q_audio_path:
                    temp_files.append(q_audio_path)
                    q_audio = AudioFileClip(q_audio_path)
                    q_dur = q_audio.duration + 0.5 # A bit of pause
                    q_clip = ImageClip(q_img).set_duration(q_dur).set_audio(q_audio)
                else:
                    q_clip = ImageClip(q_img).set_duration(q_dur)
                
                clips.append(q_clip)
                current_duration += q_dur
                
                # --- Thinking Time (10s) ---
                # Visual countdown on top of the question slide
                for countdown in range(10, 0, -1):
                    # Only create image for even numbers or every second to save time? 
                    # User requested 10s thinking time.
                    count_img = create_countdown_slide(q_img, countdown)
                    temp_files.append(count_img)
                    
                    # Tick sound
                    tick_file = f"temp_tick_{countdown}_{random.randint(0,1000)}.wav"
                    generate_beep_wav(tick_file, duration=0.1, freq=800)
                    temp_files.append(tick_file)
                    
                    tick_audio = AudioFileClip(tick_file)
                    count_clip = ImageClip(count_img).set_duration(1.0).set_audio(tick_audio)
                    clips.append(count_clip)
                    current_duration += 1.0
                
                # --- Answer Slide ---
                # Highlight correct answer
                a_img = create_landscape_slide(q_text_display, options=q['options'], correct_idx=q['correct_idx'], show_answer=True)
                temp_files.append(a_img)
                
                a_text_spoken = f"The answer is {q['a']}"
                a_audio_path = generate_audio(a_text_spoken, f"temp_along_{random.randint(0,1000)}.mp3")
                
                a_dur = 3.0
                if a_audio_path:
                    temp_files.append(a_audio_path)
                    a_audio = AudioFileClip(a_audio_path)
                    a_dur = a_audio.duration + 0.5
                    a_clip = ImageClip(a_img).set_duration(a_dur).set_audio(a_audio)
                    clips.append(a_clip)
                else:
                    clips.append(ImageClip(a_img).set_duration(a_dur))
                    
                current_duration += a_dur
                final_questions_used.append(q)
                
        # Outro
        outro_text = "Thanks for watching!\nDon't forget to subscribe!"
        outro_img = create_landscape_slide(outro_text, type="outro")
        temp_files.append(outro_img)
        clips.append(ImageClip(outro_img).set_duration(5))
        
        # Concatenate
        print("Concatenating clips...")
        final_video = concatenate_videoclips(clips, method="compose")
        
        # Background Music
        bg_music_path = os.path.join("assets", "funny_bg.mp3")
        if os.path.exists(bg_music_path):
            try:
                print(f"Adding background music from {bg_music_path}")
                bg_music = AudioFileClip(bg_music_path)
                
                # Loop logic
                if bg_music.duration < final_video.duration:
                    loop_count = int(final_video.duration / bg_music.duration) + 2
                    bg_clips = [bg_music] * loop_count
                    bg_music = concatenate_audioclips(bg_clips)
                
                # Trim
                bg_music = bg_music.subclipped(0, final_video.duration)
                
                # Volume
                bg_music = bg_music.volumex(0.15)
                
                # Composite
                final_audio = CompositeAudioClip([final_video.audio, bg_music])
                final_video.audio = final_audio
            except Exception as e:
                print(f"⚠️ Failed to add background music: {e}")
             
        print(f"Writing video to {output_path}...")
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", ffmpeg_params=["-pix_fmt", "yuv420p"])
        
        # Save used questions
        save_used_questions([q['q'] for q in final_questions_used], USED_LONG_QUESTIONS_FILE)
        print(f"✅ Long video generated! Used {len(final_questions_used)} questions.")
        
        return final_questions_used

    finally:
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass


if __name__ == "__main__":
    # Test
    qs = [
        {"q": "What is the capital of France?", "a": "Paris"},
        {"q": "Who wrote Romeo and Juliet?", "a": "William Shakespeare"},
        {"q": "What is 2 + 2?", "a": "4"}
    ]
    generate_quiz_video(qs, "test_quiz.mp4")
