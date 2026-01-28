import os
import random
import requests
from mutagen.mp3 import MP3
import edge_tts
import asyncio
import re
import string
import whisper  
import time
import praw

spoken_subreddits = {
    "AskReddit": "Ask Reddit",
    "TIFU": "T-I-F-U",
    "TrueOffMyChest": "True Off My Chest",
    "Confession": "Confession",
    "AmItheAsshole": "Am I the Asshole",
    "RelationshipAdvice": "Relationship Advice",
    "PettyRevenge": "Petty Revenge",
    "MaliciousCompliance": "Malicious Compliance",
    "LetsNotMeet": "Let's Not Meet",
    "BestofRedditorUpdates": "Best of Redditor Updates"
}

# Reddit credentials
reddit = praw.Reddit(
    client_id="5AnLlKToDNPFRqqaCkNYqA",
    client_secret="A31kc9ztkD-aIpxuDdr5GqbD0KUAZA",
    user_agent="script:yt-bot:v1.0 (by u/Maggrosu)",
    username="Maggrosu",
    password="Mircea123"
)

# NSFW filter
nsfw_words = {
    "fuck", "fucking", "fucked", "shit", "bullshit", "bitch", "asshole", "douche", "bastard",
    "damn", "crap", "dick", "cock", "pussy", "cunt", "twat", "slut", "whore",
    "sex", "sexy", "porn", "porno", "pornhub", "nudes", "nude", "naked", "stripper", "orgasm", 
    "cum", "cumming", "masturbate", "masturbation", "masturbating", "jerk", "jerking", "blowjob", 
    "handjob", "anal", "rimjob", "69", "doggy", "doggystyle", "missionary", "kamasutra", 
    "deepthroat", "suck", "sucking", "penetrate", "penetration", "fetish", "bdsm", "bondage",
    "boobs", "tits", "nipples", "dildo", "vibrator", "clit", "clitoris", "genitals", "penis", 
    "vagina", "testicles", "balls", "nut", "nutsack", "butt", "booty", "rear", "arse",
    "hoe", "thot", "skank", "cumslut", "fuckboy", "fuckgirl", "simp", "incel", "coomer", 
    "milf", "gilf", "sloot", "sugardaddy", "sugarbaby",
    "fuk", "fuq", "fck", "fml", "sh1t", "b1tch", "d1ck", "p0rn", "cumshot", "camgirl"
}

# 🔄 In-memory title storage
latest_title = None
def memorize_title(title):
    global latest_title
    latest_title = title.strip()
    print(f"title: {latest_title}")
    try:
        with open("latest_title.txt", "w", encoding="utf-8") as f:
            f.write(latest_title)
    except Exception as e:
        print(f"Warning: Could not save latest_title: {e}")

def get_memorized_title():
    global latest_title
    if latest_title:
        return latest_title
    if os.path.exists("latest_title.txt"):
        try:
            with open("latest_title.txt", "r", encoding="utf-8") as f:
                latest_title = f.read().strip()
                return latest_title
        except:
            pass
    return None

def censor_text(text):
    def censor_word(word):
        return word[0] + "*" * (len(word) - 1) if len(word) > 1 else "*"
    def replace(match):
        word = match.group()
        clean = word.lower().strip(string.punctuation)
        return censor_word(word) if clean in nsfw_words else word
    return re.sub(r"\b\w+\b", replace, text, flags=re.IGNORECASE)

def clean_text_for_tts(text):
    text = re.sub(r'\s+', ' ', text.strip())
    allowed_punct = ".!?,"
    text = ''.join(c for c in text if c.isalnum() or c.isspace() or c in allowed_punct)
    text = re.sub(r'([.!?,])(?=\w)', r'\1 ', text)
    text = re.sub(r'([.!?,])\1+', r'\1', text)
    return text

