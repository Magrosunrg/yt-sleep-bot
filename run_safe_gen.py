import subprocess
import time
import sys
import os

MAX_RETRIES = 5
SCRIPT_TO_RUN = "simulate_gui_story.py"

def run_safely():
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🚀 Attempt {attempt}/{MAX_RETRIES} to run {SCRIPT_TO_RUN}...")
        
        start_time = time.time()
        
        # Run the script as a subprocess
        # Using python executable
        cmd = [sys.executable, SCRIPT_TO_RUN]
        
        try:
            # We want to see output in real-time if possible, but also capture it
            # For simplicity, let's just let it print to stdout/stderr and wait
            process = subprocess.run(cmd, check=False)
            
            exit_code = process.returncode
            duration = time.time() - start_time
            
            print(f"🏁 Attempt {attempt} finished with exit code {exit_code} in {duration:.1f}s")
            
            if exit_code == 0:
                print("✅ Success! Video generation completed.")
                return True
            else:
                print(f"❌ Attempt {attempt} failed (exit code {exit_code}).")
                
        except Exception as e:
            print(f"❌ Attempt {attempt} encountered an exception running subprocess: {e}")
        
        # Wait before retrying
        if attempt < MAX_RETRIES:
            wait_time = 10
            print(f"⏳ Waiting {wait_time}s before next attempt...")
            time.sleep(wait_time)
            
    return False

if __name__ == "__main__":
    success = run_safely()
    if not success:
        print("\n💀 All attempts failed.")
        sys.exit(1)
    else:
        sys.exit(0)
