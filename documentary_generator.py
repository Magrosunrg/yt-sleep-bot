import os
import textwrap
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
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
import asyncio
import edge_tts

import tempfile
from script_generator import ScriptGenerator
from media_manager import MediaManager

def generate_tts_audio(text, filename, voice="en-US-ChristopherNeural"):
    """Generates TTS audio using Edge TTS."""
    try:
        if os.path.exists(filename):
            os.remove(filename)
            
        async def _run_edge():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(filename)
            
        asyncio.run(_run_edge())
        
        return filename if os.path.exists(filename) else None
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

def create_text_image(text, width=1920, height=1080):
    """Creates a dark documentary style text slide."""
    img = Image.new('RGB', (width, height), (15, 15, 20)) 
    draw = ImageDraw.Draw(img)
    
    font_size = 80
    try:
        font = ImageFont.truetype("times.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

    lines = textwrap.wrap(text, width=40)
    line_height = font_size + 20
    total_text_height = len(lines) * line_height
    
    current_y = (height - total_text_height) // 2
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        
        draw.text((x+3, current_y+3), line, font=font, fill=(0, 0, 0))
        draw.text((x, current_y), line, font=font, fill=(230, 230, 230))
        current_y += line_height
        
    fd, filename = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(filename)
    return filename

def generate_documentary_video(topic_or_script, output_path="documentary_output.mp4", pexels_api_key=None, openai_api_key=None, gemini_api_key=None):
    """
    Generates a documentary style video.
    """
    print("🎬 Starting Documentary Generation...")
    
    script_gen = ScriptGenerator(openai_api_key, gemini_api_key)
    media_mgr = MediaManager(pexels_api_key)
    
    if openai_api_key or gemini_api_key:
        print("Creating script from topic...")
        segments = script_gen.generate_script(topic_or_script)
    else:
        print("Parsing provided text as script...")
        segments = script_gen.process_text(topic_or_script)
        
    if not segments:
        print("❌ Failed to generate script segments.")
        return

    clips = []
    temp_files = []
    
    for i, segment in enumerate(segments):
        print(f"Processing segment {i+1}/{len(segments)}...")
        text = segment.get("text", "")
        keywords = segment.get("keywords", "")
        
        if not text:
            continue
            
        # 1. Generate Audio
        audio_file = f"temp_doc_audio_{i}.mp3"
        voice = Voice.US_MALE_1 
        
        if generate_tts_audio(text, audio_file, voice):
            temp_files.append(audio_file)
            audio_clip = AudioFileClip(audio_file)
            duration = audio_clip.duration + 0.5 
        else:
            duration = 5.0
            audio_clip = None
            
        # 2. Get Visual (Stock Video/Image or Text Slide)
        visual_path = None
        is_video = False
        
        if media_mgr and keywords:
            print(f"Searching media for: {keywords}")
            visual_url = media_mgr.search_video(keywords)
            if visual_url:
                visual_path = f"temp_doc_vid_{i}.mp4"
                if media_mgr.download_file(visual_url, visual_path):
                    is_video = True
                    temp_files.append(visual_path)
                else:
                    visual_path = None
            
            if not visual_path:
                visual_url = media_mgr.search_image(keywords)
                if visual_url:
                    visual_path = f"temp_doc_img_{i}.jpg"
                    if media_mgr.download_file(visual_url, visual_path):
                        temp_files.append(visual_path)
                    else:
                        visual_path = None
        
        # 3. Create Clip
        clip = None
        if visual_path:
            if is_video:
                try:
                    clip = VideoFileClip(visual_path)
                    # Resize/Crop logic for 1920x1080 landscape
                    # Assuming source is HD, just fit/crop
                    
                    if clip.duration < duration:
                        # Loop video
                        clip = clip.loop(duration=duration)
                    else:
                        clip = clip.subclipped(0, duration)
                        
                    clip = clip.set_duration(duration)
                    clip = clip.without_audio()
                    
                    # Resize to 1080p height, then crop width if needed
                    # clip = clip.resized(height=1080)
                    # clip = clip.cropped(x_center=clip.w/2, width=1920)
                except Exception as e:
                    print(f"Video Error: {e}, falling back.")
                    clip = None
            else:
                clip = ImageClip(visual_path).set_duration(duration)
                # Resize image
                # clip = clip.resized(height=1080)
                # clip = clip.cropped(x_center=clip.w/2, width=1920)
        
        if not clip:
            img_path = create_text_image(text)
            temp_files.append(img_path)
            clip = ImageClip(img_path).set_duration(duration)
        
        if audio_clip:
            clip = clip.set_audio(audio_clip)
            
        clips.append(clip)
        
    if not clips:
        print("❌ No clips generated.")
        return
        
    print("Merging clips...")
    final_video = concatenate_videoclips(clips, method="compose")
    
    print(f"Writing video to {output_path}...")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", ffmpeg_params=["-pix_fmt", "yuv420p"])
    
    for f in temp_files:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    
    print("✅ Documentary Generation Complete!")
    return output_path

if __name__ == "__main__":
    pass