used_ids_file = "used_posts.txt"
subreddits = [
    "AskReddit", "TIFU", "TrueOffMyChest", "Confession", "AmItheAsshole",
    "RelationshipAdvice", "PettyRevenge", "MaliciousCompliance", "LetsNotMeet", "BestofRedditorUpdates", "Advice"
]

def load_used_ids():
    if not os.path.exists(used_ids_file):
        return set()
    with open(used_ids_file, "r") as f:
        return set(f.read().splitlines())

def save_post_id(post_id):
    with open(used_ids_file, "a") as f:
        f.write(post_id + "\n")

def get_unique_post():
    used_ids = load_used_ids()
    while True:
        subreddit_name = random.choice(subreddits)
        subreddit = reddit.subreddit(subreddit_name)

        try:
            print(f"🔍 Fetching top posts from r/{subreddit_name}")
            posts = list(subreddit.top(time_filter="year", limit=1000))
        except Exception as e:
            print(f"❌ Error accessing r/{subreddit_name} with PRAW:", e)
            time.sleep(2)
            continue

        posts = sorted(posts, key=lambda p: p.score, reverse=True)

        for post in posts:
            post_id = post.id
            body = post.selftext.strip()
            # Filter out unusable posts
            if (post_id in used_ids or 
                post.stickied or 
                not body or 
                body in ["[removed]", "[deleted]"] or 
                len(body) < 200): # Ensure enough content for a video
                continue

            save_post_id(post_id)
            title = censor_text(post.title.strip())
            memorize_title(title)

            spoken_name = spoken_subreddits.get(subreddit_name, subreddit_name)
            full_text = f"From subreddit {spoken_name}. {title}. {body}"
            return full_text

        print(f"⚠️ No suitable post found in r/{subreddit_name}, retrying...\n")

def get_audio_duration(filename):
    audio = MP3(filename)
    return audio.info.length

def get_ffmpeg_path() -> str:
    """Return local ffmpeg.exe if present, otherwise use ffmpeg from PATH."""
    local = os.path.join(os.getcwd(), "ffmpeg.exe")
    return os.path.abspath(local) if os.path.isfile(local) else "ffmpeg"


def post_process_audio(input_path: str) -> bool:
    """Apply gentle FFmpeg filters to smooth and calm the voice.

    Filters:
    - acompressor: light compression for smoother dynamics
    - equalizer: reduce sibilance around 6kHz
    - highpass: remove low-end rumble
    - loudnorm: slightly lower integrated loudness for a calmer feel
    """
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

        # Re-encode as MP3 at 160k for compatibility
        cmd = [
            ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error",
            "-y", "-i", input_path,
            "-af", filter_chain,
            "-c:a", "libmp3lame", "-b:a", "160k",
            output_path
        ]

        import subprocess
        subprocess.run(cmd, check=True)

        # Replace original with processed output
        try:
            os.replace(output_path, input_path)
        except Exception:
            # Fallback: copy then remove
            import shutil
            shutil.copyfile(output_path, input_path)
            os.remove(output_path)

        return True
    except Exception as e:
        print("⚠️ FFmpeg post-process failed:", e)
        return False


