import os
import re
import pickle
import json
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog, ttk
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from shorts_generator import run_generation
import quiz_generator
from short_title import generate_title_and_description
from datetime import datetime, timedelta
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from instagrapi import Client  
from tiktok_uploader.upload import upload_video, upload_videos
from tiktok_uploader.auth import AuthBackend

UPLOAD_URL = "https://www.tiktok.com/upload"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE = "token.pickle"

INSTAGRAM_USERNAME = "love.couplevids"
INSTAGRAM_PASSWORD = "mAGGROSU123!"
INSTAGRAM_SESSION_FILE = "insta_session.json"

instagram_client = None  # Global session

def upload_to_tiktok(video_path, caption, output_callback):
    try:
        add_timestamped_message(output_callback, "🌐 Uploading to TikTok using tiktok-uploader...")
        # Use CREDENTIALS for credential-based authentication if BROWSER is not available
        upload_video(
            video_path,
            caption,
            auth_backend=AuthBackend.CREDENTIALS  # Use CREDENTIALS if BROWSER is not available
        )
        add_timestamped_message(output_callback, "✅ Uploaded to TikTok successfully.")
    except Exception as e:
        add_timestamped_message(output_callback, f"❌ TikTok upload failed: {e}")

def authenticate_youtube():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)

def analyze_video_and_generate_metadata(video_path, part_number=1, total_parts=1):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    title, description, tags = generate_title_and_description(part_number=part_number, total_parts=total_parts)
    return title, description, tags

def upload_short_youtube(youtube, video_path, title, description, tags, thumbnail_path=None):
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public"
        }
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    response = request.execute()
    video_id = response.get("id")

    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            # print(f"🖼️ Uploading thumbnail: {thumbnail_path}") # Use UI log if possible, but here we don't have 'output'
            media_thumb = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            youtube.thumbnails().set(videoId=video_id, media_body=media_thumb).execute()
        except Exception as e:
            print(f"⚠️ Thumbnail upload failed: {e}")

    return video_id

def login_instagram(output):
    cl = Client()

    if os.path.exists(INSTAGRAM_SESSION_FILE):
        cl.load_settings(INSTAGRAM_SESSION_FILE)
        try:
            cl.get_timeline_feed()
            add_timestamped_message(output, "🔑 Loaded existing Instagram session.")
            return cl
        except Exception:
            add_timestamped_message(output, "⚠️ Existing session invalid, re-logging in...")

    try:
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        add_timestamped_message(output, "✅ Logged into Instagram successfully.")
        cl.dump_settings(INSTAGRAM_SESSION_FILE)
        return cl

    except Exception as e:
        if "challenge_required" in str(e):
            add_timestamped_message(output, "🔐 Instagram challenge required.")

            try:
                cl.get_timeline_feed()  # Forces challenge flow to initiate properly
            except Exception:
                pass

            try:
                cl.challenge_resolve()  # Step 1: resolve challenge
                cl.challenge_select_verify_method(0)  # Step 2: choose 0 (usually SMS or email)
                cl.challenge_code_send()  # Step 3: send code

                # ✅ Tkinter popup for code
                code = simpledialog.askstring("Instagram Verification", "Enter the verification code you received via SMS or email:")
                cl.challenge_code_verify(code)  # Step 4: submit code

                add_timestamped_message(output, "✅ Challenge passed.")
                cl.dump_settings(INSTAGRAM_SESSION_FILE)
                return cl

            except Exception as ce:
                add_timestamped_message(output, f"❌ Challenge failed: {ce}")
                return None
        else:
            add_timestamped_message(output, f"❌ Login error: {e}")
            return None


def upload_short_instagram(video_path, caption, output):
    global instagram_client
    if instagram_client is None:
        instagram_client = login_instagram(output)

    if instagram_client is None:
        add_timestamped_message(output, "❌ Instagram upload skipped due to login failure.")
        return

    try:
        instagram_client.clip_upload(video_path, caption)
        add_timestamped_message(output, "📲 Uploaded to Instagram Reels successfully.")
    except Exception as e:
        add_timestamped_message(output, f"❌ Instagram upload failed: {e}")

stop_flag = threading.Event()
quiz_stop_flag = threading.Event()

