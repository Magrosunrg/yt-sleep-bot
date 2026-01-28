import os
import random
import subprocess
import time
import shutil

# MoviePy imports with proper submodule paths
try:
    # Try MoviePy 2.x import style first
    from moviepy.editor import VideoFileClip, AudioFileClip
except ImportError:
    # Fallback to MoviePy 1.x import style
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        from moviepy.audio.io.AudioFileClip import AudioFileClip
    except ImportError:
        # Final fallback - try direct import
        try:
            from moviepy import VideoFileClip, AudioFileClip
        except ImportError:
            # If all imports fail, provide helpful error
            raise ImportError("Could not import VideoFileClip or AudioFileClip from moviepy. "
                           "Please check your MoviePy installation.")


def get_ffmpeg_path() -> str:
    """Return local ffmpeg.exe if present, otherwise use ffmpeg from PATH."""
    local = os.path.join(os.getcwd(), "ffmpeg.exe")
    return os.path.abspath(local) if os.path.isfile(local) else "ffmpeg"


def run_ffmpeg(args: list) -> None:
    """Run FFmpeg with hardened flags and raise on error."""
    ffmpeg = get_ffmpeg_path()
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error"] + args
    subprocess.run(cmd, check=True)


def ffprobe_duration(path: str) -> float:
    """Get media duration in seconds using ffprobe."""
    ffprobe = get_ffmpeg_path().replace("ffmpeg", "ffprobe")
    try:
        out = subprocess.check_output([
            ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path
        ])
        return float(out.decode().strip())
    except Exception:
        return 0.0


def escape_for_ffmpeg_filter(path: str) -> str:
    """Escape path for use in FFmpeg filter expressions (ass=)."""
    p = os.path.abspath(path).replace("\\", "/")
    p = p.replace(":", "\\:")  # escape drive colon, e.g., C\:/...
    p = p.replace("'", "\\'")
    return p


def find_existing_audio_parts(max_parts: int = 3):
    """Find existing reddit_tts_partN.mp3 files."""
    parts = []
    for i in range(1, max_parts + 1):
        f = f"reddit_tts_part{i}.mp3"
        if os.path.isfile(f):
            parts.append((f, None, i))  # (filename, text(None), index)
    return parts


def run_generation():
    seed_val = int(time.time())
    random.seed(seed_val)

    os.makedirs("generated_shorts", exist_ok=True)

    # Ensure MoviePy uses our local ffmpeg if present
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.isfile(local_ffmpeg):
        os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.abspath(local_ffmpeg)

    # Validate background video
    long_video_path = "assets/background.mp4"
    if not os.path.isfile(long_video_path):
        raise FileNotFoundError(f"Background video not found: {long_video_path}")

    # Validate FFmpeg availability
    ffmpeg_path = get_ffmpeg_path()
    if shutil.which(ffmpeg_path) is None and not os.path.isfile(local_ffmpeg):
        raise RuntimeError("ffmpeg not found. Place ffmpeg.exe in the project root or add ffmpeg to PATH.")

    # Prefer existing audio parts to avoid heavy dependency imports
    reddit_audio_parts = find_existing_audio_parts()
    if not reddit_audio_parts:
        # Try to generate if story_picker and its deps are available
        try:
            from story_picker import get_audio_duration as sp_get_audio_duration, generate_valid_reddit_audio
            reddit_audio_parts = generate_valid_reddit_audio()  # list of (filename, text, index)
            get_audio_duration = sp_get_audio_duration
        except Exception:
            raise RuntimeError("No audio parts available. Place reddit_tts_part*.mp3 in the project root or install generation deps.")
    else:
        # Use ffprobe for duration, fallback to MoviePy if ffprobe not available
        def get_audio_duration(path: str) -> float:
            d = ffprobe_duration(path)
            if d and d > 0:
                return d
            try:
                clip = AudioFileClip(path)
                duration = float(clip.duration or 0.0)
                clip.close()
                return duration
            except Exception:
                return 0.0

    # Load your long background video
    video = VideoFileClip(long_video_path)

    try:
        # Total TTS duration for all parts
        total_audio_duration = sum(get_audio_duration(part[0]) for part in reddit_audio_parts)
        if total_audio_duration <= 0:
            raise ValueError("Audio duration calculation failed. Ensure ffprobe is available or generation deps installed.")
        if total_audio_duration >= video.duration:
            raise ValueError("Total Reddit audio duration is longer than the background video!")

        # Pick a random segment of background video with enough length
        max_start = video.duration - total_audio_duration
        start_time = random.uniform(0, max_start)
        print(f"[INFO] Selected start offset: {start_time:.2f}s (max {max_start:.2f}s)")

        # Create a video for each part
        current_time = start_time
        made_files = []
        for filename, _, index in reddit_audio_parts:
            duration = get_audio_duration(filename)
            end_time = current_time + duration

            # MoviePy subclip
            subclip = video.subclipped(current_time, end_time)
            subclip_path = f"generated_shorts/temp_part_{index}.mp4"
            output_path = f"generated_shorts/short_part{index}.mp4"
            subtitle_path = f"captions_part{index}.ass"

            try:
                # Export video only (H.264, yuv420p for device compatibility)
                subclip.write_videofile(
                    subclip_path,
                    codec="libx264",
                    audio=False,
                    logger=None,
                    preset="medium",
                    threads=max(1, (os.cpu_count() or 2) // 2),
                    ffmpeg_params=["-pix_fmt", "yuv420p"]
                )
            finally:
                subclip.close()

            # Mux Reddit audio with video and apply gentle, calming audio filters
            # - acompressor: smooth dynamics
            # - equalizer: tame sibilance around 6kHz
            # - highpass: remove low-end rumble
            # - loudnorm: slightly lower integrated loudness for a calmer feel
            audio_filters = (
                "acompressor=ratio=2:threshold=-18dB:attack=10:release=250:makeup=1.5,"
                "equalizer=f=6000:t=h:w=250:g=-4,"
                "highpass=f=60,"
                "loudnorm=I=-20:LRA=7:TP=-2.0"
            )

            run_ffmpeg([
                "-i", subclip_path,
                "-i", filename,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "160k",
                "-af", audio_filters,
                "-movflags", "+faststart",
                "-shortest", output_path
            ])

            # Burn subtitles if they exist
            if os.path.exists(subtitle_path):
                final_with_subs = f"generated_shorts/short_part{index}_with_subs.mp4"
                subtitle_arg_path = escape_for_ffmpeg_filter(subtitle_path)
                run_ffmpeg([
                    "-i", output_path,
                    "-vf", f"ass='{subtitle_arg_path}'",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    final_with_subs
                ])
                os.replace(final_with_subs, output_path)

            # Clean temp
            if os.path.exists(subclip_path):
                try:
                    os.remove(subclip_path)
                except OSError:
                    pass

            made_files.append(output_path)
            current_time += duration

        print("[INFO] Generated files:")
        for f in made_files:
            print(" -", f)

    finally:
        video.close()


if __name__ == "__main__":
    print("🎬 Running short generation...")
    run_generation()
    print("✅ Done!")