async def _generate_edge_tts(text, filename, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

def speak_and_save(text, filename="reddit_tts.mp3", voice="en-US-AriaNeural"):
    """Generate TTS using Edge TTS and apply calming post-processing.
    
    Default voice set to en-US-AriaNeural.
    """
    for attempt in range(3):
        try:
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
            
            asyncio.run(_generate_edge_tts(text, filename, voice))
            
            # 1. Check if file exists and has size
            if not os.path.exists(filename) or os.path.getsize(filename) < 100:
                print(f"⚠️ TTS attempt {attempt+1} failed: Invalid file size ({filename}).")
                time.sleep(1.5)
                continue
            
            # 3. Post-process
            if post_process_audio(filename):
                print(f"✅ Edge TTS audio saved to {filename}")
                return True
            else:
                print(f"⚠️ Post-processing failed for {filename}. Retrying...")
                time.sleep(1.5)
                continue

        except Exception as e:
            print(f"❌ Error during TTS generation (Attempt {attempt+1}): {e}")
            time.sleep(1.5)
            
    print(f"❌ All TTS attempts failed for text: {text[:20]}...")
    return False

def generate_ass_from_whisper(audio_file, output_file="captions.ass"):
    model = whisper.load_model("base")
    result = model.transcribe(audio_file)

    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds - int(seconds)) * 100)
        return f"{h}:{m:02}:{s:02}.{cs:02}"

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Centered,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,5,0,0,540,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header)
        for segment in result["segments"]:
            words = segment["text"].strip().split()
            start_time = segment["start"]
            end_time = segment["end"]
            segment_duration = end_time - start_time
            if len(words) == 0:
                continue
            time_per_word = segment_duration / len(words)
            i = 0
            while i < len(words):
                chunk_words = words[i:i+2]
                chunk_text = " ".join(chunk_words)
                chunk_start = start_time + i * time_per_word
                chunk_end = chunk_start + len(chunk_words) * time_per_word
                start = format_time(chunk_start)
                end = format_time(chunk_end)
                f.write(f"Dialogue: 0,{start},{end},Centered,,0,0,0,,{chunk_text}\n")
                i += 2
    print(f"✅ Whisper-based subtitles saved to {output_file}")

def generate_valid_reddit_audio():
    while True:
        post_text = get_unique_post()
        if not post_text:
            print("❌ Couldn’t fetch a post, retrying...")
            continue

        print("🧠 Reddit post:\n", post_text[:300], "...")
        censored_text = censor_text(post_text)
        cleaned_text = clean_text_for_tts(censored_text)

        parts = split_text_into_parts(cleaned_text, max_parts=3, target_chars=1000)
        result = []
        part_index = 1
        valid_durations = [False] * len(parts)

        for i, part in enumerate(parts):
            filename = f"reddit_tts_part{i+1}.mp3"
            if not speak_and_save(part, filename):
                print(f"❌ TTS generation failed for part {i+1}, retrying whole post...\n")
                break

            try:
                duration = get_audio_duration(filename)
                print(f"🎧 Part {i+1} duration: {duration:.2f}s")
            except Exception as e:
                print(f"⚠️ Audio file check failed (corrupt?): {e}. Retrying whole post...\n")
                break

            if not (30 <= duration <= 59 or 90 <= duration <= 119 or 150 <= duration <= 179):
                print(f"⚠️ Part {i+1} duration not in allowed range. Skipping this post...\n")
                break

            try:
                generate_ass_from_whisper(filename, f"captions_part{i+1}.ass")
            except Exception as e:
                 print(f"⚠️ Caption generation failed: {e}. Retrying whole post...\n")
                 break

            result.append((filename, part, part_index))
            part_index += 1
            valid_durations[i] = True

        if all(valid_durations):
            print("✅ All parts are valid.")
            return result
        else:
            print("🔁 Trying another post...")

def split_text_into_parts(text, max_parts=3, target_chars=1000):
    """
    Splits text into up to max_parts chunks, trying to get close to target_chars per chunk.
    """
    sentences = re.split(r'(?<=[.!?]) +', text)
    parts = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) <= target_chars or not current:
            current += sentence + " "
        else:
            parts.append(current.strip())
            current = sentence + " "
            if len(parts) == max_parts - 1:
                break

    remaining = " ".join(sentences[len(" ".join(parts).split()):])
    if current.strip():
        parts.append(current.strip())
    if len(parts) < max_parts and remaining.strip() and remaining.strip() not in parts:
        parts.append(remaining.strip())

    return parts[:max_parts]

if __name__ == "__main__":
    try:
        filename, post_text = generate_valid_reddit_audio()
        print(f"Generated audio file: {filename}")
        print(f"Post text: {post_text[:300]}...")
        print(f"📝 Memorized title: {get_memorized_title()}")
    except Exception as e:
        print("Fatal error:", e)
