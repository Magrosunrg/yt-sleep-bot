import argparse
import os
import sys
import threading
import time

# Ensure current directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def progress_callback(percentage):
    """Simple progress bar for CLI/Colab"""
    bar_length = 40
    filled_length = int(bar_length * percentage // 100)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    sys.stdout.write(f'\rProgress: |{bar}| {percentage}% Complete')
    sys.stdout.flush()
    if percentage == 100:
        print()

def run_sleep_video(args):
    try:
        from long_video_mgr import LongVideoManager
        mgr = LongVideoManager()
        
        topic = args.topic or "Relaxing Nature"
        num_facts = int(args.num_facts) if args.num_facts else 15
        output = args.output or f"sleep_{topic.replace(' ', '_')}.mp4"
        duration = int(args.duration) if args.duration else 7200 # 2 hours default
        
        print(f"🌙 Starting Sleep Video: {topic}")
        print(f"   Facts: {num_facts}")
        print(f"   Target Duration: {duration}s")
        print(f"   Output: {output}")
        print(f"   ⚡ Optimization: FFmpeg Filters Enabled (Fast Render)")
        
        # Check for custom script file
        custom_script = None
        if args.script_file and os.path.exists(args.script_file):
            with open(args.script_file, 'r', encoding='utf-8') as f:
                custom_script = f.read()
            print("   Using custom script file.")
            
        mgr.create_long_video(
            topic=topic,
            num_facts=num_facts,
            output_file=output,
            outro_duration=duration,
            custom_script=custom_script,
            progress_callback=progress_callback,
            use_ai_visuals=getattr(args, 'use_ai', False)
        )
        print(f"\n✅ Done! Video saved to: {os.path.abspath(output)}")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure you have installed all requirements.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def run_story_short(args):
    try:
        import story_shorts_mgr
        
        prompt = args.prompt
        if not prompt:
            print("❌ Error: --prompt is required for story mode.")
            return
            
        output = args.output or f"story_{prompt[:10].replace(' ', '_')}.mp4"
        
        print(f"📖 Starting Story Short: {prompt}")
        print(f"   Output: {output}")
        
        def status_update(msg):
            print(f"   [STATUS] {msg}")
            
        story_shorts_mgr.create_story_video(
            user_prompt=prompt,
            output_file=output,
            status_callback=status_update,
            use_ai_visuals=getattr(args, 'use_ai', False)
        )
        print(f"\n✅ Done! Video saved to: {os.path.abspath(output)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Colab Runner for YT Bot")
    # Global arguments (can be used before subcommand)
    parser.add_argument("--use_ai", action="store_true", help="Use AI Visuals (Global Flag)")
    
    subparsers = parser.add_subparsers(dest="mode", help="Mode: sleep or story")
    
    # Sleep Mode
    sleep_parser = subparsers.add_parser("sleep", help="Generate Sleep/Relaxation Video")
    sleep_parser.add_argument("--topic", type=str, help="Topic for facts (e.g. 'Space', 'Ocean')")
    sleep_parser.add_argument("--num_facts", type=int, default=15, help="Number of facts (default: 15)")
    sleep_parser.add_argument("--duration", type=int, default=7200, help="Target duration in seconds (default: 7200)")
    sleep_parser.add_argument("--output", type=str, help="Output filename")
    sleep_parser.add_argument("--script_file", type=str, help="Path to custom script text file")
    # Add use_ai here too for compatibility if user puts it after subcommand
    sleep_parser.add_argument("--use_ai", action="store_true", help="Use AI Visuals")
    
    # Story Mode
    story_parser = subparsers.add_parser("story", help="Generate Story Short")
    story_parser.add_argument("--prompt", type=str, required=True, help="Story prompt")
    story_parser.add_argument("--output", type=str, help="Output filename")
    story_parser.add_argument("--use_ai", action="store_true", help="Use AI Visuals instead of movie clips")
    
    args = parser.parse_args()
    
    if args.mode == "sleep":
        run_sleep_video(args)
    elif args.mode == "story":
        run_story_short(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
