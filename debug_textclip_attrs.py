
import sys
import os

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "Ai-couple-vid-gen-main", "Ai-couple-vid-gen-main")
src_path = os.path.join(project_root, "src")
sys.path.append(src_path)

try:
    import moviepy
    print(f"MoviePy Version: {moviepy.__version__}")
    
    from moviepy import TextClip, ColorClip
    
    print("Inspect TextClip:")
    tc = TextClip(text="Test", font_size=24, font=r"C:/Windows/Fonts/arial.ttf", color=(255,255,255))
    print(f"TextClip type: {type(tc)}")
    print(f"Has set_position: {hasattr(tc, 'set_position')}")
    print(f"Has set_start: {hasattr(tc, 'set_start')}")
    print(f"Has set_duration: {hasattr(tc, 'set_duration')}")
    print(f"Attributes: {dir(tc)}")

except Exception as e:
    print(f"Error: {e}")
