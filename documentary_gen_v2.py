
import os
import asyncio
import edge_tts
import nest_asyncio
import subprocess
import gc
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
# MoviePy imports with proper fallback
try:
    from moviepy.editor import VideoFileClip, ImageClip, ColorClip, CompositeVideoClip, AudioFileClip, VideoClip, vfx, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip
except ImportError:
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        from moviepy.video.VideoClip import VideoClip, ImageClip, ColorClip
        from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
        from moviepy.video.compositing.concatenate import concatenate_videoclips
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        from moviepy.audio.AudioClip import CompositeAudioClip
        from moviepy.audio.compositing.concatenate import concatenate_audioclips
        import moviepy.video.fx.all as vfx
    except ImportError:
        # Try direct import for MoviePy v2
        from moviepy import VideoFileClip, ImageClip, ColorClip, CompositeVideoClip, AudioFileClip, VideoClip, vfx, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import textwrap
import random

from script_generator import ScriptGenerator
from media_manager import MediaManager

# Try to import CLIP Filter
try:
    from clip_filter import ClipFilter
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    print("⚠️ CLIP Filter not available (transformers/torch missing).")

# Constants
VOICE = "en-US-ChristopherNeural"

# Enhanced Visual Map: Abstract -> Concrete
VISUAL_MAP = {
    "reputation": "shattering glass slow motion cinematic",
    "destroyed": "building explosion debris dust 4k",
    "mistake": "spilled coffee dark moody lighting",
    "future": "futuristic cyberpunk city neon lights timelapse",
    "history": "ancient scroll dust floating in light beam",
    "crisis": "emergency red light alarm spinning",
    "market": "stock market ticker chaotic fast",
    "growth": "plant growing timelapse macro detail",
    "musk": "rocket launch smoke fire 4k",
    "tesla": "electric car charging station night rain",
    "money": "counting cash stacks cinematic lighting",
    "fail": "car crash dummy test impact slow motion",
    "success": "mountain climber reaching summit sunrise",
    "idea": "lightbulb filament glowing macro",
    "network": "fiber optic cables glowing blue data flow",
    "data": "matrix code rain green digital",
    "ai": "robot eye close up lens flare reflection",
    "fear": "dark forest fog silhouettes mysterious",
    "hope": "sunrise clouds golden hour majestic",
    "time": "clock ticking fast timelapse blur",
    "economy": "stock market ticker trading floor busy",
    "war": "soldiers marching silhouette sunset dust",
    "peace": "sunrise calm ocean waves",
    "death": "graveyard fog night mystery",
    "love": "holding hands couple sunset silhouette",
    "power": "lightning strike storm dark clouds",
    "internet": "server room lights blinking bokeh",
    "technology": "circuit board macro electronic components",
    "mind": "brain neuron firing synopsis",
    "secret": "keyhole light shining through dust",
    "truth": "magnifying glass revealing detail",
    "lie": "crossed fingers behind back shadow",
    "ancient": "pyramids desert sunset epic scale",
    "space": "galaxy stars nebula deep space 8k",
    "ocean": "waves crashing cliff dramatic spray",
    "nature": "forest aerial drone shot mist",
    "city": "city skyline night lights reflections",
    "people": "crowd walking busy street timelapse blur",
    "lonely": "person sitting alone bench rain moody",
    "happy": "people laughing slow motion sunshine",
    "sad": "rain on window macro droplets",
    "angry": "storm clouds thunder dark ominous",
    "fast": "highway timelapse car lights streaks",
    "slow": "snail crawling macro leaf",
    "rich": "gold bars vault shiny treasure",
    "poor": "homeless sign cardboard texture dirty",
    "win": "trophy gold sparkling spotlight",
    "lose": "game over screen glitch distortion",
    "start": "green light traffic signal go",
    "end": "sunset horizon fading light",
    "born": "baby smiling soft light angelic",
    "die": "wilted flower time lapse decay",
    "fight": "boxing gloves impact sweat particles",
    "help": "shaking hands agreement business suit",
    # 2025 Specific Realities
    "brand value": "stock market red crash graph falling",
    "financial crash": "stock market red crash panic",
    "tornado": "worried face close up sweat eyes",
    "social tax": "person looking stressed at phone screen light",
    "cybertruck": "cybertruck driving desert futuristic",
    "tesla": "tesla factory robots assembly line",
    "elon": "elon musk speaking press conference cinematic",
    "money": "stacks of cash cinematic lighting",
    "luxury": "luxury mansion interior gold 4k",
    "nature": "majestic mountain landscape aerial 8k",
    "technology": "futuristic laboratory glowing blue lights",
    "city": "cyberpunk city night neon rain detailed",
    "innovation": "lightbulb filament glowing macro sparks",
    "code": "matrix digital rain green code flowing",
    "crypto": "bitcoin gold coin spinning cinematic",
    "blockchain": "digital blocks connecting network glowing",
    "virus": "microscopic virus cell 3d render danger",
    "health": "dna double helix rotating blue medical",
    "brain": "neurons firing electrical signals brain 3d",
    "space x": "falcon heavy rocket launch smoke fire",
    "mars": "red planet surface rover dust storm",
    "moon": "moon surface craters earth rise",
    "sun": "sun solar flare burning star space",
    "earth": "earth from space blue marble rotating",
    "universe": "galaxy nebula stars deep space infinite",
    "black hole": "black hole accretion disk bending light",
    "robot": "humanoid robot face artificial intelligence",
    "vr": "person wearing vr headset virtual reality",
    "metaverse": "digital avatar virtual world neon",
    "gaming": "esports arena crowd lights screens",
    "hacker": "hooded figure typing laptop dark room green code",
    "security": "padlock digital shield cyber security",
    "cloud": "server farm data center blue lights clouds",
    "mobile": "smartphone screen app social media scrolling",
    "social": "network connections people nodes lines",
    "media": "tv screens news anchor camera lens",
    "fake news": "newspaper headlines spinning glitch distortion",
    "politics": "capitol building flag waving dramatic sky",
    "justice": "gavel hitting wooden block law court",
    "crime": "police lights red blue flashing night rain",
    "prison": "prison bars shadow silhouette jail",
    "freedom": "bird flying cage open sky sunset",
    "education": "library books shelves old knowledge",
    "science": "microscope lab coat chemicals flask",
    "art": "paint brush canvas colors artistic creative",
    "music": "piano keys musical notes floating staff",
    "movie": "cinema projector beam dust particles",
    "sports": "stadium lights crowd cheering match",
    "football": "football grass field stadium lights",
    "basketball": "basketball hoop net swish slow motion",
    "soccer": "soccer ball grass goal net kick",
}