def add_timestamped_message(output, message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
    output.insert(tk.END, timestamp + message + "\n")
    output.see(tk.END)

def safe_delete(path, output=None):
    import gc
    for _ in range(20):  # Try more times
        try:
            gc.collect()  # Force garbage collection to help release file handles
            if os.path.exists(path):
                os.remove(path)
            if not os.path.exists(path):
                if output:
                    add_timestamped_message(output, f"🗑️ Deleted: {path}")
                return
        except PermissionError:
            time.sleep(0.5)  # Wait a bit longer
    if output:
        add_timestamped_message(output, f"⚠️ Could not delete {path} after multiple attempts.")

def delete_all_generated_shorts(output=None):
    dir_path = "generated_shorts"
    if not os.path.exists(dir_path):
        return
    for f in os.listdir(dir_path):
        file_path = os.path.join(dir_path, f)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                if output:
                    add_timestamped_message(output, f"🗑️ Deleted: {file_path}")
            except Exception as e:
                if output:
                    add_timestamped_message(output, f"⚠️ Could not delete {file_path}: {e}")

def generate_and_upload_periodically(output, post_to_yt_var, post_to_ig_var, post_to_tt_var):
    def task():
        while not stop_flag.is_set():
            # Always generate new shorts before uploading
            add_timestamped_message(output, "🎥 Generating new shorts...")
            run_generation()

            video_dir = "generated_shorts"
            short_files = [f for f in os.listdir(video_dir) if re.match(r"short_part\d+\.mp4", f)]

            # Sort by part number
            short_files.sort(key=lambda f: int(re.search(r"\d+", f).group()))

            if not short_files:
                add_timestamped_message(output, "❌ No short_part files found.")
                return

            total_parts = len(short_files)
            for idx, filename in enumerate(short_files):
                if stop_flag.is_set():
                    break

                try:
                    part_num = int(re.search(r"\d+", filename).group())
                    video_path = os.path.join(video_dir, filename)

                    add_timestamped_message(output, f"🎬 Processing {filename}...")

                    title, description, tags = analyze_video_and_generate_metadata(
                        video_path, part_number=part_num, total_parts=total_parts
                    )

                    if post_to_yt_var.get():
                        youtube = authenticate_youtube()
                        add_timestamped_message(output, "📤 Uploading to YouTube...")
                        try:
                            video_id = upload_short_youtube(youtube, video_path, title, description, tags)
                            add_timestamped_message(output, f"✅ Uploaded to YouTube: https://www.youtube.com/shorts/{video_id}")
                        except Exception as e:
                            if "quotaExceeded" in str(e):
                                add_timestamped_message(output, "⛔ YouTube quota exceeded. Stopping.")
                                stop_flag.set()
                                break
                            add_timestamped_message(output, f"❌ YouTube upload failed: {e}")

                    if post_to_ig_var.get():
                        add_timestamped_message(output, "📤 Uploading to Instagram Reels...")
                        upload_short_instagram(video_path, title + "\n\n" + description, output)

                    if post_to_tt_var.get():
                        add_timestamped_message(output, "📤 Uploading to TikTok...")
                        upload_to_tiktok(video_path, title + "\n\n" + description, output)

                    safe_delete(video_path, output)
                    time.sleep(30)  # Optional wait between uploads

                except Exception as e:
                    add_timestamped_message(output, f"❌ Error processing {filename}: {e}")

            if stop_flag.is_set():
                break

            # Delete all files in generated_shorts after last part is posted
            delete_all_generated_shorts(output)

            add_timestamped_message(output, "⏳ All parts uploaded. Waiting 60 minutes before next cycle...")
            time.sleep(1800)  # 30 minutes

    threading.Thread(target=task, daemon=True).start()

long_quiz_stop_flag = threading.Event()

def long_quiz_auto_loop(output, post_yt_var, freq_scale_var, karaoke_var=None):
    def task():
        while not long_quiz_stop_flag.is_set():
            is_karaoke = karaoke_var.get() if karaoke_var else False
            mode_str = "Karaoke" if is_karaoke else "Long Quiz"
            
            add_timestamped_message(output, f"🎬 Starting {mode_str} Generation Cycle...")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_shorts/{'karaoke' if is_karaoke else 'long_quiz'}_{timestamp}.mp4"
            os.makedirs("generated_shorts", exist_ok=True)
            
            try:
                # Generate
                add_timestamped_message(output, f"🎥 Generating {mode_str} Video...")
                
                chosen_title = ""
                desc = ""
                tags = []
                thumbnail_path = None
                
                if is_karaoke:
                    meta = karaoke_generator.create_karaoke_video(filename)
                    
                    if not meta:
                        add_timestamped_message(output, "❌ Karaoke Generation Failed (No Metadata returned). Skipping...")
                        time.sleep(10)
                        continue
                        
                    chosen_title = meta.get('title', 'Karaoke Video')
                    desc = meta.get('description', 'Sing along!')
                    tags = meta.get('tags', ['karaoke'])
                    thumbnail_path = meta.get('thumbnail')
                    add_timestamped_message(output, f"✅ Karaoke Generated: {filename}")
                    if thumbnail_path:
                        add_timestamped_message(output, f"🖼️ Thumbnail: {thumbnail_path}")
                else:
                    used_qs = quiz_generator.generate_long_quiz_video(filename)
                    add_timestamped_message(output, f"✅ Long Quiz Generated: {filename}")
                    
                    # Metadata (Legacy Logic)
                    import random
                    titles = [
                        "Ultimate General Knowledge Quiz! Can you score 100%?",
                        "20 Minute Trivia Challenge - Test Your Knowledge!",
                        "Hardest General Knowledge Quiz Ever?",
                        "Relaxing Trivia Quiz - 20 Minutes of Fun Facts",
                        "Bf & Gf Quiz Challenge - Who is Smarter? (Full Episode)"
                    ]
                    
                    chosen_title = random.choice(titles)
                    desc = "Welcome to the Ultimate General Knowledge Quiz! 🧠\n\n"
                    desc += "Test your knowledge with these multiple choice questions. You have 10 seconds to think about each answer!\n\n"
                    desc += "Comment your score below! 👇\n\n"
                    desc += "Timestamps:\n0:00 Intro\n"
                    if used_qs:
                        desc += "Questions covered:\n"
                        for i, q in enumerate(used_qs):
                            desc += f"- {q['q']}\n"
                    desc += "\n#quiz #trivia #generalknowledge #education #learning #test #exam"
                    tags = ["quiz", "trivia", "general knowledge", "test", "exam", "education", "learning", "documentary", "fun facts"]

                if not os.path.exists(filename):
                     add_timestamped_message(output, f"❌ {mode_str} generation failed: File not created.")
                     time.sleep(60)
                     continue

                # Upload to YouTube
                if post_yt_var.get():
                    try:
                        add_timestamped_message(output, "📤 Uploading Long Video to YouTube...")
                        youtube = authenticate_youtube()
                        vid_id = upload_short_youtube(youtube, filename, chosen_title, desc, tags, thumbnail_path=thumbnail_path)
                        add_timestamped_message(output, f"✅ YouTube Long Video Upload Success: https://youtu.be/{vid_id}")
                    except Exception as e:
                        add_timestamped_message(output, f"❌ YouTube Upload Failed: {e}")

                # Cleanup
                safe_delete(filename, output)
                if thumbnail_path: safe_delete(thumbnail_path, output)

            except Exception as e:
                add_timestamped_message(output, f"❌ Error in {mode_str} Loop: {e}")

            if long_quiz_stop_flag.is_set():
                break
            
            # Wait
            hours = freq_scale_var.get()
            wait_seconds = int(hours * 3600)
            add_timestamped_message(output, f"⏳ Long Video: Waiting {hours} hours before next cycle...")
            
            for _ in range(wait_seconds // 5):
                if long_quiz_stop_flag.is_set():
                    break
                time.sleep(5)
                
    threading.Thread(target=task, daemon=True).start()

def quiz_auto_loop(output, post_yt_var, post_ig_var, freq_scale_var, sched_mode_var=None, daily_time_var=None):
    def task():
        while not quiz_stop_flag.is_set():
            # --- Scheduling Logic (Start of Loop) ---
            if sched_mode_var and sched_mode_var.get() == "daily" and daily_time_var:
                target_str = daily_time_var.get()
                try:
                    now = datetime.now()
                    target_time = datetime.strptime(target_str, "%H:%M").time()
                    target_dt = datetime.combine(now.date(), target_time)
                    
                    if target_dt <= now:
                        # Target time passed for today, schedule for tomorrow
                        target_dt += timedelta(days=1)
                    
                    wait_seconds = (target_dt - now).total_seconds()
                    add_timestamped_message(output, f"⏳ Daily Mode: Waiting until {target_dt.strftime('%H:%M')} ({int(wait_seconds)}s)...")
                    
                    # Sleep in chunks
                    chunk = 5
                    while wait_seconds > 0:
                        if quiz_stop_flag.is_set(): return
                        sleep_time = min(chunk, wait_seconds)
                        time.sleep(sleep_time)
                        wait_seconds -= sleep_time
                        
                except ValueError:
                    add_timestamped_message(output, f"❌ Invalid Time Format '{target_str}'. Defaulting to immediate run.")
            
            # --- Generation & Upload ---
            add_timestamped_message(output, "🧠 Starting Quiz Generation Cycle...")
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_shorts/quiz_{timestamp}.mp4"
            
            # Ensure directory exists
            os.makedirs("generated_shorts", exist_ok=True)
            
            try:
                # Generate Quiz (Force Auto Mode for automation)
                add_timestamped_message(output, "🎥 Generating Quiz Video...")
                used_qs = quiz_generator.generate_quiz_video(questions=None, output_path=filename, auto_mode=True)
                
                if not os.path.exists(filename):
                    add_timestamped_message(output, "❌ Quiz generation failed: File not created.")
                    time.sleep(60)
                    continue

                add_timestamped_message(output, f"✅ Quiz Generated: {filename}")

                # Prepare Metadata
                import random
                
                # Check for generated metadata
                base_name = os.path.splitext(filename)[0]
                meta_path = f"{base_name}_meta.txt"
                
                chosen_title = ""
                desc = ""
                
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            for line in lines:
                                if line.startswith("TITLE:"):
                                    chosen_title = line.replace("TITLE:", "").strip()
                                elif line.startswith("DESCRIPTION:"):
                                    desc += line.replace("DESCRIPTION:", "").strip() + "\n"
                        add_timestamped_message(output, f"📄 Using Generated Metadata: {chosen_title}")
                    except Exception as e:
                        add_timestamped_message(output, f"⚠️ Failed to read metadata: {e}")
                
                if not chosen_title:
                    title_templates = [
                        "ONLY 1% Can Pass This! Who is smarter? #shorts",
                        "Send this to your Partner NOW! Test their IQ! #shorts",
                        "Couples Quiz: If you miss one, you owe me dinner! #shorts",
                        "Bet you can't get 100%! Who is the smart one? #shorts",
                        "Relationship Test: Who is actually smarter? #shorts",
                        "FAIL = BUY DINNER! Couples General Knowledge Quiz #shorts",
                        "Can you beat your GF/BF? Ultimate Trivia! #shorts"
                    ]
                    chosen_title = random.choice(title_templates)
                    desc = "Test your partner! #shorts #quiz #couplegoals"

                tags = ["shorts", "quiz", "trivia", "couples", "relationship", "test", "boyfriend", "girlfriend"]
                
                cta_templates = [
                    "If you missed any, you have to buy dinner! 🍕 Comment your score!",
                    "Tag your partner and see if they can beat you! 👇",
                    "Who is the smart one in the relationship? Prove it below! 🧠",
                    "Send this to 3 friends or bad luck for 7 years! 😱 (Just kidding, but comment score!)",
                    "Did you get 100%? I bet you didn't! 👇"
                ]

                chosen_cta = random.choice(cta_templates)
                
                # Construct Description
                if not desc:
                    desc = f"{chosen_cta}\n\n"
                else:
                    desc = f"{desc}\n\n{chosen_cta}\n\n"
                    
                if used_qs:
                    for i, q in enumerate(used_qs):
                        desc += f"Q{i+1}: {q['q']}\n"
                desc += "\nSubscribe for more daily quizzes!\n#quiz #trivia #knowledge #education #shorts #fyp #foryou #couplegoals #challenge"
                
                if not tags:
                    tags = ["quiz", "trivia", "generalknowledge", "shorts", "learn", "education", "challenge", "couple", "bf", "gf"]

                # Upload YouTube
                if post_yt_var.get():
                    try:
                        add_timestamped_message(output, "📤 Uploading to YouTube...")
                        youtube = authenticate_youtube()
                        vid_id = upload_short_youtube(youtube, filename, chosen_title, desc, tags)
                        add_timestamped_message(output, f"✅ YouTube Upload Success: https://youtube.com/shorts/{vid_id}")
                    except Exception as e:
                        add_timestamped_message(output, f"❌ YouTube Upload Failed: {e}")

                # Upload Instagram
                if post_ig_var.get():
                    try:
                        add_timestamped_message(output, "📤 Uploading to Instagram...")
                        upload_short_instagram(filename, chosen_title + "\n\n" + desc, output)
                    except Exception as e:
                        add_timestamped_message(output, f"❌ Instagram Upload Failed: {e}")

                # Cleanup
                safe_delete(filename, output)

            except Exception as e:
                add_timestamped_message(output, f"❌ Error in Quiz Loop: {e}")

            if quiz_stop_flag.is_set():
                break
            
            # --- Wait for next cycle (Interval Mode) ---
            # If Daily Mode, the loop restarts and hits the 'Wait Logic' at the top, calculating time to TOMORROW's slot.
            if not (sched_mode_var and sched_mode_var.get() == "daily"):
                hours = freq_scale_var.get()
                wait_seconds = int(hours * 3600)
                add_timestamped_message(output, f"⏳ Waiting {hours} hours ({wait_seconds}s) before next quiz...")
                
                # Sleep in chunks to allow responsive stop
                for _ in range(wait_seconds // 5):
                    if quiz_stop_flag.is_set():
                        break
                    time.sleep(5)
            
            if quiz_stop_flag.is_set():
                break
                
    threading.Thread(target=task, daemon=True).start()

def stop_task():
    stop_flag.set()

import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
import quiz_generator
import karaoke_generator
from story_shorts_mgr import create_story_video
from long_video_mgr import LongVideoManager

def run_gui():
    root = tk.Tk()
    root.title("Auto Content Suite")
    root.geometry("700x850")

    # Create Tabs
    notebook = ttk.Notebook(root)
    notebook.pack(expand=True, fill="both")

    # --- Tab 1: Shorts Auto Uploader ---
    tab1 = tk.Frame(notebook)
    notebook.add(tab1, text="Shorts Auto Uploader")

    output = tk.Text(tab1, height=16, width=80)
    output.grid(row=0, column=0, columnspan=3, pady=10, padx=10)

    post_to_yt = tk.BooleanVar(value=True)
    post_to_ig = tk.BooleanVar(value=True)
    post_to_tt = tk.BooleanVar(value=True)

    tk.Checkbutton(tab1, text="Upload to YouTube", variable=post_to_yt).grid(row=1, column=0, sticky="w", padx=10)
    tk.Checkbutton(tab1, text="Upload to Instagram", variable=post_to_ig).grid(row=2, column=0, sticky="w", padx=10)
    tk.Checkbutton(tab1, text="Upload to TikTok", variable=post_to_tt).grid(row=3, column=0, sticky="w", padx=10)

    def on_start():
        stop_flag.clear()
        output.delete("1.0", tk.END)
        generate_and_upload_periodically(output, post_to_yt, post_to_ig, post_to_tt)

    tk.Button(tab1, text="▶ Start", command=on_start, bg="green", fg="white", width=10).grid(row=1, column=1, pady=10)
    tk.Button(tab1, text="⏹ Stop", command=stop_task, bg="red", fg="white", width=10).grid(row=2, column=1, pady=10)

    # --- Tab 2: Quiz Generator ---
    tab2 = tk.Frame(notebook)
    notebook.add(tab2, text="Quiz Generator")

    tk.Label(tab2, text="Quiz Video Generator", font=("Arial", 16, "bold")).pack(pady=10)
    
    # Info Label about Audio
    tk.Label(tab2, text="Tip: Place 'funny_bg.mp3' in 'assets/' folder for background music.", fg="gray", font=("Arial", 9)).pack()
    
    out_frame = tk.Frame(tab2)
    out_frame.pack(pady=5)
    tk.Label(out_frame, text="Output File:").pack(side="left")
    out_path_var = tk.StringVar(value="quiz_output.mp4")
    tk.Entry(out_frame, textvariable=out_path_var, width=40).pack(side="left", padx=5)
    
    def browse_quiz_out():
        f = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 files", "*.mp4")])
        if f:
            out_path_var.set(f)
            
    tk.Button(out_frame, text="Browse", command=browse_quiz_out).pack(side="left")

    def run_quiz_gen():
        out_file = out_path_var.get()
        # Always auto mode
        is_auto = True
        questions = []
        
        gen_btn.config(state="disabled", text="Generating...")
        
        def worker():
            try:
                used_qs = quiz_generator.generate_quiz_video(questions, out_file, auto_mode=is_auto)
                msg = f"Quiz video saved to:\n{out_file}"
                if is_auto and used_qs:
                    msg += f"\n\nAuto-Generated {len(used_qs)} questions."
                    # No longer displaying list in removed text box
                
                messagebox.showinfo("Success", msg)
            except Exception as e:
                messagebox.showerror("Error", f"Generation failed:\n{e}")
            finally:
                gen_btn.config(state="normal", text="Generate Quiz Video")

        threading.Thread(target=worker, daemon=True).start()

    gen_btn = tk.Button(tab2, text="Generate Quiz Video", command=run_quiz_gen, bg="#00acc1", fg="white", font=("Arial", 12, "bold"))
    gen_btn.pack(pady=10)

    # --- Long Video Button ---
    def run_long_quiz_gen():
        out_file = "long_quiz_output.mp4"
        
        is_karaoke = karaoke_long_var.get()
        btn_text = "Generating Karaoke..." if is_karaoke else "Generating Long Video..."
        long_gen_btn.config(state="disabled", text=btn_text)
        
        def worker():
            try:
                if is_karaoke:
                    meta = karaoke_generator.create_karaoke_video(out_file)
                    msg = f"Karaoke saved to:\n{os.path.abspath(out_file)}\nTitle: {meta.get('title')}"
                else:
                    # Call the long video generator
                    used_qs = quiz_generator.generate_long_quiz_video(out_file)
                    msg = f"Long Quiz video saved to:\n{os.path.abspath(out_file)}\n\nUsed {len(used_qs)} questions."
                messagebox.showinfo("Success", msg)
            except Exception as e:
                messagebox.showerror("Error", f"Generation failed:\n{e}")
            finally:
                long_gen_btn.config(state="normal", text="Generate Long Quiz Video (16:9)")

        threading.Thread(target=worker, daemon=True).start()

    long_gen_btn = tk.Button(tab2, text="Generate Long Quiz Video (16:9)", command=run_long_quiz_gen, bg="#ff9800", fg="white", font=("Arial", 12, "bold"))
    long_gen_btn.pack(pady=5)

    # --- Tab 3: Sleep Video Generator ---
    tab3 = tk.Frame(notebook)
    notebook.add(tab3, text="Sleep Video Generator")

    tk.Label(tab3, text="Sleep Video Generator (AI Visuals)", font=("Arial", 16, "bold")).pack(pady=10)

    # Topic Input
    topic_frame = tk.Frame(tab3)
    topic_frame.pack(pady=5)
    tk.Label(topic_frame, text="Topic:").pack(side="left")
    topic_var = tk.StringVar(value="Universe Mysteries")
    tk.Entry(topic_frame, textvariable=topic_var, width=40).pack(side="left", padx=5)

    # Duration Input
    dur_frame = tk.Frame(tab3)
    dur_frame.pack(pady=5)
    tk.Label(dur_frame, text="Duration (Hours):").pack(side="left")
    duration_var = tk.DoubleVar(value=2.0)
    tk.Scale(dur_frame, variable=duration_var, from_=0.05, to=10.0, resolution=0.05, orient="horizontal", length=200).pack(side="left", padx=5)

    # Custom Script Input
    tk.Label(tab3, text="Custom Script (Optional - Leave empty for auto):", font=("Arial", 10, "bold")).pack(pady=(10, 0))
    script_text = tk.Text(tab3, height=10, width=60)
    script_text.pack(pady=5)

    # Options
    sleep_opts_frame = tk.Frame(tab3)
    sleep_opts_frame.pack(pady=10)
    post_sleep_yt = tk.BooleanVar(value=False)
    tk.Checkbutton(sleep_opts_frame, text="Upload to YouTube", variable=post_sleep_yt).pack(side="left", padx=10)

    # Output Log for Tab 3
    sleep_output = tk.Text(tab3, height=10, width=80)
    sleep_output.pack(pady=10)

    sleep_stop_flag = threading.Event()

    def sleep_video_auto_loop():
        topic = topic_var.get()
        duration_hours = duration_var.get()
        custom_script = script_text.get("1.0", tk.END).strip()
        if not custom_script:
            custom_script = None
        
        should_upload = post_sleep_yt.get()

        def task():
            while not sleep_stop_flag.is_set():
                add_timestamped_message(sleep_output, f"🎬 Starting Sleep Video Generation for topic: {topic}...")
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).strip("_")
                filename = f"generated_shorts/sleep_{safe_topic}_{timestamp}.mp4"
                os.makedirs("generated_shorts", exist_ok=True)

                try:
                    mgr = LongVideoManager()
                    # Calculate duration in seconds
                    target_seconds = int(duration_hours * 3600)
                    
                    final_video = mgr.create_long_video(
                        topic=topic,
                        output_file=filename,
                        target_duration=target_seconds,
                        custom_script=custom_script
                    )

                    if final_video and os.path.exists(final_video):
                        add_timestamped_message(sleep_output, f"✅ Sleep Video Generated: {final_video}")
                        
                        if should_upload:
                            add_timestamped_message(sleep_output, "📤 Uploading to YouTube...")
                            try:
                                youtube = authenticate_youtube()
                                title = f"Sleep to {topic} | Deep Sleep & Relaxation"
                                desc = f"Relax and sleep while learning about {topic}. \n\n#sleep #relaxation #science #{safe_topic}"
                                tags = ["sleep", "relaxation", "science", "documentary", topic, "calm"]
                                
                                vid_id = upload_short_youtube(youtube, final_video, title, desc, tags)
                                add_timestamped_message(sleep_output, f"✅ YouTube Upload Success: https://youtu.be/{vid_id}")
                                
                                # Cleanup after upload
                                safe_delete(final_video, sleep_output)
                            except Exception as e:
                                add_timestamped_message(sleep_output, f"❌ YouTube Upload Failed: {e}")
                    else:
                        add_timestamped_message(sleep_output, "❌ Generation failed (No video file).")

                except Exception as e:
                    add_timestamped_message(sleep_output, f"❌ Error in Sleep Video Loop: {e}")

                if sleep_stop_flag.is_set():
                    break
                
                # Wait for next cycle (e.g., 24 hours or user defined - hardcoded to 24h for now as these are long)
                wait_hours = 24
                add_timestamped_message(sleep_output, f"⏳ Waiting {wait_hours} hours before next sleep video...")
                for _ in range(int(wait_hours * 3600 / 5)):
                    if sleep_stop_flag.is_set(): break
                    time.sleep(5)

        threading.Thread(target=task, daemon=True).start()

    def start_sleep_loop():
        sleep_stop_flag.clear()
        sleep_video_auto_loop()

    def stop_sleep_loop():
        sleep_stop_flag.set()
        add_timestamped_message(sleep_output, "🛑 Stopping Sleep Video Loop...")

    def generate_sleep_once():
        topic = topic_var.get()
        duration_hours = duration_var.get()
        custom_script = script_text.get("1.0", tk.END).strip()
        if not custom_script: custom_script = None
        should_upload = post_sleep_yt.get()

        btn_once.config(state="disabled", text="Generating...")

        def worker():
            add_timestamped_message(sleep_output, f"🎬 Starting Single Sleep Video Generation for topic: {topic}...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).strip("_")
            filename = f"generated_shorts/sleep_{safe_topic}_{timestamp}.mp4"
            os.makedirs("generated_shorts", exist_ok=True)

            try:
                mgr = LongVideoManager()
                target_seconds = int(duration_hours * 3600)
                final_video = mgr.create_long_video(
                    topic=topic,
                    output_file=filename,
                    target_duration=target_seconds,
                    custom_script=custom_script
                )
                
                if final_video and os.path.exists(final_video):
                    msg = f"✅ Sleep Video Generated: {os.path.abspath(final_video)}"
                    add_timestamped_message(sleep_output, msg)
                    messagebox.showinfo("Success", msg)

                    if should_upload:
                        add_timestamped_message(sleep_output, "📤 Uploading to YouTube...")
                        try:
                            youtube = authenticate_youtube()
                            title = f"Sleep to {topic} | Deep Sleep & Relaxation"
                            desc = f"Relax and sleep while learning about {topic}. \n\n#sleep #relaxation #science #{safe_topic}"
                            tags = ["sleep", "relaxation", "science", "documentary", topic, "calm"]
                            vid_id = upload_short_youtube(youtube, final_video, title, desc, tags)
                            add_timestamped_message(sleep_output, f"✅ YouTube Upload Success: https://youtu.be/{vid_id}")
                            safe_delete(final_video, sleep_output)
                        except Exception as e:
                            add_timestamped_message(sleep_output, f"❌ YouTube Upload Failed: {e}")
                else:
                    add_timestamped_message(sleep_output, "❌ Generation failed (No video file).")
            except Exception as e:
                add_timestamped_message(sleep_output, f"❌ Error: {e}")
            finally:
                btn_once.config(state="normal", text="Generate Once (No Loop)")

        threading.Thread(target=worker, daemon=True).start()

    btn_frame = tk.Frame(tab3)
    btn_frame.pack(pady=10)
    btn_once = tk.Button(btn_frame, text="Generate Once (No Loop)", command=generate_sleep_once, bg="#2196f3", fg="white", width=20)
    btn_once.pack(side="left", padx=10)
    tk.Button(btn_frame, text="▶ Start Auto Loop", command=start_sleep_loop, bg="green", fg="white", width=15).pack(side="left", padx=10)
    tk.Button(btn_frame, text="⏹ Stop Loop", command=stop_sleep_loop, bg="red", fg="white", width=15).pack(side="left", padx=10)

    # --- Karaoke Only Button ---
    def run_karaoke_only():
        out_file = "karaoke_output.mp4"
        karaoke_only_btn.config(state="disabled", text="Generating Karaoke...")
        
        def worker():
            try:
                meta = karaoke_generator.create_karaoke_video(out_file)
                msg = f"Karaoke saved to:\n{os.path.abspath(out_file)}\nTitle: {meta.get('title')}\n\n(Not posted to YouTube)"
                messagebox.showinfo("Success", msg)
            except Exception as e:
                messagebox.showerror("Error", f"Karaoke Generation failed:\n{e}")
            finally:
                karaoke_only_btn.config(state="normal", text="Generate Karaoke Only (No Post)")
        
        threading.Thread(target=worker, daemon=True).start()

    karaoke_only_btn = tk.Button(tab2, text="Generate Karaoke Only (No Post)", command=run_karaoke_only, bg="#e91e63", fg="white", font=("Arial", 12, "bold"))
    karaoke_only_btn.pack(pady=5)

    # --- Auto-Posting Scheduler Section ---
    ttk.Separator(tab2, orient='horizontal').pack(fill='x', pady=15)
    
    tk.Label(tab2, text="Auto-Posting Scheduler", font=("Arial", 14, "bold")).pack(pady=5)
    
    # Controls Frame
    sched_frame = tk.Frame(tab2)
    sched_frame.pack(pady=5)
    
    q_post_yt = tk.BooleanVar(value=True)
    q_post_ig = tk.BooleanVar(value=True)
    
    tk.Label(sched_frame, text="Shorts:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    tk.Checkbutton(sched_frame, text="Post to YouTube", variable=q_post_yt).pack(side="left", padx=5)
    tk.Checkbutton(sched_frame, text="Post to Instagram", variable=q_post_ig).pack(side="left", padx=5)
    
    # Frequency Slider
    freq_frame = tk.Frame(tab2)
    freq_frame.pack(pady=5)
    tk.Label(freq_frame, text="Shorts Frequency (Hours):").pack(side="left")
    freq_scale = tk.Scale(freq_frame, from_=0.5, to=24.0, resolution=0.5, orient="horizontal", length=200)
    freq_scale.set(1.0) # Default 1 hour
    freq_scale.pack(side="left", padx=10)

    # --- Daily Scheduling Mode ---
    tk.Label(tab2, text="Scheduling Mode:", font=("Arial", 10, "bold")).pack(pady=(10, 5))
    
    mode_frame = tk.Frame(tab2)
    mode_frame.pack()
    
    sched_mode_var = tk.StringVar(value="interval")
    
    tk.Radiobutton(mode_frame, text="Interval (Every X Hours)", variable=sched_mode_var, value="interval").pack(side="left", padx=10)
    tk.Radiobutton(mode_frame, text="Daily (Fixed Time)", variable=sched_mode_var, value="daily").pack(side="left", padx=10)
    
    daily_frame = tk.Frame(tab2)
    daily_frame.pack(pady=5)
    tk.Label(daily_frame, text="Daily Time (HH:MM, 24h):").pack(side="left")
    daily_time_var = tk.StringVar(value="16:00")
    tk.Entry(daily_frame, textvariable=daily_time_var, width=10).pack(side="left", padx=5)

    # --- Long Video Auto Controls ---
    long_sched_frame = tk.Frame(tab2)
    long_sched_frame.pack(pady=10)
    
    q_post_long_yt = tk.BooleanVar(value=False)
    karaoke_long_var = tk.BooleanVar(value=False)
    
    tk.Label(long_sched_frame, text="Long Video:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    tk.Checkbutton(long_sched_frame, text="Post to YouTube (Long)", variable=q_post_long_yt).pack(side="left", padx=10)
    tk.Checkbutton(long_sched_frame, text="Karaoke Long", variable=karaoke_long_var).pack(side="left", padx=10)
    
    # Long Freq Slider
    long_freq_frame = tk.Frame(tab2)
    long_freq_frame.pack(pady=5)
    tk.Label(long_freq_frame, text="Long Video Frequency (Hours):").pack(side="left")
    long_freq_scale = tk.Scale(long_freq_frame, from_=1.0, to=48.0, resolution=1.0, orient="horizontal", length=200)
    long_freq_scale.set(24.0) # Default 24 hours
    long_freq_scale.pack(side="left", padx=10)
    
    # Output Log for Quiz Tab
    q_output = tk.Text(tab2, height=10, width=80)
    q_output.pack(pady=10)
    
    def start_quiz_auto():
        q_output.delete("1.0", tk.END)
        
        # Shorts
        if q_post_yt.get() or q_post_ig.get():
            quiz_stop_flag.clear()
            # Pass new scheduling vars
            quiz_auto_loop(q_output, q_post_yt, q_post_ig, freq_scale, sched_mode_var, daily_time_var)
        else:
            add_timestamped_message(q_output, "ℹ️ Shorts Auto-Posting disabled (no platform selected).")

        # Long Video
        if q_post_long_yt.get():
            long_quiz_stop_flag.clear()
            long_quiz_auto_loop(q_output, q_post_long_yt, long_freq_scale, karaoke_long_var)
        else:
            add_timestamped_message(q_output, "ℹ️ Long Video Auto-Posting disabled (checkbox unchecked).")
        
    def stop_quiz_auto():
        quiz_stop_flag.set()
        long_quiz_stop_flag.set()
        add_timestamped_message(q_output, "🛑 Stopping ALL Auto-Posters (finishing current steps)...")

    btn_frame = tk.Frame(tab2)
    btn_frame.pack(pady=5)
    tk.Button(btn_frame, text="▶ Start Auto-Posting", command=start_quiz_auto, bg="green", fg="white", width=20).pack(side="left", padx=10)
    tk.Button(btn_frame, text="⏹ Stop Auto-Posting", command=stop_quiz_auto, bg="red", fg="white", width=20).pack(side="left", padx=10)

    # --- Tab 3: Documentary Generator ---
    tab3 = tk.Frame(notebook)
    notebook.add(tab3, text="Documentary Mode")

    tk.Label(tab3, text="Documentary Video Generator (v2: Ken Burns + EdgeTTS)", font=("Arial", 16, "bold")).pack(pady=10)
    
    # Config Frame
    config_frame = tk.Frame(tab3)
    config_frame.pack(pady=5, padx=10, fill="x")
    
    tk.Label(config_frame, text="Pexels API Key (Optional):").grid(row=0, column=0, sticky="w")
    pexels_key_var = tk.StringVar()
    tk.Entry(config_frame, textvariable=pexels_key_var, width=50, show="*").grid(row=0, column=1, padx=5)
    
    tk.Label(config_frame, text="OpenAI API Key (Optional):").grid(row=1, column=0, sticky="w")
    openai_key_var = tk.StringVar()
    tk.Entry(config_frame, textvariable=openai_key_var, width=50, show="*").grid(row=1, column=1, padx=5)

    # Ollama Controls
    tk.Label(config_frame, text="Use Ollama (Local AI):").grid(row=2, column=0, sticky="w")
    use_ollama_var = tk.BooleanVar(value=False)
    tk.Checkbutton(config_frame, variable=use_ollama_var, text="Enable").grid(row=2, column=1, sticky="w", padx=5)

    tk.Label(config_frame, text="Ollama Model:").grid(row=3, column=0, sticky="w")
    ollama_model_var = tk.StringVar(value="llama3")
    tk.Entry(config_frame, textvariable=ollama_model_var, width=20).grid(row=3, column=1, sticky="w", padx=5)

    # CLIP Controls
    use_clip_var = tk.BooleanVar(value=True)
    tk.Checkbutton(config_frame, variable=use_clip_var, text="Use CLIP (Smart Vision)").grid(row=2, column=2, sticky="w", padx=5)

    tk.Label(config_frame, text="* Leave keys empty for Free/Offline Mode (Mixkit Media + Text Parsing)", fg="gray", font=("Arial", 8)).grid(row=4, column=0, columnspan=2, sticky="w", padx=5)

    # Load config
    CONFIG_FILE = "config.json"
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                pexels_key_var.set(config.get("pexels_key", ""))
                openai_key_var.set(config.get("openai_key", ""))
        except:
            pass
            
    def save_config():
        config = {
            "pexels_key": pexels_key_var.get(),
            "openai_key": openai_key_var.get()
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
            
    tk.Button(config_frame, text="Save Keys", command=save_config).grid(row=0, column=2, rowspan=3, padx=5)
    
    tk.Label(tab3, text="Enter Topic OR Script (Paragraphs will be separate scenes):").pack(pady=5)
    
    doc_script_text = tk.Text(tab3, height=15, width=70)
    doc_script_text.pack(pady=5, padx=10)
    
    # Default script
    doc_script_text.insert("1.0", "How One Ad Destroyed Jaguar's Billion-Dollar Empire")
    
    def run_doc_gen():
        text_input = doc_script_text.get("1.0", tk.END).strip()
        if not text_input:
            messagebox.showwarning("Warning", "Please enter a topic or script.")
            return
            
        save_config() # Auto save
        
        doc_gen_btn.config(state="disabled", text="Generating...")
        
        def worker():
            try:
                import documentary_gen_v2
                
                openai_key = openai_key_var.get().strip() or None
                pexels_key = pexels_key_var.get().strip() or None
                
                out = documentary_gen_v2.generate_documentary_video(
                    text_input, 
                    "documentary_output.mp4",
                    pexels_api_key=pexels_key,
                    openai_api_key=openai_key,
                    use_ollama=use_ollama_var.get(),
                    ollama_model=ollama_model_var.get(),
                    use_clip=use_clip_var.get()
                )
                if out:
                    messagebox.showinfo("Success", f"Documentary saved to:\n{os.path.abspath(out)}")
                else:
                     messagebox.showerror("Error", "Generation failed (check logs).")
            except Exception as e:
                messagebox.showerror("Error", f"Documentary generation failed:\n{e}")
            finally:
                doc_gen_btn.config(state="normal", text="Generate Documentary")
                
        threading.Thread(target=worker, daemon=True).start()
        
    doc_gen_btn = tk.Button(tab3, text="Generate Documentary", command=run_doc_gen, bg="#5c6bc0", fg="white", font=("Arial", 12, "bold"))
    doc_gen_btn.pack(pady=20)

    # --- Tab 4: Popular Events ---
    tab4 = tk.Frame(notebook)
    notebook.add(tab4, text="Popular Events")
    
    tk.Label(tab4, text="Viral Event Commentary Generator", font=("Arial", 16, "bold")).pack(pady=10)
    
    tk.Label(tab4, text="Enter Event Topic (e.g. 'Met Gala Highlights', 'Super Bowl'):").pack(pady=5)
    
    topic_frame = tk.Frame(tab4)
    topic_frame.pack(pady=5)
    
    event_topic_var = tk.StringVar()
    tk.Entry(topic_frame, textvariable=event_topic_var, width=40).pack(side="left", padx=5)
    
    def auto_pick_topic():
        model = event_model_var.get().strip()
        try:
            import popular_events_mgr
            # Change button state
            auto_btn.config(state="disabled", text="Thinking...")
            root.update()
            
            # Run in thread or just quick call (Ollama might take 2-3s)
            def fetch():
                try:
                    topic = popular_events_mgr.generate_viral_topic(model=model)
                    root.after(0, lambda: event_topic_var.set(topic))
                except Exception as e:
                    print(e)
                finally:
                    root.after(0, lambda: auto_btn.config(state="normal", text="🎲 Auto-Pick"))
            
            threading.Thread(target=fetch, daemon=True).start()
            
        except ImportError:
            pass

    auto_btn = tk.Button(topic_frame, text="🎲 Auto-Pick", command=auto_pick_topic, bg="#9c27b0", fg="white")
    auto_btn.pack(side="left", padx=5)
    
    tk.Label(tab4, text="Ollama Model:").pack(pady=5)
    event_model_var = tk.StringVar(value="llama3")
    tk.Entry(tab4, textvariable=event_model_var, width=20).pack(pady=5)
    
    def run_event_gen():
        topic = event_topic_var.get().strip()
        if not topic:
            messagebox.showwarning("Warning", "Please enter a topic.")
            return
            
        model = event_model_var.get().strip()
        
        event_btn.config(state="disabled", text="Generating...")
        
        def worker():
            try:
                import popular_events_mgr
                # Sanitize filename
                safe_topic = "".join([c for c in topic if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
                out_file = f"event_{safe_topic}.mp4"
                
                out = popular_events_mgr.process_event_video(topic, output_file=out_file, model=model)
                
                if out and os.path.exists(out):
                    event_btn.after(0, lambda: messagebox.showinfo("Success", f"Video saved to:\n{os.path.abspath(out)}"))
                else:
                    event_btn.after(0, lambda: messagebox.showerror("Error", f"Failed: {out}"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                event_btn.after(0, lambda: messagebox.showerror("Error", f"Event generation failed:\n{e}"))
            finally:
                event_btn.after(0, lambda: event_btn.config(state="normal", text="Generate Commentary Video"))
        
        threading.Thread(target=worker, daemon=True).start()

    event_btn = tk.Button(tab4, text="Generate Commentary Video", command=run_event_gen, bg="#ff9800", fg="white", font=("Arial", 12, "bold"))
    event_btn.pack(pady=20)

    # --- Tab 5: Story Shorts ---
    tab5 = tk.Frame(notebook)
    notebook.add(tab5, text="Story Shorts")
    
    tk.Label(tab5, text="Perspective Story Generator", font=("Arial", 16, "bold")).pack(pady=10)
    tk.Label(tab5, text="Create shorts telling a story from a specific perspective.", fg="gray").pack(pady=5)
    
    tk.Label(tab5, text="Story Prompt (e.g. \"Tell the story of 'The Consultant' from Regus's perspective\"):").pack(pady=5)
    
    story_prompt_text = tk.Text(tab5, height=5, width=60)
    story_prompt_text.pack(pady=5, padx=10)
    story_prompt_text.insert("1.0", "Tell the story of 'The Consultant' from Regus's perspective")

    # Output Log for Story Tab
    story_output = tk.Text(tab5, height=12, width=80)
    story_output.pack(pady=10, padx=10)

    def run_story_gen():
        prompt = story_prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Warning", "Please enter a prompt.")
            return
            
        story_btn.config(state="disabled", text="Generating Story...")
        story_output.delete("1.0", tk.END)

        def status_update(msg):
            # Add timestamped message to GUI output log
            timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
            def _update():
                story_output.insert(tk.END, timestamp + str(msg) + "\n")
                story_output.see(tk.END)
            # Schedule update on main thread
            story_output.after(0, _update)
        
        def worker():
            try:
                import story_shorts_mgr
                # Sanitize filename from prompt (first 5 words)
                safe_name = "".join([c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
                out_file = f"story_{safe_name}.mp4"
                
                # Pass status_callback to create_story_video
                out = story_shorts_mgr.create_story_video(prompt, output_file=out_file, status_callback=status_update)
                
                if out and os.path.exists(out):
                    story_output.after(0, lambda: messagebox.showinfo("Success", f"Story Video saved to:\n{os.path.abspath(out)}"))
                    status_update(f"✅ Video saved to: {out}")
                else:
                    story_output.after(0, lambda: messagebox.showerror("Error", f"Failed to create story video."))
                    status_update("❌ Failed to create story video.")
            except Exception as e:
                import traceback
                traceback.print_exc()
                story_output.after(0, lambda: messagebox.showerror("Error", f"Story generation failed:\n{e}"))
                status_update(f"❌ Error: {e}")
            finally:
                story_output.after(0, lambda: story_btn.config(state="normal", text="Generate Story Short"))
        
        threading.Thread(target=worker, daemon=True).start()
        
    story_btn = tk.Button(tab5, text="Generate Story Short", command=run_story_gen, bg="#673ab7", fg="white", font=("Arial", 12, "bold"))
    story_btn.pack(pady=20)

    # --- Tab 6: Sleep Video Generator ---
    tab6 = tk.Frame(notebook)
    notebook.add(tab6, text="Sleep Video")

    tk.Label(tab6, text="Sleep & Relaxation Video", font=("Arial", 16, "bold")).pack(pady=10)
    tk.Label(tab6, text="Creates sleep videos with calm facts, nature visuals, and brown noise.", fg="gray").pack(pady=5)

    # Input Fields
    sleep_form = tk.Frame(tab6)
    sleep_form.pack(pady=10)

    tk.Label(sleep_form, text="Topic:").grid(row=0, column=0, sticky="e", padx=5)
    sleep_topic_var = tk.StringVar(value="Ancient Forests")
    tk.Entry(sleep_form, textvariable=sleep_topic_var, width=40).grid(row=0, column=1, padx=5)

    tk.Label(sleep_form, text="Num Facts:").grid(row=1, column=0, sticky="e", padx=5)
    sleep_facts_var = tk.IntVar(value=5)
    tk.Spinbox(sleep_form, from_=1, to=500, textvariable=sleep_facts_var, width=5).grid(row=1, column=1, sticky="w", padx=5)

    tk.Label(sleep_form, text="Duration:").grid(row=2, column=0, sticky="e", padx=5)
    tk.Label(sleep_form, text="Random (1h 50m - 2h 30m)", fg="gray").grid(row=2, column=1, sticky="w", padx=5)

    tk.Label(sleep_form, text="Custom Script (Optional):").grid(row=3, column=0, sticky="ne", padx=5, pady=5)
    sleep_script_text = tk.Text(sleep_form, height=8, width=40)
    sleep_script_text.grid(row=3, column=1, padx=5, pady=5)
    
    # Options
    sleep_opts = tk.Frame(tab6)
    sleep_opts.pack(pady=10)
    
    sleep_post_yt = tk.BooleanVar(value=False)
    tk.Checkbutton(sleep_opts, text="Post to YouTube", variable=sleep_post_yt).pack(side="left", padx=10)

    # Progress Bar
    sleep_progress = ttk.Progressbar(tab6, orient="horizontal", length=600, mode="determinate")
    sleep_progress.pack(pady=5)

    # Output Log
    sleep_output = tk.Text(tab6, height=12, width=80)
    sleep_output.pack(pady=10, padx=10)

    def run_sleep_gen():
        topic = sleep_topic_var.get().strip()
        num = sleep_facts_var.get()
        custom_script = sleep_script_text.get("1.0", tk.END).strip()
        
        if not topic and not custom_script:
            messagebox.showwarning("Warning", "Please enter a topic or a custom script.")
            return

        sleep_btn.config(state="disabled", text="Generating Sleep Video...")
        sleep_output.delete("1.0", tk.END)
        sleep_progress["value"] = 0

        def log(msg):
            timestamp = datetime.now().strftime("[%H:%M:%S] ")
            sleep_output.after(0, lambda: sleep_output.insert(tk.END, timestamp + str(msg) + "\n"))
            sleep_output.after(0, lambda: sleep_output.see(tk.END))

        def update_prog(val):
            sleep_output.after(0, lambda: sleep_progress.configure(value=val))

        def worker():
            try:
                import random
                from long_video_mgr import LongVideoManager

                log(f"🌙 Starting generation...")
                if custom_script:
                     log("📜 Using Custom Script (Duration will match audio length)")
                else:
                     log(f"📚 Using Topic: {topic}")

                mgr = LongVideoManager()
                
                # Sanitize filename
                safe_name = topic if topic else "custom_script"
                safe_topic = "".join([c for c in safe_name if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
                out_file = f"sleep_{safe_topic}.mp4"
                
                # Random duration between 1h 50m (6600s) and 2h 30m (9000s)
                # This is only used if custom_script is NOT provided
                min_dur = 6600 # 1h 50m
                max_dur = 9000 # 2h 30m
                random_duration = random.randint(min_dur, max_dur)
                
                log(f"🎲 Randomized Target Duration: {random_duration} seconds (~{random_duration//60} mins)")
                
                final_file = mgr.create_long_video(
                    topic=topic if topic else "Sleep Video", 
                    num_facts=num, 
                    output_file=out_file, 
                    outro_duration=random_duration,
                    custom_script=custom_script if custom_script else None,
                    progress_callback=update_prog
                )
                
                if final_file and os.path.exists(final_file):
                    log(f"✅ Video created: {final_file}")
                    
                    if sleep_post_yt.get():
                        log("📤 Uploading to YouTube...")
                        youtube = authenticate_youtube()
                        
                        # Generate simple metadata
                        display_topic = topic if topic else "Sleep Story"
                        title = f"Sleep Story: {display_topic} (Relaxing 4K Nature) - Deep Voice ASMR"
                        desc = f"Relax and fall asleep with this calming sleep story about {display_topic}.\n\nVisuals: 4K Nature\nAudio: Brown Noise + Deep Voice\n\n#sleep #asmr #relaxing #nature #sleepstory"
                        tags = ["sleep", "asmr", "relaxing", "nature", display_topic, "brown noise", "insomnia", "calm", "sleep story"]
                        
                        vid_id = upload_short_youtube(youtube, final_file, title, desc, tags)
                        log(f"✅ Uploaded: https://youtu.be/{vid_id}")
                    
                    sleep_output.after(0, lambda: messagebox.showinfo("Success", f"Video saved to:\n{os.path.abspath(final_file)}"))
                else:
                    log("❌ Generation failed.")
                    sleep_output.after(0, lambda: messagebox.showerror("Error", "Failed to create video."))
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                log(f"❌ Error: {e}")
                sleep_output.after(0, lambda: messagebox.showerror("Error", f"Error: {e}"))
            finally:
                sleep_output.after(0, lambda: sleep_btn.config(state="normal", text="Generate Sleep Video"))

        threading.Thread(target=worker, daemon=True).start()

    sleep_btn = tk.Button(tab6, text="Generate Sleep Video", command=run_sleep_gen, bg="#00796b", fg="white", font=("Arial", 12, "bold"))
    sleep_btn.pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
