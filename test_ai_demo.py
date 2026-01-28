
import os
import sys
import random
import time
import traceback
from long_video_mgr import LongVideoManager

def run_demo():
    log_file = open("demo_final.log", "w", encoding="utf-8")
    
    def log(msg):
        print(msg)
        log_file.write(msg + "\n")
        log_file.flush()

    log("🚀 Starting Quick AI Visual Demo...")
    
    try:
        # 1. Random Topic
        topics = [
            "A glowing cybernetic city",
            "Geometric shapes floating in space",
            "A peaceful digital forest",
            "Abstract quantum fields"
        ]
        topic = random.choice(topics)
        log(f"🎨 Chosen Topic: {topic}")
        
        # 2. Initialize Manager
        log("Initializing LongVideoManager...")
        mgr = LongVideoManager()
        
        # 3. Generate Short Video
        output_file = "demo_ai_visual_test.mp4"
        duration = 20 # Keep it short for testing
        
        # Ensure output file doesn't exist
        if os.path.exists(output_file):
            os.remove(output_file)
            
        log(f"⏳ Generating {duration}s demo video to {output_file}...")
        
        # We need to monkey-patch or configure the manager to be verbose if needed
        # But for now let's just run it
        
        final_file = mgr.create_long_video(
            topic=topic, 
            num_facts=1, 
            output_file=output_file, 
            target_duration=duration
        )
        
        if final_file and os.path.exists(final_file):
            log(f"✅ Success! Demo video created at: {final_file}")
            log(f"File size: {os.path.getsize(final_file)} bytes")
        else:
            log("❌ Failed: Video file was not created.")
            
    except Exception as e:
        log(f"❌ CRITICAL ERROR: {e}")
        traceback.print_exc(file=log_file)
    finally:
        log("Done.")
        log_file.close()

if __name__ == "__main__":
    run_demo()
