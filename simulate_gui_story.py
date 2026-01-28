import story_shorts_mgr
import os
import sys
from datetime import datetime

# Force UTF-8 for stdout/stderr
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def status_update(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
    line = f"{timestamp}{msg}"
    print(line)
    try:
        with open("sim_log_internal.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def run_simulation():
    prompt = "Tell the story of 'Fight Club' from Tyler Durden's perspective"
    print(f"--- Simulating GUI 'Story Shorts' generation with prompt: '{prompt}' ---")
    
    # Sanitize filename (logic from gui_app.py)
    safe_name = "".join([c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
    out_file = f"story_{safe_name}.mp4"
    
    try:
        out = story_shorts_mgr.create_story_video(prompt, output_file=out_file, status_callback=status_update)
        
        if out and os.path.exists(out):
            print(f"\nSUCCESS: Video saved to: {os.path.abspath(out)}")
            sys.exit(0)
        else:
            print("\nFAILURE: create_story_video returned None or file does not exist.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nEXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_simulation()