def get_visual_keyword(text, extracted_keyword):
    """
    Maps abstract text to concrete visual keywords.
    Prioritizes specific nouns found in text.
    """
    text_lower = text.lower()
    
    prompt = extracted_keyword
    
    # 1. Check Manual Map (Abstract -> Concrete)
    for word, visual in VISUAL_MAP.items():
        if word in text_lower:
            prompt = visual
            break
            
    # 2. If extracted keyword is too short or generic, fallback
    if len(prompt) < 3:
        prompt = "cinematic abstract background"

    # 3. Enhance prompt with quality modifiers
    modifiers = " cinematic lighting, 8k, photorealistic, highly detailed, dramatic atmosphere"
    if "cinematic" not in prompt.lower():
        prompt += modifiers
        
    return prompt

def create_chart_clip(type="line", duration=3, data=None):
    """Creates a stylized chart animation using PIL."""
    w, h = 1920, 1080
    img = Image.new('RGB', (w, h), (20, 20, 20)) # Dark background
    draw = ImageDraw.Draw(img)
    
    # Fonts
    try:
        title_font = ImageFont.truetype("arial.ttf", 60)
        label_font = ImageFont.truetype("arial.ttf", 30)
    except:
        title_font = ImageFont.load_default()
        label_font = ImageFont.load_default()

    # Draw Grid
    for i in range(0, w, 100):
        draw.line([(i, 0), (i, h)], fill=(40, 40, 40), width=1)
    for i in range(0, h, 100):
        draw.line([(0, i), (w, i)], fill=(40, 40, 40), width=1)
        
    # Draw Axis
    draw.line([(100, h-100), (w-100, h-100)], fill=(200, 200, 200), width=4) # X
    draw.line([(100, 100), (100, h-100)], fill=(200, 200, 200), width=4) # Y
    
    # Title
    if data and "title" in data:
        draw.text((w//2 - 200, 50), data["title"], font=title_font, fill=(255, 255, 255))
        
    # Axis Labels
    if data:
        if "x_label" in data:
            draw.text((w//2, h-60), data["x_label"], font=label_font, fill=(200, 200, 200))
        if "y_label" in data:
            # Rotate text? PIL draw.text doesn't rotate easily. Just place it at top of Y
            draw.text((20, 100), data["y_label"], font=label_font, fill=(200, 200, 200))

    # Data Points
    points = []
    
    if data and "data" in data and len(data["data"]) > 1:
        # Use provided data
        items = data["data"]
        # Normalize values
        values = [float(item["value"]) for item in items]
        min_val = min(values)
        max_val = max(values)
        val_range = max_val - min_val if max_val != min_val else 1
        
        num_points = len(items)
        # X range: 100 to w-100
        # Y range: h-100 (min) to 100 (max) - Inverted Y
        
        for i, item in enumerate(items):
            x = 100 + (i / (num_points - 1)) * (w - 200)
            # Y mapping
            norm_val = (item["value"] - min_val) / val_range
            y = (h - 100) - (norm_val * (h - 200))
            points.append((x, y))
            
            # Draw X labels
            draw.text((x - 20, h - 90), str(item["label"]), font=label_font, fill=(150, 150, 150))
            
        # Determine color based on start/end
        if values[-1] < values[0]:
            color = (255, 50, 50) # Crash
        else:
            color = (50, 255, 50) # Growth
            
    else:
        # Fallback to Random Gen
        import math
        if type == "crash":
            # Downward trend
            for x in range(100, w-100, 20):
                progress = (x - 100) / (w - 200)
                y = (h-200) - (1 - progress) * (h-400) + random.randint(-20, 20)
                if progress > 0.7: # Crash at the end
                    y += (progress - 0.7) * 800
                points.append((x, min(y, h-100)))
            color = (255, 50, 50)
        else:
            # Upward trend
            for x in range(100, w-100, 20):
                progress = (x - 100) / (w - 200)
                y = (h-100) - progress * (h-300) + random.randint(-20, 20)
                points.append((x, y))
            color = (50, 255, 50)
            
    if len(points) > 1:
        draw.line(points, fill=color, width=5)
        # Draw circles at points
        for p in points:
            draw.ellipse((p[0]-5, p[1]-5, p[0]+5, p[1]+5), fill=color)
        
    # Convert to Clip
    img_np = np.array(img)
    clip = ImageClip(img_np).set_duration(duration)
    return clip

def create_split_screen(clip1, clip2):
    """Combines two clips side-by-side."""
    w, h = 1920, 1080
    
    # Resize to half width, full height
    c1 = clip1.resize(newsize=(w//2, h))
    c2 = clip2.resize(newsize=(w//2, h))
    
    # Position
    c1 = c1.set_position((0, 0))
    c2 = c2.set_position((w//2, 0))
    
    return CompositeVideoClip([c1, c2], size=(w, h))

def create_source_attribution(source_name, duration):
    """Creates a small 'Source: X' overlay."""
    w, h = 1920, 1080
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    text = f"Source: {source_name}"
    font = ImageFont.load_default()
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        pass
        
    # Bottom right
    text_w = 200 # approx
    x = w - text_w - 50
    y = h - 80
    
    # Background box
    draw.rectangle([x-10, y-10, w-30, y+40], fill=(0,0,0,128))
    draw.text((x, y), text, font=font, fill=(200, 200, 200, 200))
    
    img_np = np.array(img)
    return ImageClip(img_np).set_duration(duration)

def create_title_clip(text, duration):
    """Creates a cinematic text title overlay using PIL (No ImageMagick dependency)."""
    # Extract first 3-4 words for impact
    words = text.split()
    title_text = " ".join(words[:4]).upper()
    if len(words) > 4:
        title_text += "..."
        
    w, h = 1920, 1080
    
    # Create transparent image
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Load font (try system fonts for better look)
    font_paths = [
        "C:/Windows/Fonts/georgia.ttf", 
        "C:/Windows/Fonts/times.ttf", 
        "arial.ttf"
    ]
    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, 90)
            break
        except:
            continue
            
    if not font:
        font = ImageFont.load_default()
        
    # Calculate text size (basic estimation)
    try:
        left, top, right, bottom = draw.textbbox((0, 0), title_text, font=font)
        text_w = right - left
        text_h = bottom - top
    except:
        text_w, text_h = 600, 100 # Fallback
        
    # Draw text with shadow for visibility
    x = (w - text_w) // 2
    y = h - 180 # Bottom center, slightly higher
    
    # Cinematic text styling:
    # 1. Subtle drop shadow
    draw.text((x+4, y+4), title_text, font=font, fill=(0,0,0,180))
    # 2. Main text
    draw.text((x, y), title_text, font=font, fill=(240, 240, 240, 255)) # Slightly off-white
    
    # Convert to numpy for MoviePy
    img_np = np.array(img)
    
    clip = ImageClip(img_np).set_duration(duration)
    
    # Add Fade In/Out
    try:
        clip = clip.crossfadein(0.5).crossfadeout(0.5)
    except:
        pass
        
    return clip

def apply_cinematic_grade(clip):
    """Applies subtle contrast and saturation boost."""
    # Contrast & Saturation
    try:
        # Increase contrast
        clip = clip.fx(vfx.lum_contrast, contrast=1.1)
        # Desaturate slightly for "documentary" feel (optional, or boost for vibrancy)
        # Let's boost slightly for engagement
        # clip = clip.fx(vfx.colorx, 1.1) 
    except:
        pass # If fails, return original
    return clip

async def generate_voiceover_async(text, output_filename):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_filename)

def create_audio(text, filename):
    """Wrapper to run edge-tts synchronously."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Use nest_asyncio to allow nested event loops (useful if running in GUI/Notebook)
    nest_asyncio.apply()
    
    try:
        loop.run_until_complete(generate_voiceover_async(text, filename))
    except Exception as e:
        print(f"Audio Generation Error: {e}")
        pass

def create_scanline_overlay(width=1920, height=1080):
    temp_file = "temp_overlay_scanlines.png"
    if os.path.exists(temp_file):
        return ImageClip(temp_file)
        
    img = Image.new('RGBA', (width, height), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    
    # 1. Vignette (Dark corners)
    # Create a radial gradient mask
    # This is manual in PIL. Simpler: Draw semi-transparent black rectangle with hole?
    # Or just draw a large radial gradient.
    
    # Let's do a simple vignette by drawing a radial gradient on a separate layer
    # Center is transparent, edges are black.
    
    # Create meshgrid for distance calculation
    # (Doing this in numpy is faster but we need to save as PNG for ffmpeg overlay)
    
    # Simpler Vignette: Draw large ellipse in center (transparent) and fill rest with black (blurred)?
    # Or just scanlines + slight dark overlay.
    
    # Draw scanlines (faint black lines)
    for y in range(0, height, 4):
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, 20), width=1)
        
    # Add Vignette manually using a radial gradient approximation or just darken edges
    # For speed/simplicity in PIL:
    # Just draw borders with increasing opacity? No, too blocky.
    
    # Let's use numpy to generate vignette
    X, Y = np.meshgrid(np.linspace(-1, 1, width), np.linspace(-1, 1, height))
    radius = np.sqrt(X**2 + Y**2)
    # radius 0 at center, >1 at corners.
    # Vignette: opacity increases with radius.
    # mask = smoothstep(0.5, 1.2, radius) * 255
    
    # Simple linear vignette
    vignette_mask = np.clip((radius - 0.4) * 0.8, 0, 1) * 200 # Max opacity 200/255
    vignette_layer = np.zeros((height, width, 4), dtype=np.uint8)
    vignette_layer[:, :, 3] = vignette_mask.astype(np.uint8) # Alpha channel
    
    # Combine scanlines (PIL Image) with Vignette (Numpy)
    scanline_np = np.array(img)
    
    # Alpha blending: Source (Vignette) over Destination (Scanlines)
    # Scanlines is mostly transparent (0,0,0,0) with some lines (0,0,0,20).
    # Vignette is (0,0,0, A).
    # Result = Vignette + Scanlines. Since both are black, we just add alphas?
    # Or just max the alphas?
    
    # Let's just create a new image from vignette numpy array and alpha composite
    vignette_img = Image.fromarray(vignette_layer, 'RGBA')
    img = Image.alpha_composite(img, vignette_img)
    
    img.save(temp_file)
    return ImageClip(temp_file)

def resize_to_1080p(clip):
    target_w, target_h = 1920, 1080
    
    # Resize to cover
    ratio = max(target_w / clip.width, target_h / clip.height)
    new_w = int(clip.width * ratio)
    new_h = int(clip.height * ratio)
    
    clip = clip.resize(newsize=(new_w, new_h))
    
    # Center Crop
    clip = clip.crop(width=target_w, height=target_h, x_center=new_w/2, y_center=new_h/2)
    return clip

def create_zooming_clip(image_path, duration):
    """
    Applies a smart Ken Burns effect (zoom/pan) to static images.
    Preserves original resolution for high-quality zooms.
    """
    try:
        # Load image size
        with Image.open(image_path) as img:
            w, h = img.size
            
        target_w, target_h = 1920, 1080
        target_ar = target_w / target_h
        img_ar = w / h
        
        # Determine the maximum possible 16:9 crop from the source image
        if img_ar > target_ar:
            # Image is wider than 16:9. Constrained by height.
            max_crop_h = h
            max_crop_w = int(h * target_ar)
        else:
            # Image is taller/narrower. Constrained by width.
            max_crop_w = w
            max_crop_h = int(w / target_ar)
            
        # Ensure we don't crash if image is tiny (unlikely with stock fetcher but possible)
        if max_crop_w == 0 or max_crop_h == 0:
             return ImageClip(image_path).set_duration(duration).resize(newsize=(target_w, target_h))

        clip = ImageClip(image_path).set_duration(duration)
        
        # Decision: Pan or Zoom?
        # Pan if significantly wider (panorama)
        is_wide = img_ar > target_ar * 1.5 
        effect_type = random.choice(["pan_right", "pan_left"]) if is_wide else random.choice(["zoom_in", "zoom_out"])
        
        print(f"Applying smart Ken Burns: {effect_type} for {image_path} (Original: {w}x{h})")

        # Define Start and End Crop Rectangles (width, height, x_center, y_center)
        # We define them relative to the original image coordinates
        
        if "pan" in effect_type:
            # Pan uses the max crop size but moves the x_center
            crop_w, crop_h = max_crop_w, max_crop_h
            
            # Calculate x range
            # Center of leftmost crop: crop_w / 2
            # Center of rightmost crop: w - (crop_w / 2)
            min_x = crop_w / 2
            max_x = w - (crop_w / 2)
            
            if effect_type == "pan_right":
                # Move from Left to Right
                start_x, start_y = min_x, h / 2
                end_x, end_y = max_x, h / 2
            else:
                # Move from Right to Left
                start_x, start_y = max_x, h / 2
                end_x, end_y = min_x, h / 2
                
            start_w, start_h = crop_w, crop_h
            end_w, end_h = crop_w, crop_h
            
        elif "zoom" in effect_type:
            # Zoom In: Start at Full, End at 85%
            # Zoom Out: Start at 85%, End at Full
            
            full_w, full_h = max_crop_w, max_crop_h
            zoom_factor = 0.85 # Zoom in to 85% of the image
            zoomed_w, zoomed_h = full_w * zoom_factor, full_h * zoom_factor
            
            # Randomize focus point for the zoomed state
            # The zoomed crop must be within the full crop
            # Valid center range for zoomed crop:
            # Min x: (full_w - zoomed_w)/2 + (w - full_w)/2 ... wait, let's keep it simple.
            # Just center it for now to be safe, or slightly offset.
            
            center_x, center_y = w / 2, h / 2
            
            if effect_type == "zoom_in":
                start_w, start_h = full_w, full_h
                end_w, end_h = zoomed_w, zoomed_h
            else:
                start_w, start_h = zoomed_w, zoomed_h
                end_w, end_h = full_w, full_h
                
            start_x, start_y = center_x, center_y
            end_x, end_y = center_x, center_y

        # Define interpolation function
        def crop_filter(t):
            try:
                # In MoviePy v2, t can sometimes be a function or have weird types during init
                curr_t = t() if callable(t) else t
                p = float(curr_t) / duration
            except Exception:
                p = 0
            
            # Linear interpolation
            cw = start_w + (end_w - start_w) * p
            ch = start_h + (end_h - start_h) * p
            cx = start_x + (end_x - start_x) * p
            cy = start_y + (end_y - start_y) * p
            
            return (cx, cy, cw, ch)

        # Apply dynamic crop and resize via transform for MoviePy v2 compatibility
        def ken_burns_transform(get_frame, t):
            img_np = get_frame(t)
            cx, cy, cw, ch = crop_filter(t)
            
            # Calculate coordinates
            x1 = max(0, int(cx - cw/2))
            y1 = max(0, int(cy - ch/2))
            x2 = min(img_np.shape[1], int(x1 + cw))
            y2 = min(img_np.shape[0], int(y1 + ch))
            
            # Crop
            cropped = img_np[y1:y2, x1:x2]
            
            # Resize to target
            img_pil = Image.fromarray(cropped)
            img_resized = img_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
            return np.array(img_resized)

        clip = clip.fl(ken_burns_transform)
                
        return clip

    except Exception as e:
        import traceback
        print(f"Ken Burns Error: {e}")
        traceback.print_exc()
        # Fallback: Simple Resize & Crop
        return ImageClip(image_path).set_duration(duration).resize(height=1080).crop(width=1920, height=1080)

def generate_documentary_video(topic_or_script, output_path="documentary_output.mp4", pexels_api_key=None, openai_api_key=None, gemini_api_key=None, use_ollama=False, ollama_model="llama3", use_clip=True):
    script_gen = ScriptGenerator(openai_api_key, gemini_api_key, use_ollama=use_ollama, ollama_model=ollama_model)
    media_mgr = MediaManager(pexels_api_key)
    
    clip_filter = None
    if use_clip and CLIP_AVAILABLE:
        print("🧠 Initializing CLIP Filter for visual relevance...")
        clip_filter = ClipFilter()
    
    print(f"🎬 Starting Documentary Generation (v2 - Pro / Low Memory)...")
    
    # 1. Generate/Parse Script
    if openai_api_key or gemini_api_key or use_ollama:
        print("Generating script with AI...")
        segments = script_gen.generate_script(topic_or_script)
    else:
        print("Parsing provided text as script...")
        segments = script_gen.process_text(topic_or_script)
    
    temp_segment_files = []
    temp_files_to_clean = []
    
    try:
        for i, segment in enumerate(segments):
            gc.collect()
            print(f"Processing segment {i+1}/{len(segments)}...")
            text = segment['text']
            
            # Resource tracking for this segment to ensure closure
            segment_resources = []
            clip = None
            
            try:
                # Smart Keyword Extraction
                extracted = segment.get('keywords', '')
                visual_keyword_list = []
                
                if not extracted:
                    extracted = script_gen._extract_keywords(text)
                
                if isinstance(extracted, list):
                    visual_keyword_list = extracted
                    visual_keyword = extracted[0] if extracted else "background"
                else:
                    # Legacy or Single String
                    if (use_ollama or openai_api_key or gemini_api_key) and extracted and len(extracted) > 5:
                         visual_keyword = extracted
                    else:
                         visual_keyword = get_visual_keyword(text, extracted)
                    visual_keyword_list = [visual_keyword]
                
                print(f"Keywords: {visual_keyword_list if len(visual_keyword_list) > 1 else visual_keyword}")

                # 1. Generate Audio
                audio_file = f"temp_audio_{i}.mp3"
                create_audio(text, audio_file)
                temp_files_to_clean.append(audio_file)
                
                audioclip = None
                duration = 3
                if os.path.exists(audio_file):
                    # Load audio
                    ac_temp = AudioFileClip(audio_file)
                    segment_resources.append(ac_temp)
                    duration = ac_temp.duration + 0.5
                    audioclip = ac_temp
                else:
                    print("Audio generation failed.")

                # 2. Get Visuals (Multi-Stage Fallback)
                
                # Check for Visual Triggers
                trigger_clip = None
                text_lower = text.lower()
                
                if "[chart]" in text_lower or "graph" in text_lower or "plummet" in text_lower:
                    print("Triggering Chart Animation...")
                    # Generate accurate data
                    chart_data = script_gen.generate_chart_data(text)
                    print(f"Chart Data: {chart_data}")
                    
                    chart_type = "crash" if "plummet" in text_lower or "crash" in text_lower or "drop" in text_lower else "growth"
                    trigger_clip = create_chart_clip(type=chart_type, duration=duration, data=chart_data)
                    clip = trigger_clip
                    
                elif "[split screen]" in text_lower:
                    print("Triggering Split Screen...")
                    
                    # Try to parse "one side X, other side Y"
                    import re
                    # Look for "one side... [noun phrase]... other... [noun phrase]"
                    # Simple heuristic: Split by "on the other"
                    split_term_1 = f"{visual_keyword} happy" # Default contrast
                    split_term_2 = f"{visual_keyword} sad"
                    
                    if "one side" in text_lower and "other" in text_lower:
                        try:
                            parts = text_lower.split("on the other")
                            part1 = parts[0].split("one side")[-1] # content after "one side"
                            part2 = parts[1] # content after "other"
                            
                            # Extract key noun from these parts? 
                            # Just use the whole phrase but clean it
                            def clean_side(t):
                                t = re.sub(r'[^\w\s]', '', t)
                                words = t.strip().split()
                                # Take last 2-3 words as they are likely the subject
                                return " ".join(words[-3:]) if len(words) > 3 else " ".join(words)
                                
                            term1 = clean_side(part1)
                            term2 = clean_side(part2)
                            
                            if term1 and term2:
                                split_term_1 = term1
                                split_term_2 = term2
                                print(f"Split Screen Terms: '{term1}' vs '{term2}'")
                        except:
                            pass

                    # Search for two different things
                    res1 = media_mgr.search_video(f"{split_term_1} cinematic")
                    res2 = media_mgr.search_video(f"{split_term_2} cinematic")
                    
                    clip1 = None
                    clip2 = None
                    
                    if res1:
                        f1 = f"temp_split_1_{i}.mp4"
                        if media_mgr.download_file(res1['url'], f1):
                            temp_files_to_clean.append(f1)
                            clip1 = VideoFileClip(f1)
                            segment_resources.append(clip1)
                            
                    if res2:
                        f2 = f"temp_split_2_{i}.mp4"
                        if media_mgr.download_file(res2['url'], f2):
                            temp_files_to_clean.append(f2)
                            clip2 = VideoFileClip(f2)
                            segment_resources.append(clip2)
                            
                    if clip1 and clip2:
                        # Loop/Cut to duration
                        clip1 = clip1.subclipped(0, duration) if clip1.duration > duration else clip1.loop(duration=duration)
                        clip2 = clip2.subclipped(0, duration) if clip2.duration > duration else clip2.loop(duration=duration)
                        clip = create_split_screen(clip1, clip2)
                
                # Normal Search if no trigger
                source_attribution = None
                
                if not clip:
                    # Multi-Clip Logic for better pacing
                    # Target ~4-5 seconds per clip
                    target_subclip_dur = 4.5
                    num_clips_needed = 1
                    if duration > 7.0:
                        num_clips_needed = int(np.ceil(duration / target_subclip_dur))
                        
                    if num_clips_needed > 1:
                        print(f"Targeting {num_clips_needed} clips for {duration:.1f}s segment...")
                        
                    sub_clips = []
                    used_media_urls = set()
                    
                    # Calculate exact duration for each sub-clip to match total audio
                    sub_clip_durations = [duration / num_clips_needed] * num_clips_needed
                    
                    for k in range(num_clips_needed):
                        current_clip = None
                        search_result = None
                        
                        # Rotate keywords and modifiers
                        kw_index = k % len(visual_keyword_list)
                        base_keyword = visual_keyword_list[kw_index]
                        
                        query_modifiers = ["cinematic", "4k", "detailed", "slow motion", "close up", "wide shot"]
                        modifier = query_modifiers[k % len(query_modifiers)]
                        
                        # --- 1. Try Video ---
                        # A. CLIP Search (First clip only or all?)
                        if clip_filter and k == 0 and not search_result:
                            # Use existing CLIP logic just for the first one for now
                            all_candidates = []
                            for kw in visual_keyword_list:
                                cands = media_mgr.search_candidates(kw, per_page=5)
                                all_candidates.extend(cands)
                                if len(all_candidates) >= 5 and kw == visual_keyword_list[0]: break
                            
                            if all_candidates:
                                best_match = clip_filter.score_candidates(all_candidates, text)
                                if best_match:
                                    search_result = best_match
                                    print(f"✅ CLIP selected ({k+1}): {search_result['url']}")

                        # B. Standard Search
                        if not search_result:
                            # Try multiple queries to find unused media
                            for q_attempt in range(3):
                                # First attempt: base + modifier. Subsequent: random modifier.
                                q_mod = modifier if q_attempt == 0 else random.choice(query_modifiers)
                                q = f"{base_keyword} {q_mod}"
                                if k > 0: q += " footage" # bias towards video
                                
                                print(f"Searching video ({k+1}/{num_clips_needed}): {q}")
                                res = media_mgr.search_video(q)
                                
                                if res and res['url'] not in used_media_urls:
                                    search_result = res
                                    break
                                elif res and num_clips_needed == 1:
                                    # If only 1 clip needed, duplicates don't matter (first run)
                                    search_result = res
                                    break
                        
                        # Process Video Result
                        if search_result:
                            url = search_result['url']
                            used_media_urls.add(url)
                            source_name = search_result.get('source', 'Unknown')
                            if source_name in ['YouTube', 'X (Twitter)']:
                                source_attribution = source_name 
                                
                            try:
                                v_file = f"temp_video_{i}_{k}.mp4"
                                if media_mgr.download_file(url, v_file):
                                    temp_files_to_clean.append(v_file)
                                    vc = VideoFileClip(v_file)
                                    segment_resources.append(vc)
                                    
                                    # Loop or Subclip to exact sub_clip_durations[k]
                                    target_dur = sub_clip_durations[k]
                                    
                                    if vc.duration < target_dur:
                                        vc = vc.loop(duration=target_dur)
                                    else:
                                        vc = vc.subclipped(0, target_dur)
                                        
                                    vc = resize_to_1080p(vc)
                                    current_clip = vc
                            except Exception as e:
                                print(f"Video load error: {e}")
                                
                        # --- 2. Try Image (Ken Burns) ---
                        if not current_clip:
                            q_img = f"{base_keyword} {modifier} photorealistic"
                            print(f"Searching image ({k+1}/{num_clips_needed}): {q_img}")
                            img_url = media_mgr.search_image(q_img)
                            
                            # For images, we can reuse URL if we apply different Ken Burns? 
                            # But better to get new one.
                            if img_url:
                                if img_url not in used_media_urls or num_clips_needed == 1:
                                    used_media_urls.add(img_url)
                                    img_file = f"temp_image_{i}_{k}.jpg"
                                    if media_mgr.download_file(img_url, img_file):
                                        temp_files_to_clean.append(img_file)
                                        target_dur = sub_clip_durations[k]
                                        current_clip = create_zooming_clip(img_file, duration=target_dur)
                        
                        if current_clip:
                            sub_clips.append(current_clip)
                        else:
                            print(f"Failed to find clip {k+1}")
                            # Fallback to black for this subclip? 
                            # Or just skip? If we skip, duration mismatches.
                            # Create placeholder
                            target_dur = sub_clip_durations[k]
                            color_uint8 = np.array([10, 10, 10], dtype=np.uint8)
                            placeholder = ColorClip(size=(1920, 1080), color=color_uint8, duration=target_dur)
                            sub_clips.append(placeholder)
                    
                    # Concatenate Sub-Clips
                    if sub_clips:
                        try:
                            clip = concatenate_videoclips(sub_clips, method="compose")
                        except Exception as e:
                            print(f"Concat Error: {e}")
                            if sub_clips:
                                clip = sub_clips[0] # Fallback to first
                    
                    # Final Fallback (Global)
                    if not clip:
                        print("⚠️ No relevant footage found. Using neutral placeholder (Black Screen).")
                        color_uint8 = np.array([5, 5, 5], dtype=np.uint8)
                        clip = ColorClip(size=(1920, 1080), color=color_uint8, duration=duration)
                
                # --- Cinematic Polish ---
                if clip:
                    # 1. Color Grade
                    clip = apply_cinematic_grade(clip)
                    
                    # 2. Title Overlay
                    overlays = []
                    
                    # Main Title
                    title_overlay = create_title_clip(text, clip.duration)
                    overlays.append(title_overlay)
                    
                    # Source Attribution
                    if source_attribution:
                        attr_overlay = create_source_attribution(source_attribution, clip.duration)
                        overlays.append(attr_overlay)
                        
                    # Use CompositeVideoClip
                    clip = CompositeVideoClip([clip] + overlays)
                    
                    # 3. Attach Audio
                    if audioclip:
                        clip = clip.set_audio(audioclip)
                    
                # RENDER SEGMENT IMMEDIATELY to free resources
                seg_filename = f"temp_render_{i}.mp4"
                print(f"Rendering segment {i} to {seg_filename}...")
                
                clip.write_videofile(
                    seg_filename, 
                    fps=24, 
                    codec='libx264', 
                    audio_codec='aac',
                    threads=1,
                    preset='ultrafast', # Fast render for segments
                    ffmpeg_params=["-pix_fmt", "yuv420p"],
                    logger=None
                )
                temp_segment_files.append(seg_filename)
                temp_files_to_clean.append(seg_filename)
                
            except Exception as e:
                print(f"Error processing segment {i}: {e}")
                # Create a simple error slide or skip
                # For now, we skip
                continue
            finally:
                # Close all resources for this segment
                if clip:
                    try:
                        clip.close()
                    except:
                        pass
                for res in segment_resources:
                    try:
                        res.close()
                    except:
                        pass
            
        if not temp_segment_files:
            print("No segments generated!")
            return

        # Concatenate Files using ffmpeg
        print("Concatenating segments with ffmpeg...")
        concat_list_path = "concat_list.txt"
        temp_files_to_clean.append(concat_list_path)
        
        with open(concat_list_path, "w") as f:
            for path in temp_segment_files:
                # ffmpeg requires absolute paths or safe relative
                abs_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
                
        temp_joined = "temp_joined.mp4"
        temp_files_to_clean.append(temp_joined)
        
        # ffmpeg command
        # Use shell=True if on Windows and ffmpeg is in PATH
        # But better to use imageio_ffmpeg to be safe
        ffmpeg_exe = get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", 
            "-i", concat_list_path, "-c", "copy", temp_joined
        ]
        subprocess.run(cmd, check=True)
        
        # Apply Cinematic Overlay (Scanlines) using FFMPEG (No Python Memory)
        print("Applying cinematic overlay with ffmpeg...")
        
        # 1. Generate Overlay Image
        overlay_clip = create_scanline_overlay()
        overlay_img_path = "temp_overlay_scanlines.png"
        temp_files_to_clean.append(overlay_img_path)
        overlay_clip.save_frame(overlay_img_path, t=0)
        
        # 2. Apply Overlay with FFMPEG
        # ffmpeg -i video.mp4 -i overlay.png -filter_complex "overlay=0:0" ...
        # Note: We need to re-encode video here to burn in overlay.
        # This is where we set final bitrate/preset.
        
        cmd_overlay = [
            ffmpeg_exe, "-y", 
            "-i", temp_joined,
            "-i", overlay_img_path,
            "-filter_complex", "overlay=0:0",
            "-c:v", "libx264",
            "-preset", "faster",
            "-c:a", "aac",
            output_path
        ]
        
        print("Rendering final video...")
        subprocess.run(cmd_overlay, check=True)
        
        print(f"✅ Documentary saved to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        print("Cleaning up temporary files...")
        for f in temp_files_to_clean:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        if os.path.exists("temp_text_fallback.png"):
            os.remove("temp_text_fallback.png")
        if os.path.exists("temp_overlay_scanlines.png"):
            os.remove("temp_overlay_scanlines.png")

if __name__ == "__main__":
    # Test
    # generate_documentary_video("The history of the internet", "test_doc.mp4")
    pass
