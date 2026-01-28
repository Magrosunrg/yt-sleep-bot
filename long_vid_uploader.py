#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Smart YouTube Editor (PyQt5) - Pro edition (replaces "normal mode")
Major upgrades:
 - Pro pipeline (hook, story, climax, CTA)
 - semantic + visual deduplication (avoid repeats)
 - animated hook title and lower-thirds (drawtext)
 - broadcast audio chain (denoise, de-ess, compand, loudnorm)
 - adaptive transitions + music ducking + logo watermark + CTA card
 - robust fallbacks if optional libs (Pillow, imagehash) or tools (whisper) not available
"""
import sys
import os
import re
import json
import shutil
import uuid
import subprocess
import time
import shlex
import tempfile
import hashlib
from typing import List, Tuple, Dict, Optional, Callable
from difflib import SequenceMatcher
import story_picker

# --- Constants for optimization ---
TEXT_SIMILARITY_THRESHOLD = 0.72
KEYWORD_BOOST_SCORE = 0.8
KEYWORD_MATCH_MAX_COUNT = 3
SCENE_BOOST_MAX_SCORE = 5.0

# --- AI Content Analysis Constants ---
AUDIO_QUALITY_WEIGHT = 0.15
VISUAL_APPEAL_WEIGHT = 0.20
SPEECH_CONTENT_WEIGHT = 0.25
ENGAGEMENT_WEIGHT = 0.25
TECHNICAL_QUALITY_WEIGHT = 0.15

# Engagement keywords that boost content scores
ENGAGEMENT_KEYWORDS = [
    "amazing", "incredible", "unbelievable", "shocking", "mind-blowing",
    "you won't believe", "must see", "game changer", "life changing",
    "secret", "hidden", "exclusive", "first time", "never seen before",
    "tutorial", "how to", "step by step", "beginner", "advanced",
    "tips", "tricks", "hacks", "secrets", "pro tips",
    "subscribe", "like", "share", "comment", "follow",
    "important", "critical", "urgent", "breaking", "latest"
]

# Visual appeal indicators
VISUAL_APPEAL_INDICATORS = [
    "bright", "colorful", "vibrant", "stunning", "beautiful",
    "action", "movement", "dynamic", "fast-paced", "intense"
]
# ----------------------------------

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QProgressBar, QTextEdit, QCheckBox, QComboBox, QSpinBox,
    QGroupBox, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor

# Import Quiz GUI
try:
    from quiz_gui import QuizGeneratorWidget
except ImportError:
    QuizGeneratorWidget = None


# Optional imports for image hashing
try:
    from PIL import Image
    import imagehash
except Exception:
    Image = None
    imagehash = None

# Optional moviepy pieces if available
try:
    from moviepy.editor import ColorClip, CompositeVideoClip
except Exception:
    ColorClip = None
    CompositeVideoClip = None

# =========================
# Utilities
# =========================

def run(cmd: List[str], timeout: int = 7200, check: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess, capture stdout/stderr. Expects list command."""
    try:
        # cmd is expected to be a list already, no shlex.split here
        parts = cmd  # Already a list from calling sites
        # Prefer local ffmpeg/ffprobe binaries if present
        if parts:
            root = os.path.dirname(os.path.abspath(__file__))
            local_ffmpeg = os.path.join(root, "ffmpeg.exe")
            local_ffprobe = os.path.join(root, "ffprobe.exe")
            if parts[0] == "ffmpeg" and os.path.exists(local_ffmpeg):
                parts[0] = local_ffmpeg
            elif parts[0] == "ffprobe" and os.path.exists(local_ffprobe):
                parts[0] = local_ffprobe
        # Auto-inject -loglevel error for ffmpeg/ffprobe calls when not provided
        if parts and (os.path.basename(parts[0]).lower().startswith("ffmpeg") or os.path.basename(parts[0]).lower().startswith("ffprobe")) and "-loglevel" not in parts:
            parts = [parts[0], "-loglevel", "error"] + parts[1:]
        print(f"[DEBUG] run: Executing: {' '.join(parts)}")
        result = subprocess.run(
            parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=check,  # Use the new check parameter
        )
        if result.stderr:
            truncated = (result.stderr[:1000] + '...') if len(result.stderr) > 1000 else result.stderr
            print(f"[DEBUG] run: STDERR: {truncated}")
        return result
    except subprocess.TimeoutExpired as e:
        print(f"[ERROR] run: Command timed out: {' '.join(cmd)} - {e}")
        raise # Re-raise to be handled by caller
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] run: Command failed with exit code {e.returncode}: {' '.join(e.cmd)} - {e.stderr}")
        raise # Re-raise to be handled by caller
    except Exception as e:
        print(f"[DEBUG] run: Exception: {e}")
        cp = subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr=str(e))
        return cp

def have_ffmpeg() -> bool:
    root = os.path.dirname(os.path.abspath(__file__))
    local_ffmpeg = os.path.join(root, "ffmpeg.exe")
    local_ffprobe = os.path.join(root, "ffprobe.exe")
    ffmpeg_ok = shutil.which("ffmpeg") is not None or os.path.exists(local_ffmpeg)
    ffprobe_ok = shutil.which("ffprobe") is not None or os.path.exists(local_ffprobe)
    return ffmpeg_ok and ffprobe_ok

def ffprobe_duration(path: str) -> float:
    if not os.path.exists(path):
        return 0.0
    p = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ], check=True)
    try:
        duration = float((p.stdout or "").strip())
        return duration
    except Exception:
        return 0.0

def ffprobe_dimensions(path: str) -> Tuple[int, int]:
    if not os.path.exists(path):
        return 0, 0
    p = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", path
    ], check=True)
    try:
        dimensions = (p.stdout or "").strip().split('x')
        if len(dimensions) != 2:
            return 0, 0
        return int(dimensions[0]), int(dimensions[1])
    except Exception:
        return 0, 0

def has_audio_stream(path: str) -> bool:
    if not os.path.exists(path):
        return False
    p = run([
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        path
    ], check=True)
    return bool((p.stdout or "").strip())

def path_for_filter(p: str) -> str:
    return os.path.abspath(p).replace("\\", "/")

def audio_props(path: str):
    if not os.path.exists(path):
        return None
    p = run([
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ], check=True)
    vals = (p.stdout or "").splitlines()
    if len(vals) >= 3:
        return vals[0].strip(), vals[1].strip(), vals[2].strip()
    return None

# =========================
# FFmpeg helper primitives (from original)
# =========================

def run_ffmpeg(cmd: str, output: str) -> bool:
    print(f"[DEBUG] Running ffmpeg: {cmd}")
    try:
        proc = run(shlex.split(cmd), check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ffmpeg failed for {output}\n{e.stderr}")
        return False
    if not os.path.exists(output) or os.path.getsize(output) == 0:
        print(f"[ERROR] Output missing or empty: {output}\n{proc.stderr}")
        return False
    return True

def trim_out(input_path: str, start: float, end: float, output_path: str, vf_extra: Optional[str] = None) -> bool:
    dur = max(0.0, end - start)
    # Reduced minimum duration from 0.05 to 0.01 to preserve more content
    if dur <= 0.01:
        return False
    vf_base = "format=yuv420p,setsar=1,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    vf_final = f"{vf_base},{vf_extra}" if vf_extra else vf_base
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", input_path,
        "-r", "60",
        "-vf", vf_final,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-af", "aresample=async=1000",
        "-movflags", "+faststart",
        "-y", output_path
    ]
    run(cmd, check=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def concat_hard_cut(a_path: str, b_path: str, out_path: str) -> bool:
    try:
        # Check if input files exist and have audio streams
        if not (os.path.exists(a_path) and os.path.exists(b_path)):
            print(f"[ERROR] Input file missing: {a_path if not os.path.exists(a_path) else b_path}")
            return False
            
        # Run the FFmpeg command with proper error handling
        run([
            "ffmpeg", "-hide_banner", "-nostats", "-i", a_path, "-i", b_path,
            "-filter_complex", "[0:v]format=yuv420p[v0];[1:v]format=yuv420p[v1];[v0][v1]concat=n=2:v=1[outv];[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo[a0];[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo[a1];[a0][a1]concat=n=2:v=0:a=1[outa]",
            "-map", "[outv]", "-map", "[outa]",
            "-r", "60",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-af", "aresample=async=1000", "-movflags", "+faststart", "-y", out_path
        ], check=True)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        print(f"[ERROR] concat_hard_cut failed: {e}")
        return False


def combine_videos_in_order(input_paths: List[str], output_path: str, log_func=None) -> bool:
    """
    Combine multiple videos in order into a single file.
    Mechanism: preflight checks, attempt fast concat demuxer, fallback to filter_complex concat with scaling.
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)

    if not input_paths:
        log("[COMBINE] Error: No input paths provided")
        return False

    # Check if all input files exist and non-empty
    for i, path in enumerate(input_paths):
        if not os.path.exists(path):
            log(f"[COMBINE] Error: Input file {i+1} does not exist: {path}")
            return False
        if os.path.getsize(path) == 0:
            log(f"[COMBINE] Error: Input file {i+1} is empty: {path}")
            return False

    # Preflight: ffmpeg version & minimal free disk space
    try:
        v = run(["ffmpeg", "-version"], check=False)
        first = (v.stdout or "").splitlines()[0] if v.stdout else ""
        if first:
            log(f"[FFMPEG] {first}")
    except Exception:
        pass
    out_dir = os.path.dirname(output_path) or "."
    try:
        usage = shutil.disk_usage(out_dir)
        free_mb = usage.free / (1024 * 1024)
        log(f"[COMBINE] Free disk space: {free_mb:.0f} MB in {out_dir}")
        if free_mb < 512:
            log("[COMBINE] Error: Not enough free disk space in output directory")
            return False
    except Exception:
        pass

    log(f"[COMBINE] Processing {len(input_paths)} files")
    for i, path in enumerate(input_paths):
        log(f"[COMBINE]   Input {i+1}: {os.path.basename(path)}")

    if len(input_paths) == 1:
        try:
            log(f"[COMBINE] Copying single file to {os.path.basename(output_path)}")
            shutil.copy2(input_paths[0], output_path)
            log("[COMBINE] Successfully copied single file")
            return True
        except Exception as e:
            log(f"[COMBINE] Single file copy error: {e}")
            return False

    try:
        # Detect audio presence and target dimensions from first input
        has_audio = all(has_audio_stream(path) for path in input_paths)
        first_width, first_height = ffprobe_dimensions(input_paths[0])
        if first_width <= 0 or first_height <= 0:
            log("[COMBINE] Warning: Could not detect dimensions from first video, using defaults")
            first_width, first_height = 1920, 1080
        log(f"[COMBINE] Using target dimensions: {first_width}x{first_height} (preserving original aspect ratio)")

        # Fast path: concat demuxer (stream copy) if inputs are compatible
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="lvu_concat_")
        demux_succeeded = False
        try:
            list_file = os.path.join(tmp_dir, "list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for p in input_paths:
                    f.write(f"file '{path_for_filter(p)}'\n")
            log("[COMBINE] Attempting fast concat demuxer (stream copy)...")
            res = run([
                "ffmpeg", "-hide_banner", "-nostats",
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                "-movflags", "+faststart", "-y",
                output_path
            ], check=True)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                log(f"[COMBINE] Concat demuxer succeeded (size={os.path.getsize(output_path)} bytes)")
                demux_succeeded = True
            else:
                log("[COMBINE] Demuxer output not created or empty, falling back")
        except Exception as e:
            log(f"[COMBINE] Demuxer concat failed: {e}. Falling back to filter-based concat")
        finally:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
        if demux_succeeded:
            return True

        # Fallback: filter_complex concat with scaling/padding
        cmd = ["ffmpeg", "-hide_banner", "-nostats"]
        for path in input_paths:
            cmd.extend(["-i", path])

        if has_audio:
            scale_parts = []
            concat_parts = []
            for i in range(len(input_paths)):
                scale_parts.append(f"[{i}:v]scale={first_width}:{first_height}:force_original_aspect_ratio=decrease,pad={first_width}:{first_height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
                concat_parts.append(f"[v{i}][{i}:a]")
            filter_complex = f"{';'.join(scale_parts)};{''.join(concat_parts)}concat=n={len(input_paths)}:v=1:a=1[outv][outa]"
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-q:a", "2",
                "-movflags", "+faststart", "-y", output_path
            ])
        else:
            scale_parts = []
            concat_parts = []
            for i in range(len(input_paths)):
                scale_parts.append(f"[{i}:v]scale={first_width}:{first_height}:force_original_aspect_ratio=decrease,pad={first_width}:{first_height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
                concat_parts.append(f"[v{i}]")
            filter_complex = f"{';'.join(scale_parts)};{''.join(concat_parts)}concat=n={len(input_paths)}:v=1:a=0[outv]"
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-movflags", "+faststart", "-y", output_path
            ])

        log(f"[COMBINE] Audio streams detected: {has_audio}")
        log(f"[COMBINE] Running FFmpeg to combine {len(input_paths)} videos (fallback mode)...")
        result = run(cmd, check=True)
        log(f"[COMBINE] FFmpeg completed with return code: {result.returncode}")

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log(f"[COMBINE] Successfully created output file: {os.path.basename(output_path)} ({os.path.getsize(output_path)} bytes)")
            return True
        else:
            log("[COMBINE] Error: Output file not created or is empty")
            return False
    except subprocess.CalledProcessError as e:
        log(f"[COMBINE] FFmpeg error: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            log(f"[COMBINE] FFmpeg stderr: {e.stderr}")
        return False
    except Exception as e:
        log(f"[COMBINE] Error: {e}")
        return False


def crossfade_two_clips(a_path: str, b_path: str, out_path: str, duration: float = 0.8, transition: str = "fade") -> bool:
    """Enhanced crossfade with better quality and smoother transitions"""
    try:
        da = ffprobe_duration(a_path)
        db = ffprobe_duration(b_path)
        if da <= 0 or db <= 0:
            return False
            
        # Optimize transition duration for better visual effect
        duration = min(duration, min(da, db) * 0.2)  # Max 20% of shorter clip for smoother transition
        offset = max(0.0, da - duration)
        
        # Enhanced filter complex with better scaling and color handling
        fc = (
            f"[0:v]format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[v0];"
            f"[1:v]format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[v1];"
            f"[v0][v1]xfade=transition={transition}:duration={duration}:offset={offset}[v];"
            f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
            f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
            f"[a0][a1]acrossfade=d={duration}:curve1=tri:curve2=tri[a]"
        )
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", a_path, "-i", b_path,
            "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-r", "60",  # Higher framerate for smoother transitions
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",  # Better quality
            "-c:a", "aac", "-b:a", "320k", "-ar", "48000",  # Higher audio quality
            "-movflags", "+faststart", "-y", out_path
        ]
        
        run(cmd, check=False, timeout=300)  # 5 minute timeout
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return True
            
        # Fallback: simple concat for speed
        return concat_hard_cut(a_path, b_path, out_path)
    except Exception:
        # Final fallback: direct copy of first clip
        try:
            shutil.copy(a_path, out_path)
            return True
        except Exception:
            return False

def loudness_normalize(input_path: str, output_path: str, i_lufs: float = -14.0, lra: float = 11.0, tp: float = -1.5) -> bool:
    try:
        m = run([
            "ffmpeg", "-hide_banner", "-nostats", "-i", input_path,
            "-af", f"loudnorm=I={i_lufs}:LRA={lra}:TP={tp}:print_format=json",
            "-f", "null", "-"], timeout=600, check=True)
    except subprocess.CalledProcessError:
        # If analysis fails, just copy the file and return
        try:
            shutil.copy(input_path, output_path)
            return True
        except Exception:
            return False
    j = re.search(r"\{[\s\S]*\}", m.stderr or "")
    if not j:
        try:
            shutil.copy(input_path, output_path)
            return True
        except Exception:
            return False
    try:
        stats = json.loads(j.group(0))
    except Exception:
        try:
            shutil.copy(input_path, output_path)
            return True
        except Exception:
            return False
    af = (
        f"loudnorm=I={i_lufs}:LRA={lra}:TP={tp}"
        f":measured_I={stats.get('input_i')}:measured_LRA={stats.get('input_lra')}"
        f":measured_TP={stats.get('input_tp')}:measured_thresh={stats.get('input_thresh')}"
        f":offset={stats.get('target_offset')}:linear=true"
    )
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", input_path, "-af", af, "-c:v", "copy", "-movflags", "+faststart", "-y", output_path], timeout=600, check=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def burn_in_subtitles(input_path: str, srt_path: str, output_path: str) -> bool:
    if not (os.path.exists(input_path) and os.path.exists(srt_path)):
        return False
    srt_norm = path_for_filter(srt_path)
    vf = f"subtitles={srt_norm}:force_style='Fontsize=24,Outline=1,Shadow=1'"
    run(["ffmpeg", "-hide_banner", "-nostats", "-i", input_path, "-vf", vf, "-c:a", "copy", "-movflags", "+faststart", "-y", output_path], check=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


def add_music_ducked(video_path: str, music_path: str, output_path: str, music_gain_db: float = -18.0) -> bool:
    if not (os.path.exists(video_path) and os.path.exists(music_path)):
        return False
    if not has_audio_stream(video_path):
        tmp = output_path + ".tmp_silent.mp4"
        video_dur = ffprobe_duration(video_path)
        run([
            "ffmpeg", "-hide_banner", "-nostats", "-i", video_path,
            "-f", "lavfi", "-t", str(video_dur), "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-c:v", "copy", "-shortest", "-y", tmp
        ], check=True)
        video_path = tmp

    music_vol = 10 ** (music_gain_db / 20.0)
    fc = (
        f"[1:a]volume={music_vol}[bgm];"
        f"[0:a][bgm]sidechaincompress=threshold=0.03:ratio=8:attack=200:release=800[aout]"
    )
    run([
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", video_path, "-i", music_path,
        "-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-y", output_path
    ], check=False)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        if video_path.endswith(".tmp_silent.mp4") and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass
        return True
    # fallback
    run([
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", video_path, "-i", music_path,
        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest[aout]",
        "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-y", output_path
    ], check=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def export_aspect(input_path, output_path, aspect="16:9", width=1920):
    transforms_file = os.path.join(os.path.dirname(output_path), "transforms.trf").replace("\\", "/")
    detect_cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale=640:-1,format=yuv420p,vidstabdetect=shakiness=5:accuracy=15:result={transforms_file}",
        "-an", "-f", "null", "-"
    ]
    run(detect_cmd, check=False)
    vf = f"scale={width}:-2:force_original_aspect_ratio=decrease," \
         f"pad={width}:ih:(ow-iw)/2:(oh-ih)/2,setsar=1"
    if os.path.exists(transforms_file):
        vf += f",vidstabtransform=input={transforms_file}:smoothing=30,unsharp=5:5:0.8:3:3:0.4"
    af = "loudnorm=I=-14:TP=-1.5:LRA=11," \
         "highpass=f=60,lowpass=f=18000," \
         "acompressor=threshold=-30dB:ratio=2:attack=10:release=100"
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-i", input_path,
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-q:a", "2", "-ar", "48000", "-ac", "2",
        output_path
    ]
    proc = run(cmd, check=True)
    return proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0

# =========================
# Ken Burns, watermark, audio enhance (keep existing helpers)
# =========================

def apply_ken_burns(input_path: str, output_path: str, mode: str = "in", max_zoom: float = 1.08) -> bool:
    if not os.path.exists(input_path):
        return False
        
    # Get video dimensions for better scaling
    width, height = ffprobe_dimensions(input_path)
    if width <= 0 or height <= 0:
        return False
        
    # Ensure dimensions are even for better encoding
    width = width - (width % 2)
    height = height - (height % 2)
    
    # Improved zoom parameters for smoother effect
    if mode == "in":
        z_expr = f"min(zoom+0.0005,{max_zoom:.3f})"
    else:
        z_expr = f"max(zoom-0.0005,1.0)"
        
    # Get video duration to ensure zoompan generates frames for the entire clip
    duration = ffprobe_duration(input_path)
    if duration <= 0:
        return False
        
    # Enhanced zoompan with better scaling and positioning
    fc = f"[0:v]scale={width}:{height},setsar=1,zoompan=z='{z_expr}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={int(duration*60)}:fps=60,format=yuv420p[v]"
    
    args = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", input_path,
        "-filter_complex", fc, "-map", "[v]"
    ]
    
    if has_audio_stream(input_path):
        # Improve audio quality instead of just copying
        args += ["-map", "0:a", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
    
    args += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
        "-movflags", "+faststart", "-y", output_path
    ]
    run(args, check=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def get_overlay_logo_filter(logo_path: str, position: str = "tr", margin: int = 24, rel_width: float = 0.12, opacity: float = 0.9) -> Optional[str]:
    if not os.path.exists(logo_path):
        return None
    pos_map = {
        "tl": ("{margin}", "{margin}"),
        "tr": ("W-w-{margin}", "{margin}"),
        "bl": ("{margin}", "H-h-{margin}"),
        "br": ("W-w-{margin}", "H-h-{margin}")
    }
    px, py = pos_map.get(position, pos_map["tr"])
    px = px.format(margin=margin)
    py = py.format(margin=margin)
    fc = (
        f"[1][0:v]scale2ref=w=iw*{rel_width}:h=ow/mdar[lg][base];"
        f"[lg]format=rgba,colorchannelmixer=aa={opacity}[loga];"
        f"[base][loga]overlay={px}:{py}[v]"
    )
    return fc

def overlay_logo(video_path: str, logo_path: str, out_path: str, position: str = "tr", margin: int = 24, rel_width: float = 0.12, opacity: float = 0.9) -> bool:
    if not (os.path.exists(video_path) and os.path.exists(logo_path)):
        return False
    pos_map = {
        "tl": ("{margin}", "{margin}"),
        "tr": ("W-w-{margin}", "{margin}"),
        "bl": ("{margin}", "H-h-{margin}"),
        "br": ("W-w-{margin}", "H-h-{margin}")
    }
    px, py = pos_map.get(position, pos_map["tr"])
    px = px.format(margin=margin)
    py = py.format(margin=margin)
    fc = (
        f"[1][0:v]scale2ref=w=iw*{rel_width}:h=ow/mdar[lg][base];"
        f"[lg]format=rgba,colorchannelmixer=aa={opacity}[loga];"
        f"[base][loga]overlay={px}:{py}[v]"
    )
    args = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", video_path, "-i", logo_path,
        "-filter_complex", fc, "-map", "[v]"
    ]
    if has_audio_stream(video_path):
        args += ["-map", "0:a", "-c:a", "copy"]
    args += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "23",
        "-movflags", "+faststart", "-y", out_path
    ]
    run(args, check=True)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0

def analyze_audio_characteristics(video_path: str) -> Dict:
    """Analyze audio characteristics to determine optimal processing parameters."""
    try:
        # Get audio stats
        cmd = [
            "ffprobe", "-v", "quiet", "-show_entries", "stream=bit_rate,sample_rate,channels",
            "-select_streams", "a:0", "-of", "csv=p=0", video_path
        ]
        result = run(cmd, check=True)
        audio_info = result.stdout.decode().strip().split(',')
        
        # Get volume stats
        vol_cmd = [
            "ffmpeg", "-i", video_path, "-af", "volumedetect", "-f", "null", "-"
        ]
        vol_result = run(vol_cmd, check=False)
        vol_output = vol_result.stderr.decode()
        
        # Parse volume information
        mean_volume = -20.0  # default
        max_volume = -10.0   # default
        
        for line in vol_output.split('\n'):
            if 'mean_volume:' in line:
                try:
                    mean_volume = float(line.split('mean_volume:')[1].split('dB')[0].strip())
                except:
                    pass
            elif 'max_volume:' in line:
                try:
                    max_volume = float(line.split('max_volume:')[1].split('dB')[0].strip())
                except:
                    pass
        
        return {
            'sample_rate': int(audio_info[1]) if len(audio_info) > 1 else 44100,
            'channels': int(audio_info[2]) if len(audio_info) > 2 else 2,
            'mean_volume': mean_volume,
            'max_volume': max_volume,
            'dynamic_range': max_volume - mean_volume,
            'needs_noise_reduction': mean_volume < -25.0,
            'needs_compression': (max_volume - mean_volume) > 20.0
        }
    except Exception as e:
        return {
            'sample_rate': 44100,
            'channels': 2,
            'mean_volume': -20.0,
            'max_volume': -10.0,
            'dynamic_range': 10.0,
            'needs_noise_reduction': True,
            'needs_compression': False
        }

def enhance_dialogue_audio(input_path: str, output_path: str) -> bool:
    if not os.path.exists(input_path):
        return False
    
    # Analyze audio characteristics for adaptive processing
    audio_chars = analyze_audio_characteristics(input_path)
    
    # Build adaptive audio filter chain
    filters = []
    
    # Adaptive noise reduction based on volume analysis
    if audio_chars['needs_noise_reduction']:
        nr_strength = min(20, max(8, int(abs(audio_chars['mean_volume']) - 15)))
        filters.append(f"afftdn=nr={nr_strength}:nt=w")
    
    # Frequency filtering - more aggressive for noisy audio
    if audio_chars['mean_volume'] < -30:
        filters.extend([
            "highpass=f=120",  # More aggressive high-pass
            "lowpass=f=12000"  # More conservative low-pass
        ])
    else:
        filters.extend([
            "highpass=f=80",   # Gentle high-pass
            "lowpass=f=15000"  # Standard low-pass
        ])
    
    # Adaptive EQ based on audio characteristics
    if audio_chars['dynamic_range'] > 15:
        # Wide dynamic range - gentle EQ
        filters.extend([
            "equalizer=f=250:t=h:width=150:g=-1.5",   # Reduce mud
            "equalizer=f=3000:t=h:width=600:g=1.5",   # Enhance presence
            "equalizer=f=8000:t=h:width=1000:g=0.8"   # Add air
        ])
    else:
        # Compressed audio - more aggressive EQ
        filters.extend([
            "equalizer=f=300:t=h:width=200:g=-2.5",   # Cut mud
            "equalizer=f=3500:t=h:width=800:g=2.5",   # Boost presence
            "equalizer=f=10000:t=h:width=2000:g=1.2"  # Add brightness
        ])
    
    # Dynamic range processing
    if audio_chars['needs_compression']:
        # Gentle compression for overly dynamic audio
        filters.append("acompressor=threshold=-18dB:ratio=3:attack=5:release=50")
    
    # Adaptive gain adjustment
    target_level = -16.0  # Target RMS level
    gain_adjustment = target_level - audio_chars['mean_volume']
    if abs(gain_adjustment) > 2.0:  # Only apply if significant difference
        gain_adjustment = max(-12, min(12, gain_adjustment))  # Limit gain
        filters.append(f"volume={gain_adjustment}dB")
    
    # Final limiter to prevent clipping
    filters.append("alimiter=level_in=1:level_out=0.95:limit=0.95")
    
    af = ",".join(filters)
    
    # Enhanced encoding settings
    args = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", input_path,
        "-c:v", "copy", 
        "-af", af,
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",  # High quality audio
        "-movflags", "+faststart", "-y", output_path
    ]
    
    try:
        run(args, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        # Fallback to simple processing if adaptive fails
        simple_af = (
            "afftdn=nr=12:nt=w,"
            "highpass=f=100,lowpass=f=15000,"
            "equalizer=f=300:t=h:width=200:g=-2,"
            "equalizer=f=3500:t=h:width=800:g=2"
        )
        fallback_args = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", input_path,
            "-c:v", "copy", "-af", simple_af, "-movflags", "+faststart", "-y", output_path
        ]
        run(fallback_args, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0


def advanced_audio_cleanup(input_path: str, output_path: str, 
                          noise_reduction_strength: str = "medium",
                          enable_echo_cancellation: bool = True,
                          enable_hum_removal: bool = True,
                          enable_click_removal: bool = True) -> bool:
    """Advanced audio cleanup with multiple enhancement options.
    
    Args:
        input_path: Input video file path
        output_path: Output video file path
        noise_reduction_strength: "light", "medium", "heavy"
        enable_echo_cancellation: Remove echo and reverb
        enable_hum_removal: Remove electrical hum (50/60Hz)
        enable_click_removal: Remove clicks and pops
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(input_path):
            return False
        
        # Analyze audio characteristics
        audio_chars = analyze_audio_characteristics(input_path)
        
        # Build comprehensive filter chain
        filters = []
        
        # Noise reduction with configurable strength
        nr_settings = {
            "light": {"nr": 8, "nt": "w"},
            "medium": {"nr": 12, "nt": "w"},
            "heavy": {"nr": 18, "nt": "w"}
        }
        nr_config = nr_settings.get(noise_reduction_strength, nr_settings["medium"])
        filters.append(f"afftdn=nr={nr_config['nr']}:nt={nr_config['nt']}")
        
        # Electrical hum removal (50Hz and 60Hz + harmonics)
        if enable_hum_removal:
            filters.extend([
                "highpass=f=80",  # Remove very low frequencies
                "equalizer=f=50:t=q:width=2:g=-20",   # 50Hz notch
                "equalizer=f=60:t=q:width=2:g=-20",   # 60Hz notch
                "equalizer=f=100:t=q:width=2:g=-12",  # 100Hz harmonic
                "equalizer=f=120:t=q:width=2:g=-12",  # 120Hz harmonic
            ])
        
        # Click and pop removal
        if enable_click_removal:
            filters.append("adeclick=t=0.02:w=0.5")
            filters.append("adeclip=t=0.02:a=0.8")
        
        # Echo cancellation and reverb reduction
        if enable_echo_cancellation:
            filters.extend([
                "aecho=0.8:0.88:60:0.4",  # Echo reduction
                "highpass=f=100",          # Remove low-end mud
                "compand=attacks=0.02:decays=0.05:points=-80/-80|-20/-15|0/-10|20/0"  # De-reverb compression
            ])
        
        # Adaptive frequency filtering based on content
        if audio_chars['mean_volume'] < -25:  # Very quiet audio
            filters.extend([
                "highpass=f=120",
                "lowpass=f=12000",
                "equalizer=f=2000:t=h:width=1000:g=3"  # Boost speech frequencies
            ])
        else:
            filters.extend([
                "highpass=f=85",
                "lowpass=f=15000"
            ])
        
        # Speech enhancement EQ
        filters.extend([
            "equalizer=f=200:t=h:width=100:g=-2",    # Reduce muddiness
            "equalizer=f=1000:t=h:width=500:g=1",    # Enhance clarity
            "equalizer=f=3000:t=h:width=800:g=2.5",  # Boost presence
            "equalizer=f=8000:t=h:width=1500:g=1.2", # Add air
        ])
        
        # Dynamic range processing
        if audio_chars.get('needs_compression', False):
            filters.append("acompressor=threshold=-20dB:ratio=4:attack=3:release=30:makeup=2")
        
        # Adaptive gain normalization
        target_level = -16.0
        gain_adjustment = target_level - audio_chars['mean_volume']
        if abs(gain_adjustment) > 1.5:
            gain_adjustment = max(-15, min(15, gain_adjustment))
            filters.append(f"volume={gain_adjustment}dB")
        
        # Final processing
        filters.extend([
            "alimiter=level_in=1:level_out=0.95:limit=0.95",  # Prevent clipping
            "loudnorm=I=-16:LRA=11:TP=-1.5"  # Broadcast standard normalization
        ])
        
        af = ",".join(filters)
        
        # Execute with high-quality encoding
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", input_path,
            "-af", af,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
            "-movflags", "+faststart",
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error in advanced audio cleanup: {e}")
        # Fallback to basic enhancement
        try:
            return enhance_dialogue_audio(input_path, output_path)
        except:
            # Last resort: copy original
            try:
                shutil.copy(input_path, output_path)
                return True
            except:
                return False


def remove_background_noise(input_path: str, output_path: str, 
                           profile_duration: float = 1.0,
                           noise_reduction_db: float = 12.0) -> bool:
    """Remove background noise using noise profiling.
    
    Args:
        input_path: Input video file path
        output_path: Output video file path
        profile_duration: Duration in seconds to use for noise profiling
        noise_reduction_db: Amount of noise reduction in dB
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create noise profile from the beginning of the audio
        temp_profile = tempfile.mktemp(suffix=".wav")
        temp_clean = tempfile.mktemp(suffix=".wav")
        
        # Extract noise sample for profiling
        profile_cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", input_path,
            "-t", str(profile_duration),
            "-vn", "-ac", "1", "-ar", "16000",
            temp_profile
        ]
        run(profile_cmd, check=True)
        
        # Apply noise reduction using the profile
        af = f"afftdn=nr={noise_reduction_db}:nt=w:om=o:tn=1"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", input_path,
            "-af", af,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]
        
        run(cmd, check=True)
        
        # Cleanup temp files
        for temp_file in [temp_profile, temp_clean]:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error removing background noise: {e}")
        return False


def generate_subtitles_from_transcription(segments: List[dict], output_path: str, 
                                         subtitle_format: str = "srt",
                                         max_chars_per_line: int = 42,
                                         max_lines: int = 2,
                                         min_duration: float = 0.8) -> bool:
    """Generate subtitle files from transcription segments.
    
    Args:
        segments: List of transcription segments with start, end, and text
        output_path: Output subtitle file path
        subtitle_format: Format - "srt", "vtt", "ass", or "json"
        max_chars_per_line: Maximum characters per subtitle line
        max_lines: Maximum lines per subtitle
        min_duration: Minimum duration for each subtitle
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not segments:
            return False
        
        # Process segments for better subtitle timing
        processed_segments = []
        for seg in segments:
            text = seg.get('text', '').strip()
            if not text:
                continue
                
            start_time = float(seg.get('start', 0))
            end_time = float(seg.get('end', start_time + min_duration))
            
            # Ensure minimum duration
            if end_time - start_time < min_duration:
                end_time = start_time + min_duration
            
            # Split long text into multiple lines
            lines = split_text_for_subtitles(text, max_chars_per_line, max_lines)
            
            for i, line_text in enumerate(lines):
                if not line_text.strip():
                    continue
                    
                # Calculate timing for this line
                line_duration = (end_time - start_time) / len(lines)
                line_start = start_time + (i * line_duration)
                line_end = line_start + line_duration
                
                processed_segments.append({
                    'start': line_start,
                    'end': line_end,
                    'text': line_text.strip()
                })
        
        # Generate subtitle file based on format
        if subtitle_format.lower() == "srt":
            return write_srt_file(processed_segments, output_path)
        elif subtitle_format.lower() == "vtt":
            return write_vtt_file(processed_segments, output_path)
        elif subtitle_format.lower() == "ass":
            return write_ass_file(processed_segments, output_path)
        elif subtitle_format.lower() == "json":
            return write_json_subtitles(processed_segments, output_path)
        else:
            print(f"Unsupported subtitle format: {subtitle_format}")
            return False
            
    except Exception as e:
        print(f"Error generating subtitles: {e}")
        return False


def split_text_for_subtitles(text: str, max_chars_per_line: int, max_lines: int) -> List[str]:
    """Split text into subtitle-friendly lines."""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        
        if len(test_line) <= max_chars_per_line:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Word is too long, split it
                lines.append(word[:max_chars_per_line])
                current_line = word[max_chars_per_line:]
    
    if current_line:
        lines.append(current_line)
    
    # Limit to max_lines, combining if necessary
    if len(lines) > max_lines:
        combined_lines = []
        for i in range(0, len(lines), max_lines):
            chunk = lines[i:i + max_lines]
            combined_lines.append("\n".join(chunk))
        return combined_lines[:max_lines]
    
    return lines


def write_srt_file(segments: List[dict], output_path: str) -> bool:
    """Write SRT subtitle file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments, 1):
                start_time = format_srt_time(seg['start'])
                end_time = format_srt_time(seg['end'])
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{seg['text']}\n\n")
        
        return True
    except Exception as e:
        print(f"Error writing SRT file: {e}")
        return False


def write_vtt_file(segments: List[dict], output_path: str) -> bool:
    """Write WebVTT subtitle file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            
            for seg in segments:
                start_time = format_vtt_time(seg['start'])
                end_time = format_vtt_time(seg['end'])
                
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{seg['text']}\n\n")
        
        return True
    except Exception as e:
        print(f"Error writing VTT file: {e}")
        return False


def write_ass_file(segments: List[dict], output_path: str) -> bool:
    """Write ASS subtitle file with styling."""
    try:
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,10,1
Style: Karaoke,Arial,52,&H00FFFF00,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(header)
            
            for seg in segments:
                start_time = format_ass_time(seg['start'])
                end_time = format_ass_time(seg['end'])
                text = seg['text'].replace('\n', '\\N')
                
                f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n")
        
        return True
    except Exception as e:
        print(f"Error writing ASS file: {e}")
        return False


def write_json_subtitles(segments: List[dict], output_path: str) -> bool:
    """Write JSON subtitle file for programmatic use."""
    try:
        import json
        
        subtitle_data = {
            "format": "json",
            "version": "1.0",
            "segments": segments
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error writing JSON subtitles: {e}")
        return False


def format_srt_time(seconds: float) -> str:
    """Format time for SRT format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format time for WebVTT format (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"


def format_ass_time(seconds: float) -> str:
    """Format time for ASS format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def create_animated_subtitles(input_path: str, subtitle_path: str, output_path: str,
                             style: str = "karaoke", font_size: int = 48,
                             font_color: str = "white", outline_color: str = "black") -> bool:
    """Create video with animated subtitles burned in.
    
    Args:
        input_path: Input video file
        subtitle_path: Subtitle file path (SRT or ASS)
        output_path: Output video with burned subtitles
        style: Animation style - "karaoke", "typewriter", "fade", "bounce"
        font_size: Font size for subtitles
        font_color: Font color
        outline_color: Outline color
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(input_path) or not os.path.exists(subtitle_path):
            return False
        
        # Determine subtitle format
        subtitle_ext = os.path.splitext(subtitle_path)[1].lower()
        
        if subtitle_ext == '.ass':
            # Use ASS file directly with custom styling
            escaped_subtitle_path = subtitle_path.replace(':', '\\:')
            subtitle_filter = f"ass={escaped_subtitle_path}"
        else:
            # Convert SRT to styled subtitles
            if style == "karaoke":
                subtitle_filter = create_karaoke_filter(subtitle_path, font_size, font_color, outline_color)
            elif style == "typewriter":
                subtitle_filter = create_typewriter_filter(subtitle_path, font_size, font_color, outline_color)
            elif style == "fade":
                subtitle_filter = create_fade_filter(subtitle_path, font_size, font_color, outline_color)
            elif style == "bounce":
                subtitle_filter = create_bounce_filter(subtitle_path, font_size, font_color, outline_color)
            else:
                # Default simple subtitles
                escaped_subtitle_path = subtitle_path.replace(':', '\\:')
                subtitle_filter = f"subtitles={escaped_subtitle_path}:force_style='Fontsize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", input_path,
            "-vf", subtitle_filter,
            "-c:a", "copy",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-movflags", "+faststart",
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating animated subtitles: {e}")
        return False


def create_karaoke_filter(subtitle_path: str, font_size: int, font_color: str, outline_color: str) -> str:
    """Create karaoke-style subtitle filter."""
    escaped_subtitle_path = subtitle_path.replace(':', '\\:')
    return f"subtitles={escaped_subtitle_path}:force_style='Fontsize={font_size},PrimaryColour=&H00FFFF00,OutlineColour=&H00000000,Outline=2,Karaoke=1'"


def create_typewriter_filter(subtitle_path: str, font_size: int, font_color: str, outline_color: str) -> str:
    """Create typewriter-style subtitle filter."""
    escaped_subtitle_path = subtitle_path.replace(':', '\\:')
    return f"subtitles={escaped_subtitle_path}:force_style='Fontsize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'"


def create_fade_filter(subtitle_path: str, font_size: int, font_color: str, outline_color: str) -> str:
    """Create fade-in/out subtitle filter."""
    escaped_subtitle_path = subtitle_path.replace(':', '\\:')
    return f"subtitles={escaped_subtitle_path}:force_style='Fontsize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Fade=300'"


def create_bounce_filter(subtitle_path: str, font_size: int, font_color: str, outline_color: str) -> str:
    """Create bouncing subtitle filter."""
    escaped_subtitle_path = subtitle_path.replace(':', '\\:')
    return f"subtitles={escaped_subtitle_path}:force_style='Fontsize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,ScaleX=110,ScaleY=110'"


# =========================
# AI B-roll insertion system
# =========================

import requests
import re
from typing import Optional, Tuple
from urllib.parse import quote


def extract_broll_keywords(transcript_text: str, segments: List[dict]) -> List[dict]:
    """Extract keywords and phrases suitable for B-roll insertion.
    
    Args:
        transcript_text: Full transcript text
        segments: Transcription segments with timing
    
    Returns:
        List of keyword opportunities with timing and search terms
    """
    # Keywords that typically benefit from B-roll
    broll_triggers = {
        'places': r'\b(?:in|at|to|from|visit|travel|go to|went to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        'objects': r'\b(?:using|with|holding|showing|demonstrating)\s+(?:a|an|the)?\s*([a-z]+(?:\s+[a-z]+)*)',
        'activities': r'\b(?:doing|performing|practicing|learning|teaching)\s+([a-z]+(?:\s+[a-z]+)*)',
        'concepts': r'\b(?:about|discussing|explaining|talking about)\s+([a-z]+(?:\s+[a-z]+)*)',
        'nature': r'\b(mountains?|ocean|sea|forest|desert|beach|lake|river|sunset|sunrise|clouds?|sky)\b',
        'technology': r'\b(computer|laptop|phone|smartphone|tablet|software|app|website|internet|AI|artificial intelligence)\b',
        'business': r'\b(office|meeting|presentation|conference|team|company|business|work|project)\b',
        'food': r'\b(cooking|eating|restaurant|food|meal|dinner|lunch|breakfast|kitchen)\b',
        'sports': r'\b(playing|game|sport|football|basketball|tennis|running|gym|exercise|fitness)\b',
        'education': r'\b(school|university|college|student|teacher|learning|studying|classroom|book)\b'
    }
    
    opportunities = []
    
    for segment in segments:
        text = segment.get('text', '').strip()
        start_time = segment.get('start', 0)
        end_time = segment.get('end', start_time + 1)
        
        # Check for keyword matches
        for category, pattern in broll_triggers.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                keyword = match.group(1) if match.groups() else match.group(0)
                
                opportunities.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'keyword': keyword.strip(),
                    'category': category,
                    'context': text,
                    'search_terms': generate_search_terms(keyword, category)
                })
    
    # Remove duplicates and sort by time
    unique_opportunities = []
    seen_keywords = set()
    
    for opp in sorted(opportunities, key=lambda x: x['start_time']):
        key = f"{opp['keyword'].lower()}_{opp['start_time']}"
        if key not in seen_keywords:
            seen_keywords.add(key)
            unique_opportunities.append(opp)
    
    return unique_opportunities


def generate_search_terms(keyword: str, category: str) -> List[str]:
    """Generate multiple search terms for better B-roll matching."""
    base_terms = [keyword.lower()]
    
    # Add category-specific variations
    if category == 'places':
        base_terms.extend([f"{keyword} city", f"{keyword} landscape", f"{keyword} aerial"])
    elif category == 'technology':
        base_terms.extend([f"{keyword} modern", f"{keyword} digital", f"{keyword} tech"])
    elif category == 'nature':
        base_terms.extend([f"{keyword} nature", f"{keyword} beautiful", f"{keyword} scenic"])
    elif category == 'business':
        base_terms.extend([f"{keyword} professional", f"{keyword} corporate", f"{keyword} modern"])
    elif category == 'food':
        base_terms.extend([f"{keyword} delicious", f"{keyword} fresh", f"{keyword} gourmet"])
    
    return base_terms[:3]  # Limit to 3 search terms


def search_pixabay_media(keyword: str, media_type: str = "video", api_key: str = None) -> List[dict]:
    """Search Pixabay for royalty-free media.
    
    Args:
        keyword: Search keyword
        media_type: "video" or "photo"
        api_key: Pixabay API key
    
    Returns:
        List of media items with download URLs
    """
    if not api_key:
        print("Warning: No Pixabay API key provided")
        return []
    
    try:
        url = f"https://pixabay.com/api/{media_type}s/"
        params = {
            'key': api_key,
            'q': quote(keyword),
            'video_type': 'film' if media_type == 'video' else None,
            'category': 'all',
            'min_width': 1920 if media_type == 'video' else 1280,
            'min_height': 1080 if media_type == 'video' else 720,
            'per_page': 10,
            'safesearch': 'true'
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for item in data.get('hits', []):
            if media_type == 'video':
                # Get the best quality video
                videos = item.get('videos', {})
                video_url = (videos.get('large', {}).get('url') or 
                           videos.get('medium', {}).get('url') or 
                           videos.get('small', {}).get('url'))
                
                if video_url:
                    results.append({
                        'type': 'video',
                        'url': video_url,
                        'duration': item.get('duration', 10),
                        'width': videos.get('large', {}).get('width', 1920),
                        'height': videos.get('large', {}).get('height', 1080),
                        'source': 'pixabay',
                        'id': item.get('id'),
                        'tags': item.get('tags', '')
                    })
            else:
                # Get high resolution image
                image_url = item.get('largeImageURL') or item.get('webformatURL')
                if image_url:
                    results.append({
                        'type': 'image',
                        'url': image_url,
                        'width': item.get('imageWidth', 1920),
                        'height': item.get('imageHeight', 1080),
                        'source': 'pixabay',
                        'id': item.get('id'),
                        'tags': item.get('tags', '')
                    })
        
        return results
        
    except Exception as e:
        print(f"Error searching Pixabay: {e}")
        return []


def search_pexels_media(keyword: str, media_type: str = "video", api_key: str = None) -> List[dict]:
    """Search Pexels for royalty-free media."""
    if not api_key:
        print("Warning: No Pexels API key provided")
        return []
    
    try:
        if media_type == "video":
            url = "https://api.pexels.com/videos/search"
        else:
            url = "https://api.pexels.com/v1/search"
        
        headers = {'Authorization': api_key}
        params = {
            'query': keyword,
            'per_page': 10,
            'size': 'large'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for item in data.get('videos' if media_type == 'video' else 'photos', []):
            if media_type == 'video':
                # Get the best quality video file
                video_files = item.get('video_files', [])
                best_video = None
                
                for vf in video_files:
                    if vf.get('quality') == 'hd' and vf.get('width', 0) >= 1920:
                        best_video = vf
                        break
                
                if not best_video and video_files:
                    best_video = max(video_files, key=lambda x: x.get('width', 0))
                
                if best_video:
                    results.append({
                        'type': 'video',
                        'url': best_video.get('link'),
                        'duration': item.get('duration', 10),
                        'width': best_video.get('width', 1920),
                        'height': best_video.get('height', 1080),
                        'source': 'pexels',
                        'id': item.get('id')
                    })
            else:
                # Get high resolution image
                src = item.get('src', {})
                image_url = src.get('large2x') or src.get('large') or src.get('medium')
                
                if image_url:
                    results.append({
                        'type': 'image',
                        'url': image_url,
                        'width': item.get('width', 1920),
                        'height': item.get('height', 1080),
                        'source': 'pexels',
                        'id': item.get('id')
                    })
        
        return results
        
    except Exception as e:
        print(f"Error searching Pexels: {e}")
        return []


def search_unsplash_images(keyword: str, api_key: str = None) -> List[dict]:
    """Search Unsplash for royalty-free images."""
    if not api_key:
        print("Warning: No Unsplash API key provided")
        return []
    
    try:
        url = "https://api.unsplash.com/search/photos"
        headers = {'Authorization': f'Client-ID {api_key}'}
        params = {
            'query': keyword,
            'per_page': 10,
            'orientation': 'landscape'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for item in data.get('results', []):
            urls = item.get('urls', {})
            image_url = urls.get('regular') or urls.get('small')
            
            if image_url:
                results.append({
                    'type': 'image',
                    'url': image_url,
                    'width': item.get('width', 1920),
                    'height': item.get('height', 1080),
                    'source': 'unsplash',
                    'id': item.get('id'),
                    'description': item.get('description', '')
                })
        
        return results
        
    except Exception as e:
        print(f"Error searching Unsplash: {e}")
        return []


def download_media_file(media_item: dict, output_dir: str) -> Optional[str]:
    """Download media file from URL.
    
    Args:
        media_item: Media item dict with URL and metadata
        output_dir: Directory to save downloaded files
    
    Returns:
        Path to downloaded file or None if failed
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        url = media_item['url']
        source = media_item['source']
        media_id = media_item['id']
        media_type = media_item['type']
        
        # Determine file extension
        if media_type == 'video':
            ext = '.mp4'
        else:
            ext = '.jpg'
        
        filename = f"{source}_{media_id}{ext}"
        filepath = os.path.join(output_dir, filename)
        
        # Skip if already downloaded
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath
        
        # Download file
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        if os.path.getsize(filepath) > 0:
            return filepath
        else:
            os.remove(filepath)
            return None
            
    except Exception as e:
        print(f"Error downloading media: {e}")
        return None


def find_and_download_broll(opportunities: List[dict], output_dir: str,
                           pixabay_key: str = None, pexels_key: str = None, 
                           unsplash_key: str = None) -> List[dict]:
    """Find and download B-roll media for keyword opportunities.
    
    Args:
        opportunities: List of keyword opportunities
        output_dir: Directory to save downloaded media
        pixabay_key: Pixabay API key
        pexels_key: Pexels API key  
        unsplash_key: Unsplash API key
    
    Returns:
        List of opportunities with downloaded media paths
    """
    enhanced_opportunities = []
    
    for opp in opportunities:
        print(f"Searching B-roll for: {opp['keyword']}")
        
        media_found = False
        downloaded_media = []
        
        # Try each search term
        for search_term in opp['search_terms']:
            if media_found:
                break
                
            # Search video sources first
            for source_func, api_key in [
                (lambda k, t: search_pixabay_media(k, "video", pixabay_key), pixabay_key),
                (lambda k, t: search_pexels_media(k, "video", pexels_key), pexels_key)
            ]:
                if api_key and not media_found:
                    results = source_func(search_term, "video")
                    
                    for media_item in results[:2]:  # Try top 2 results
                        filepath = download_media_file(media_item, output_dir)
                        if filepath:
                            downloaded_media.append({
                                'path': filepath,
                                'type': 'video',
                                'source': media_item['source'],
                                'duration': media_item.get('duration', 10)
                            })
                            media_found = True
                            break
            
            # If no video found, try images
            if not media_found:
                for source_func, api_key in [
                    (lambda k: search_pixabay_media(k, "photo", pixabay_key), pixabay_key),
                    (lambda k: search_pexels_media(k, "photo", pexels_key), pexels_key),
                    (lambda k: search_unsplash_images(k, unsplash_key), unsplash_key)
                ]:
                    if api_key and not media_found:
                        results = source_func(search_term)
                        
                        for media_item in results[:1]:  # Try top result
                            filepath = download_media_file(media_item, output_dir)
                            if filepath:
                                downloaded_media.append({
                                    'path': filepath,
                                    'type': 'image',
                                    'source': media_item['source']
                                })
                                media_found = True
                                break
        
        # Add media to opportunity
        opp['broll_media'] = downloaded_media
        opp['has_media'] = len(downloaded_media) > 0
        enhanced_opportunities.append(opp)
        
        if downloaded_media:
            print(f"✅ Found B-roll for '{opp['keyword']}': {len(downloaded_media)} files")
        else:
            print(f"❌ No B-roll found for '{opp['keyword']}'")
    
    return enhanced_opportunities


def insert_broll_into_video(input_video: str, broll_opportunities: List[dict], 
                           output_video: str, overlay_opacity: float = 0.8,
                           transition_duration: float = 0.5) -> bool:
    """Insert B-roll media into video at specified timestamps.
    
    Args:
        input_video: Original video path
        broll_opportunities: List of opportunities with downloaded media
        output_video: Output video path
        overlay_opacity: Opacity of B-roll overlay (0.0-1.0)
        transition_duration: Duration of fade transitions
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Filter opportunities that have media
        valid_opportunities = [opp for opp in broll_opportunities if opp.get('has_media', False)]
        
        if not valid_opportunities:
            print("No B-roll media available for insertion")
            shutil.copy(input_video, output_video)
            return True
        
        # Build complex filter for B-roll insertion
        filter_complex = []
        input_labels = ["0:v"]
        
        for i, opp in enumerate(valid_opportunities):
            media_item = opp['broll_media'][0]  # Use first media item
            media_path = media_item['path']
            start_time = opp['start_time']
            duration = min(opp['end_time'] - start_time, 5.0)  # Max 5 seconds
            
            # Add media as input
            input_labels.append(f"{i+1}:v")
            
            if media_item['type'] == 'image':
                # Convert image to video segment
                filter_complex.append(
                    f"[{i+1}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS,"
                    f"fade=t=in:st=0:d={transition_duration},"
                    f"fade=t=out:st={duration-transition_duration}:d={transition_duration}[broll{i}]"
                )
            else:
                # Process video segment
                filter_complex.append(
                    f"[{i+1}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS,"
                    f"fade=t=in:st=0:d={transition_duration},"
                    f"fade=t=out:st={duration-transition_duration}:d={transition_duration}[broll{i}]"
                )
            
            # Overlay B-roll on main video
            if i == 0:
                filter_complex.append(
                    f"[0:v][broll{i}]overlay=enable='between(t,{start_time},{start_time+duration})':alpha={overlay_opacity}[v{i}]"
                )
            else:
                filter_complex.append(
                    f"[v{i-1}][broll{i}]overlay=enable='between(t,{start_time},{start_time+duration})':alpha={overlay_opacity}[v{i}]"
                )
        
        # Build FFmpeg command
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y"]
        
        # Add input files
        cmd.extend(["-i", input_video])
        for opp in valid_opportunities:
            media_path = opp['broll_media'][0]['path']
            cmd.extend(["-i", media_path])
        
        # Add filter complex
        if filter_complex:
            cmd.extend(["-filter_complex", ";".join(filter_complex)])
            cmd.extend(["-map", f"[v{len(valid_opportunities)-1}]"])
        else:
            cmd.extend(["-c:v", "copy"])
        
        # Add audio and output settings
        cmd.extend([
            "-map", "0:a",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_video
        ])
        
        run(cmd, check=True)
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0
        
    except Exception as e:
        print(f"Error inserting B-roll: {e}")
        # Fallback: copy original video
        try:
            shutil.copy(input_video, output_video)
            return True
        except:
            return False


# =========================
# AI-Generated Background Music System
# =========================

import json
import base64
import time
from typing import Optional, Dict, Any


def generate_music_prompt(transcript_text: str, video_duration: float) -> str:
    """Generate a music prompt based on video content and mood.
    
    Args:
        transcript_text: Full transcript of the video
        video_duration: Duration of video in seconds
    
    Returns:
        Music generation prompt string
    """
    # Analyze content for mood and style
    content_lower = transcript_text.lower()
    
    # Determine mood based on content
    if any(word in content_lower for word in ['exciting', 'amazing', 'incredible', 'wow', 'fantastic']):
        mood = "upbeat and energetic"
    elif any(word in content_lower for word in ['calm', 'peaceful', 'relaxing', 'meditation', 'quiet']):
        mood = "calm and peaceful"
    elif any(word in content_lower for word in ['business', 'professional', 'corporate', 'meeting', 'work']):
        mood = "professional and modern"
    elif any(word in content_lower for word in ['tech', 'technology', 'digital', 'AI', 'computer', 'software']):
        mood = "modern and technological"
    elif any(word in content_lower for word in ['travel', 'adventure', 'journey', 'explore', 'discover']):
        mood = "adventurous and inspiring"
    elif any(word in content_lower for word in ['education', 'learning', 'tutorial', 'explain', 'teach']):
        mood = "focused and educational"
    else:
        mood = "neutral and pleasant"
    
    # Determine tempo based on content type
    if any(word in content_lower for word in ['fast', 'quick', 'rapid', 'speed', 'urgent']):
        tempo = "medium-fast tempo"
    elif any(word in content_lower for word in ['slow', 'careful', 'detailed', 'step by step']):
        tempo = "slow to medium tempo"
    else:
        tempo = "medium tempo"
    
    # Generate prompt
    duration_desc = "short" if video_duration < 60 else "medium length" if video_duration < 300 else "long"
    
    prompt = f"Instrumental background music, {mood}, {tempo}, {duration_desc} track, "
    prompt += "no vocals, suitable for voice-over, ambient, cinematic, royalty-free style"
    
    return prompt


def generate_music_with_riffusion(prompt: str, duration: float = 30.0) -> Optional[str]:
    """Generate music using Riffusion API (placeholder implementation).
    
    Args:
        prompt: Music generation prompt
        duration: Desired duration in seconds
    
    Returns:
        Path to generated audio file or None if failed
    """
    try:
        # Note: This is a placeholder implementation
        # In practice, you would need to integrate with actual Riffusion API
        print(f"Generating music with Riffusion: {prompt}")
        print(f"Duration: {duration} seconds")
        
        # Placeholder: return None to indicate service not available
        print("Riffusion API integration not implemented yet")
        return None
        
    except Exception as e:
        print(f"Error generating music with Riffusion: {e}")
        return None


def generate_music_with_stable_audio(prompt: str, duration: float = 30.0, api_key: str = None) -> Optional[str]:
    """Generate music using Stable Audio API (placeholder implementation).
    
    Args:
        prompt: Music generation prompt
        duration: Desired duration in seconds
        api_key: Stable Audio API key
    
    Returns:
        Path to generated audio file or None if failed
    """
    try:
        if not api_key:
            print("Warning: No Stable Audio API key provided")
            return None
            
        print(f"Generating music with Stable Audio: {prompt}")
        print(f"Duration: {duration} seconds")
        
        # Note: This is a placeholder implementation
        # In practice, you would integrate with the actual Stable Audio API
        print("Stable Audio API integration not implemented yet")
        return None
        
    except Exception as e:
        print(f"Error generating music with Stable Audio: {e}")
        return None


def generate_music_with_aiva(prompt: str, duration: float = 30.0, api_key: str = None) -> Optional[str]:
    """Generate music using AIVA API (placeholder implementation).
    
    Args:
        prompt: Music generation prompt
        duration: Desired duration in seconds
        api_key: AIVA API key
    
    Returns:
        Path to generated audio file or None if failed
    """
    try:
        if not api_key:
            print("Warning: No AIVA API key provided")
            return None
            
        print(f"Generating music with AIVA: {prompt}")
        print(f"Duration: {duration} seconds")
        
        # Note: This is a placeholder implementation
        # In practice, you would integrate with the actual AIVA API
        print("AIVA API integration not implemented yet")
        return None
        
    except Exception as e:
        print(f"Error generating music with AIVA: {e}")
        return None


def create_simple_background_music(duration: float, output_path: str, 
                                  style: str = "ambient") -> bool:
    """Create simple procedural background music using FFmpeg.
    
    Args:
        duration: Duration in seconds
        output_path: Output audio file path
        style: Music style (ambient, upbeat, calm)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Define different procedural music styles
        if style == "ambient":
            # Soft ambient tones
            filter_complex = (
                f"sine=frequency=220:duration={duration}[base];"
                f"sine=frequency=330:duration={duration}[harmony1];"
                f"sine=frequency=440:duration={duration}[harmony2];"
                f"[base][harmony1]amix=inputs=2:weights='0.6 0.3'[mix1];"
                f"[mix1][harmony2]amix=inputs=2:weights='0.8 0.2',"
                f"volume=0.3,"
                f"aecho=0.8:0.9:1000:0.3,"
                f"highpass=f=100,lowpass=f=8000[out]"
            )
        elif style == "upbeat":
            # More energetic with rhythm
            filter_complex = (
                f"sine=frequency=440:duration={duration}[base];"
                f"sine=frequency=660:duration={duration}[harmony1];"
                f"sine=frequency=880:duration={duration}[harmony2];"
                f"[base]volume=0.4[base_vol];"
                f"[harmony1]volume=0.2[harm1_vol];"
                f"[harmony2]volume=0.1[harm2_vol];"
                f"[base_vol][harm1_vol][harm2_vol]amix=inputs=3,"
                f"aecho=0.6:0.7:500:0.2,"
                f"highpass=f=150,lowpass=f=10000[out]"
            )
        else:  # calm
            # Gentle, soothing tones
            filter_complex = (
                f"sine=frequency=196:duration={duration}[base];"
                f"sine=frequency=294:duration={duration}[harmony];"
                f"[base][harmony]amix=inputs=2:weights='0.7 0.3',"
                f"volume=0.25,"
                f"aecho=1.0:0.8:1500:0.4,"
                f"highpass=f=80,lowpass=f=6000[out]"
            )
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(duration),
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating background music: {e}")
        return False


def generate_ai_background_music(transcript_text: str, video_duration: float,
                                output_path: str, riffusion_key: str = None,
                                stable_audio_key: str = None, aiva_key: str = None) -> Optional[str]:
    """Generate AI background music using available services.
    
    Args:
        transcript_text: Video transcript for context
        video_duration: Duration of video in seconds
        output_path: Output audio file path
        riffusion_key: Riffusion API key
        stable_audio_key: Stable Audio API key
        aiva_key: AIVA API key
    
    Returns:
        Path to generated music file or None if failed
    """
    # Generate music prompt based on content
    prompt = generate_music_prompt(transcript_text, video_duration)
    print(f"Generated music prompt: {prompt}")
    
    # Try AI services in order of preference
    music_file = None
    
    # Try Stable Audio first (usually highest quality)
    if stable_audio_key and not music_file:
        music_file = generate_music_with_stable_audio(prompt, video_duration, stable_audio_key)
    
    # Try AIVA
    if aiva_key and not music_file:
        music_file = generate_music_with_aiva(prompt, video_duration, aiva_key)
    
    # Try Riffusion
    if riffusion_key and not music_file:
        music_file = generate_music_with_riffusion(prompt, video_duration)
    
    # Fallback to procedural generation
    if not music_file:
        print("No AI music services available, using procedural generation")
        
        # Determine style from prompt
        if "energetic" in prompt or "upbeat" in prompt:
            style = "upbeat"
        elif "calm" in prompt or "peaceful" in prompt:
            style = "calm"
        else:
            style = "ambient"
        
        if create_simple_background_music(video_duration, output_path, style):
            music_file = output_path
    
    return music_file


def apply_voice_ducking(video_path: str, music_path: str, output_path: str,
                       duck_threshold: float = -20.0, duck_ratio: float = 4.0,
                       duck_attack: float = 0.1, duck_release: float = 0.5,
                       music_volume: float = 0.3) -> bool:
    """Apply automatic voice ducking to background music.
    
    Args:
        video_path: Input video with voice track
        music_path: Background music file
        output_path: Output video with ducked music
        duck_threshold: Threshold in dB for ducking trigger
        duck_ratio: Compression ratio for ducking
        duck_attack: Attack time in seconds
        duck_release: Release time in seconds
        music_volume: Base volume level for music (0.0-1.0)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get video duration to loop music if needed
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video_path
        ]
        
        result = run(probe_cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        video_duration = float(video_info['format']['duration'])
        
        # Build filter complex for voice ducking
        filter_complex = (
            # Loop/trim music to match video duration
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={video_duration},volume={music_volume}[music];"
            # Apply sidechaining (ducking) - music volume reduces when voice is present
            f"[0:a][music]sidechaincompress=threshold={duck_threshold}dB:"
            f"ratio={duck_ratio}:attack={duck_attack}:release={duck_release}[audio_out]"
        )
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[audio_out]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error applying voice ducking: {e}")
        # Fallback: copy original video
        try:
            shutil.copy(video_path, output_path)
            return True
        except:
            return False


def add_background_music_to_video(video_path: str, transcript_text: str,
                                 output_path: str, temp_dir: str = "temp_music",
                                 riffusion_key: str = None, stable_audio_key: str = None,
                                 aiva_key: str = None, music_volume: float = 0.3,
                                 enable_ducking: bool = True) -> bool:
    """Add AI-generated background music with voice ducking to video.
    
    Args:
        video_path: Input video path
        transcript_text: Video transcript for music generation
        output_path: Output video path
        temp_dir: Temporary directory for music files
        riffusion_key: Riffusion API key
        stable_audio_key: Stable Audio API key
        aiva_key: AIVA API key
        music_volume: Base volume for background music
        enable_ducking: Whether to enable voice ducking
    
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(temp_dir, exist_ok=True)
        
        # Get video duration
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video_path
        ]
        
        result = run(probe_cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        video_duration = float(video_info['format']['duration'])
        
        # Generate background music
        music_file = os.path.join(temp_dir, "background_music.aac")
        generated_music = generate_ai_background_music(
            transcript_text, video_duration, music_file,
            riffusion_key, stable_audio_key, aiva_key
        )
        
        if not generated_music or not os.path.exists(generated_music):
            print("Failed to generate background music")
            shutil.copy(video_path, output_path)
            return True
        
        # Apply voice ducking if enabled
        if enable_ducking:
            print("Applying voice ducking to background music")
            success = apply_voice_ducking(
                video_path, generated_music, output_path,
                music_volume=music_volume
            )
        else:
            # Simple mix without ducking
            print("Adding background music without ducking")
            filter_complex = (
                f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={video_duration},volume={music_volume}[music];"
                f"[0:a][music]amix=inputs=2:weights='0.8 0.2'[audio_out]"
            )
            
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-y",
                "-i", video_path,
                "-i", generated_music,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[audio_out]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]
            
            run(cmd, check=True)
            success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
        # Cleanup temporary files
        try:
            if os.path.exists(generated_music):
                os.remove(generated_music)
        except:
            pass
        
        return success
        
    except Exception as e:
        print(f"Error adding background music: {e}")
        # Fallback: copy original video
        try:
            shutil.copy(video_path, output_path)
            return True
        except:
            return False


# =========================
# Intro and Outro Card System
# =========================

from PIL import Image, ImageDraw, ImageFont
import textwrap
from typing import Dict, List, Tuple


def create_intro_card_template(width: int = 1920, height: int = 1080,
                              background_color: str = "#1a1a2e",
                              gradient_colors: List[str] = None) -> Image.Image:
    """Create a base intro card template with gradient background.
    
    Args:
        width: Card width in pixels
        height: Card height in pixels
        background_color: Solid background color (hex)
        gradient_colors: List of colors for gradient [start, end]
    
    Returns:
        PIL Image object
    """
    # Create base image
    img = Image.new('RGB', (width, height), background_color)
    
    if gradient_colors and len(gradient_colors) >= 2:
        # Create gradient background
        draw = ImageDraw.Draw(img)
        
        # Parse hex colors
        start_color = tuple(int(gradient_colors[0][i:i+2], 16) for i in (1, 3, 5))
        end_color = tuple(int(gradient_colors[1][i:i+2], 16) for i in (1, 3, 5))
        
        # Create vertical gradient
        for y in range(height):
            ratio = y / height
            r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
            g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
            b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
            
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    return img


def add_text_to_card(img: Image.Image, text: str, position: str = "center",
                    font_size: int = 72, font_color: str = "white",
                    font_family: str = "arial", max_width: int = 1600,
                    shadow: bool = True, shadow_offset: Tuple[int, int] = (3, 3)) -> Image.Image:
    """Add text to intro card with formatting options.
    
    Args:
        img: PIL Image to add text to
        text: Text content
        position: Text position ("center", "top", "bottom")
        font_size: Font size in pixels
        font_color: Text color (hex or name)
        font_family: Font family name
        max_width: Maximum text width for wrapping
        shadow: Whether to add text shadow
        shadow_offset: Shadow offset (x, y)
    
    Returns:
        Modified PIL Image
    """
    draw = ImageDraw.Draw(img)
    
    # Try to load custom font, fallback to default
    try:
        if font_family.lower() in ['arial', 'helvetica']:
            font = ImageFont.truetype("arial.ttf", font_size)
        elif font_family.lower() == 'times':
            font = ImageFont.truetype("times.ttf", font_size)
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Wrap text to fit within max_width
    avg_char_width = font_size * 0.6  # Approximate character width
    chars_per_line = int(max_width / avg_char_width)
    wrapped_lines = textwrap.wrap(text, width=chars_per_line)
    
    # Calculate total text height
    line_height = font_size + 10
    total_height = len(wrapped_lines) * line_height
    
    # Determine text position
    img_width, img_height = img.size
    
    if position == "center":
        start_y = (img_height - total_height) // 2
    elif position == "top":
        start_y = img_height // 6
    else:  # bottom
        start_y = img_height - img_height // 6 - total_height
    
    # Draw each line
    for i, line in enumerate(wrapped_lines):
        # Get text dimensions
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        
        # Center horizontally
        x = (img_width - text_width) // 2
        y = start_y + i * line_height
        
        # Draw shadow if enabled
        if shadow:
            shadow_x = x + shadow_offset[0]
            shadow_y = y + shadow_offset[1]
            draw.text((shadow_x, shadow_y), line, font=font, fill="black")
        
        # Draw main text
        draw.text((x, y), line, font=font, fill=font_color)
    
    return img


def add_logo_to_card(img: Image.Image, logo_path: str, position: str = "top-right",
                    size: Tuple[int, int] = (200, 200), margin: int = 50,
                    opacity: float = 1.0) -> Image.Image:
    """Add logo to intro card.
    
    Args:
        img: PIL Image to add logo to
        logo_path: Path to logo image file
        position: Logo position ("top-left", "top-right", "bottom-left", "bottom-right", "center")
        size: Logo size (width, height)
        margin: Margin from edges
        opacity: Logo opacity (0.0-1.0)
    
    Returns:
        Modified PIL Image
    """
    try:
        if not os.path.exists(logo_path):
            print(f"Logo file not found: {logo_path}")
            return img
        
        # Load and resize logo
        logo = Image.open(logo_path)
        logo = logo.convert("RGBA")
        logo = logo.resize(size, Image.Resampling.LANCZOS)
        
        # Apply opacity
        if opacity < 1.0:
            alpha = logo.split()[-1]
            alpha = alpha.point(lambda p: int(p * opacity))
            logo.putalpha(alpha)
        
        # Calculate position
        img_width, img_height = img.size
        logo_width, logo_height = logo.size
        
        if position == "top-left":
            x, y = margin, margin
        elif position == "top-right":
            x, y = img_width - logo_width - margin, margin
        elif position == "bottom-left":
            x, y = margin, img_height - logo_height - margin
        elif position == "bottom-right":
            x, y = img_width - logo_width - margin, img_height - logo_height - margin
        else:  # center
            x = (img_width - logo_width) // 2
            y = (img_height - logo_height) // 2
        
        # Paste logo onto image
        if logo.mode == 'RGBA':
            img.paste(logo, (x, y), logo)
        else:
            img.paste(logo, (x, y))
        
    except Exception as e:
        print(f"Error adding logo: {e}")
    
    return img


def create_intro_card(title: str, subtitle: str = "", logo_path: str = None,
                     template_config: Dict = None, output_path: str = "intro_card.png") -> bool:
    """Create a complete intro card with title, subtitle, and logo.
    
    Args:
        title: Main title text
        subtitle: Optional subtitle text
        logo_path: Path to logo image
        template_config: Configuration dict for styling
        output_path: Output image path
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Default configuration
        config = {
            'width': 1920,
            'height': 1080,
            'background_color': '#1a1a2e',
            'gradient_colors': ['#1a1a2e', '#16213e'],
            'title_font_size': 84,
            'title_color': '#ffffff',
            'subtitle_font_size': 48,
            'subtitle_color': '#cccccc',
            'logo_size': (200, 200),
            'logo_position': 'top-right'
        }
        
        # Update with user config
        if template_config:
            config.update(template_config)
        
        # Create base template
        img = create_intro_card_template(
            config['width'], config['height'],
            config['background_color'], config.get('gradient_colors')
        )
        
        # Add title
        img = add_text_to_card(
            img, title, "center",
            config['title_font_size'], config['title_color']
        )
        
        # Add subtitle if provided
        if subtitle:
            # Position subtitle below title
            img = add_text_to_card(
                img, subtitle, "center",
                config['subtitle_font_size'], config['subtitle_color']
            )
        
        # Add logo if provided
        if logo_path and os.path.exists(logo_path):
            img = add_logo_to_card(
                img, logo_path, config['logo_position'],
                config['logo_size']
            )
        
        # Save image
        img.save(output_path, 'PNG', quality=95)
        return os.path.exists(output_path)
        
    except Exception as e:
        print(f"Error creating intro card: {e}")
        return False


def create_intro_video_from_card(card_path: str, output_path: str,
                                duration: float = 4.0, transition_type: str = "fade") -> bool:
    """Convert intro card image to video with animation.
    
    Args:
        card_path: Path to intro card image
        output_path: Output video path
        duration: Duration in seconds
        transition_type: Animation type ("fade", "slide", "zoom")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(card_path):
            print(f"Intro card not found: {card_path}")
            return False
        
        # Build filter based on transition type
        if transition_type == "fade":
            # Fade in effect
            filter_complex = f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.5}:d=0.5"
        elif transition_type == "slide":
            # Slide in from left
            filter_complex = f"crop=1920:1080:0+1920*min(t/{duration}\,1):0"
        elif transition_type == "zoom":
            # Zoom in effect
            filter_complex = f"scale=1920*max(1\,1.2-0.2*t/{duration}):1080*max(1\,1.2-0.2*t/{duration}),crop=1920:1080"
        else:
            # No animation
            filter_complex = "scale=1920:1080"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-loop", "1",
            "-i", card_path,
            "-vf", filter_complex,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating intro video: {e}")
        return False


def add_intro_to_video(main_video: str, intro_config: Dict, output_path: str,
                      temp_dir: str = "temp_intro") -> bool:
    """Add intro card to the beginning of a video.
    
    Args:
        main_video: Path to main video file
        intro_config: Configuration for intro card
        output_path: Output video path
        temp_dir: Temporary directory for intro files
    
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create intro card image
        card_path = os.path.join(temp_dir, "intro_card.png")
        card_created = create_intro_card(
            intro_config.get('title', 'Video Title'),
            intro_config.get('subtitle', ''),
            intro_config.get('logo_path'),
            intro_config.get('template_config'),
            card_path
        )
        
        if not card_created:
            print("Failed to create intro card")
            shutil.copy(main_video, output_path)
            return True
        
        # Create intro video
        intro_video_path = os.path.join(temp_dir, "intro_video.mp4")
        intro_duration = intro_config.get('duration', 4.0)
        transition_type = intro_config.get('transition', 'fade')
        
        intro_created = create_intro_video_from_card(
            card_path, intro_video_path, intro_duration, transition_type
        )
        
        if not intro_created:
            print("Failed to create intro video")
            shutil.copy(main_video, output_path)
            return True
        
        # Concatenate intro with main video
        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, 'w') as f:
            f.write(f"file '{os.path.abspath(intro_video_path)}'\n")
            f.write(f"file '{os.path.abspath(main_video)}'\n")
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        
        run(cmd, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
        # Cleanup temporary files
        try:
            for file_path in [card_path, intro_video_path, concat_list_path]:
                if os.path.exists(file_path):
                    os.remove(file_path)
        except:
            pass
        
        return success
        
    except Exception as e:
        print(f"Error adding intro to video: {e}")
        # Fallback: copy original video
        try:
            shutil.copy(main_video, output_path)
            return True
        except:
            return False


# =========================
# Outro Card System
# =========================

def create_outro_card(title: str = "Thanks for Watching!", 
                      social_handles: Dict[str, str] = None,
                      call_to_action: str = "Subscribe for more content",
                      logo_path: str = None,
                      template_config: Dict = None,
                      output_path: str = "outro_card.png") -> bool:
    """Create an outro card with social handles and call-to-action.
    
    Args:
        title: Main outro message
        social_handles: Dict of social platform names and handles
        call_to_action: Call-to-action text
        logo_path: Path to logo image
        template_config: Configuration dict for styling
        output_path: Output image path
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Default configuration
        config = {
            'width': 1920,
            'height': 1080,
            'background_color': '#0f0f23',
            'gradient_colors': ['#0f0f23', '#1a1a2e'],
            'title_font_size': 72,
            'title_color': '#ffffff',
            'social_font_size': 36,
            'social_color': '#00d4ff',
            'cta_font_size': 48,
            'cta_color': '#ffaa00',
            'logo_size': (150, 150),
            'logo_position': 'center'
        }
        
        # Update with user config
        if template_config:
            config.update(template_config)
        
        # Create base template
        img = create_intro_card_template(
            config['width'], config['height'],
            config['background_color'], config.get('gradient_colors')
        )
        
        # Add logo at top if provided
        if logo_path and os.path.exists(logo_path):
            img = add_logo_to_card(
                img, logo_path, 'center',
                config['logo_size'], margin=100
            )
        
        # Add title
        img = add_text_to_card(
            img, title, "top",
            config['title_font_size'], config['title_color']
        )
        
        # Add social handles
        if social_handles:
            social_text_lines = []
            for platform, handle in social_handles.items():
                if handle:
                    social_text_lines.append(f"{platform.title()}: {handle}")
            
            if social_text_lines:
                social_text = "\n".join(social_text_lines)
                img = add_text_to_card(
                    img, social_text, "center",
                    config['social_font_size'], config['social_color']
                )
        
        # Add call-to-action
        if call_to_action:
            img = add_text_to_card(
                img, call_to_action, "bottom",
                config['cta_font_size'], config['cta_color']
            )
        
        # Save image
        img.save(output_path, 'PNG', quality=95)
        return os.path.exists(output_path)
        
    except Exception as e:
        print(f"Error creating outro card: {e}")
        return False


def create_outro_video_from_card(card_path: str, output_path: str,
                                 duration: float = 5.0, transition_type: str = "fade") -> bool:
    """Convert outro card image to video with animation.
    
    Args:
        card_path: Path to outro card image
        output_path: Output video path
        duration: Duration in seconds
        transition_type: Animation type ("fade", "slide", "zoom")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(card_path):
            print(f"Outro card not found: {card_path}")
            return False
        
        # Build filter based on transition type
        if transition_type == "fade":
            # Fade in and hold
            filter_complex = f"fade=t=in:st=0:d=0.5"
        elif transition_type == "slide":
            # Slide in from right
            filter_complex = f"crop=1920:1080:1920-1920*min(t/{duration}\,1):0"
        elif transition_type == "zoom":
            # Zoom out effect
            filter_complex = f"scale=1920*min(1.2\,1+0.2*t/{duration}):1080*min(1.2\,1+0.2*t/{duration}),crop=1920:1080"
        else:
            # No animation
            filter_complex = "scale=1920:1080"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-loop", "1",
            "-i", card_path,
            "-vf", filter_complex,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating outro video: {e}")
        return False


def add_outro_to_video(main_video: str, outro_config: Dict, output_path: str,
                      temp_dir: str = "temp_outro") -> bool:
    """Add outro card to the end of a video.
    
    Args:
        main_video: Path to main video file
        outro_config: Configuration for outro card
        output_path: Output video path
        temp_dir: Temporary directory for outro files
    
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create outro card image
        card_path = os.path.join(temp_dir, "outro_card.png")
        card_created = create_outro_card(
            outro_config.get('title', 'Thanks for Watching!'),
            outro_config.get('social_handles', {}),
            outro_config.get('call_to_action', 'Subscribe for more content'),
            outro_config.get('logo_path'),
            outro_config.get('template_config'),
            card_path
        )
        
        if not card_created:
            print("Failed to create outro card")
            shutil.copy(main_video, output_path)
            return True
        
        # Create outro video
        outro_video_path = os.path.join(temp_dir, "outro_video.mp4")
        outro_duration = outro_config.get('duration', 5.0)
        transition_type = outro_config.get('transition', 'fade')
        
        outro_created = create_outro_video_from_card(
            card_path, outro_video_path, outro_duration, transition_type
        )
        
        if not outro_created:
            print("Failed to create outro video")
            shutil.copy(main_video, output_path)
            return True
        
        # Concatenate main video with outro
        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, 'w') as f:
            f.write(f"file '{os.path.abspath(main_video)}'\n")
            f.write(f"file '{os.path.abspath(outro_video_path)}'\n")
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        
        run(cmd, check=True)
        success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
        # Cleanup temporary files
        try:
            for file_path in [card_path, outro_video_path, concat_list_path]:
                if os.path.exists(file_path):
                    os.remove(file_path)
        except:
            pass
        
        return success
        
    except Exception as e:
        print(f"Error adding outro to video: {e}")
        # Fallback: copy original video
        try:
            shutil.copy(main_video, output_path)
            return True
        except:
            return False


# =========================
# Video Transitions System
# =========================

def apply_fade_transition(input_video: str, output_video: str, 
                         fade_in_duration: float = 1.0, fade_out_duration: float = 1.0,
                         fade_color: str = "black") -> bool:
    """Apply fade in/out transitions to a video.
    
    Args:
        input_video: Path to input video
        output_video: Path to output video
        fade_in_duration: Fade in duration in seconds
        fade_out_duration: Fade out duration in seconds
        fade_color: Fade color (black, white, etc.)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get video duration
        duration = ffprobe_duration(input_video)
        if duration <= 0:
            return False
        
        # Build fade filter
        fade_out_start = max(0, duration - fade_out_duration)
        
        filter_complex = f"fade=t=in:st=0:d={fade_in_duration}:c={fade_color}"
        if fade_out_duration > 0 and fade_out_start > fade_in_duration:
            filter_complex += f",fade=t=out:st={fade_out_start}:d={fade_out_duration}:c={fade_color}"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", input_video,
            "-vf", filter_complex,
            "-c:a", "copy",
            output_video
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0
        
    except Exception as e:
        print(f"Error applying fade transition: {e}")
        return False


def create_cross_dissolve_transition(video1: str, video2: str, output_video: str,
                                    transition_duration: float = 2.0,
                                    overlap_position: str = "end") -> bool:
    """Create a cross dissolve transition between two videos.
    
    Args:
        video1: Path to first video
        video2: Path to second video
        output_video: Path to output video
        transition_duration: Duration of cross dissolve in seconds
        overlap_position: Where to place transition ("end", "middle")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get video durations
        duration1 = ffprobe_duration(video1)
        duration2 = ffprobe_duration(video2)
        
        if duration1 <= 0 or duration2 <= 0:
            return False
        
        # Calculate transition timing
        if overlap_position == "end":
            # Transition at the end of video1
            video1_end = duration1 - transition_duration
            video2_start = 0
        else:  # middle
            # Transition in the middle
            video1_end = duration1 - (transition_duration / 2)
            video2_start = transition_duration / 2
        
        # Ensure valid timing
        video1_end = max(0, video1_end)
        transition_duration = min(transition_duration, duration1, duration2)
        
        filter_complex = f"""
        [0:v]trim=0:{video1_end},setpts=PTS-STARTPTS[v1_main];
        [0:v]trim={video1_end}:{duration1},setpts=PTS-STARTPTS,
             fade=t=out:st=0:d={transition_duration}[v1_fade];
        [1:v]trim={video2_start}:{video2_start + transition_duration},setpts=PTS-STARTPTS,
             fade=t=in:st=0:d={transition_duration}[v2_fade];
        [1:v]trim={video2_start + transition_duration}:{duration2},setpts=PTS-STARTPTS[v2_main];
        [v1_fade][v2_fade]overlay[transition];
        [v1_main][transition][v2_main]concat=n=3:v=1:a=0[outv]
        """
        
        # Handle audio separately
        audio_filter = f"""
        [0:a]atrim=0:{video1_end}[a1_main];
        [0:a]atrim={video1_end}:{duration1},afade=t=out:st=0:d={transition_duration}[a1_fade];
        [1:a]atrim={video2_start}:{video2_start + transition_duration},afade=t=in:st=0:d={transition_duration}[a2_fade];
        [1:a]atrim={video2_start + transition_duration}:{duration2}[a2_main];
        [a1_fade][a2_fade]amix=inputs=2[a_transition];
        [a1_main][a_transition][a2_main]concat=n=3:v=0:a=1[outa]
        """
        
        full_filter = filter_complex + ";" + audio_filter
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", video1,
            "-i", video2,
            "-filter_complex", full_filter,
            "-map", "[outv]",
            "-map", "[outa]",
            output_video
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0
        
    except Exception as e:
        print(f"Error creating cross dissolve transition: {e}")
        return False


def create_slide_transition(video1: str, video2: str, output_video: str,
                           transition_duration: float = 1.5,
                           direction: str = "left") -> bool:
    """Create a slide transition between two videos.
    
    Args:
        video1: Path to first video
        video2: Path to second video
        output_video: Path to output video
        transition_duration: Duration of slide transition in seconds
        direction: Slide direction ("left", "right", "up", "down")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get video durations
        duration1 = ffprobe_duration(video1)
        duration2 = ffprobe_duration(video2)
        
        if duration1 <= 0 or duration2 <= 0:
            return False
        
        # Calculate transition timing
        video1_end = duration1 - transition_duration
        video1_end = max(0, video1_end)
        
        # Define slide directions
        if direction == "left":
            # Video2 slides in from right
            overlay_expr = f"x=W-W*min(t/{transition_duration}\,1):y=0"
        elif direction == "right":
            # Video2 slides in from left
            overlay_expr = f"x=-W+W*min(t/{transition_duration}\,1):y=0"
        elif direction == "up":
            # Video2 slides in from bottom
            overlay_expr = f"x=0:y=H-H*min(t/{transition_duration}\,1)"
        else:  # down
            # Video2 slides in from top
            overlay_expr = f"x=0:y=-H+H*min(t/{transition_duration}\,1)"
        
        filter_complex = f"""
        [0:v]trim=0:{video1_end},setpts=PTS-STARTPTS[v1_main];
        [0:v]trim={video1_end}:{duration1},setpts=PTS-STARTPTS[v1_transition];
        [1:v]trim=0:{transition_duration},setpts=PTS-STARTPTS[v2_transition];
        [1:v]trim={transition_duration}:{duration2},setpts=PTS-STARTPTS[v2_main];
        [v1_transition][v2_transition]overlay={overlay_expr}[transition];
        [v1_main][transition][v2_main]concat=n=3:v=1:a=0[outv]
        """
        
        # Handle audio with crossfade
        audio_filter = f"""
        [0:a]atrim=0:{video1_end}[a1_main];
        [0:a]atrim={video1_end}:{duration1},afade=t=out:st=0:d={transition_duration}[a1_fade];
        [1:a]atrim=0:{transition_duration},afade=t=in:st=0:d={transition_duration}[a2_fade];
        [1:a]atrim={transition_duration}:{duration2}[a2_main];
        [a1_fade][a2_fade]amix=inputs=2[a_transition];
        [a1_main][a_transition][a2_main]concat=n=3:v=0:a=1[outa]
        """
        
        full_filter = filter_complex + ";" + audio_filter
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", video1,
            "-i", video2,
            "-filter_complex", full_filter,
            "-map", "[outv]",
            "-map", "[outa]",
            output_video
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0
        
    except Exception as e:
        print(f"Error creating slide transition: {e}")
        return False


def create_wipe_transition(video1: str, video2: str, output_video: str,
                          transition_duration: float = 1.5,
                          wipe_type: str = "horizontal") -> bool:
    """Create a wipe transition between two videos.
    
    Args:
        video1: Path to first video
        video2: Path to second video
        output_video: Path to output video
        transition_duration: Duration of wipe transition in seconds
        wipe_type: Wipe type ("horizontal", "vertical", "diagonal")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get video durations
        duration1 = ffprobe_duration(video1)
        duration2 = ffprobe_duration(video2)
        
        if duration1 <= 0 or duration2 <= 0:
            return False
        
        # Calculate transition timing
        video1_end = duration1 - transition_duration
        video1_end = max(0, video1_end)
        
        # Define wipe patterns
        if wipe_type == "horizontal":
            # Horizontal wipe from left to right
            wipe_expr = f"crop=W*min(t/{transition_duration}\,1):H:0:0"
        elif wipe_type == "vertical":
            # Vertical wipe from top to bottom
            wipe_expr = f"crop=W:H*min(t/{transition_duration}\,1):0:0"
        else:  # diagonal
            # Diagonal wipe
            wipe_expr = f"crop=W*min(t/{transition_duration}\,1):H*min(t/{transition_duration}\,1):0:0"
        
        filter_complex = f"""
        [0:v]trim=0:{video1_end},setpts=PTS-STARTPTS[v1_main];
        [0:v]trim={video1_end}:{duration1},setpts=PTS-STARTPTS[v1_bg];
        [1:v]trim=0:{transition_duration},setpts=PTS-STARTPTS,{wipe_expr}[v2_wipe];
        [1:v]trim={transition_duration}:{duration2},setpts=PTS-STARTPTS[v2_main];
        [v1_bg][v2_wipe]overlay[transition];
        [v1_main][transition][v2_main]concat=n=3:v=1:a=0[outv]
        """
        
        # Handle audio with crossfade
        audio_filter = f"""
        [0:a]atrim=0:{video1_end}[a1_main];
        [0:a]atrim={video1_end}:{duration1},afade=t=out:st=0:d={transition_duration}[a1_fade];
        [1:a]atrim=0:{transition_duration},afade=t=in:st=0:d={transition_duration}[a2_fade];
        [1:a]atrim={transition_duration}:{duration2}[a2_main];
        [a1_fade][a2_fade]amix=inputs=2[a_transition];
        [a1_main][a_transition][a2_main]concat=n=3:v=0:a=1[outa]
        """
        
        full_filter = filter_complex + ";" + audio_filter
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", video1,
            "-i", video2,
            "-filter_complex", full_filter,
            "-map", "[outv]",
            "-map", "[outa]",
            output_video
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0
        
    except Exception as e:
        print(f"Error creating wipe transition: {e}")
        return False


def apply_transitions_to_video_segments(video_segments: List[str], output_video: str,
                                      transition_configs: List[Dict] = None,
                                      temp_dir: str = "temp_transitions") -> bool:
    """Apply transitions between multiple video segments.
    
    Args:
        video_segments: List of video file paths
        output_video: Path to output video
        transition_configs: List of transition configurations
        temp_dir: Temporary directory for processing
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if len(video_segments) < 2:
            # No transitions needed for single video
            if len(video_segments) == 1:
                shutil.copy(video_segments[0], output_video)
                return True
            return False
        
        os.makedirs(temp_dir, exist_ok=True)
        
        # Default transition config
        default_config = {
            'type': 'fade',
            'duration': 1.0,
            'direction': 'left',
            'wipe_type': 'horizontal'
        }
        
        current_video = video_segments[0]
        
        # Apply transitions between consecutive segments
        for i in range(1, len(video_segments)):
            next_video = video_segments[i]
            temp_output = os.path.join(temp_dir, f"transition_{i}.mp4")
            
            # Get transition config
            if transition_configs and i-1 < len(transition_configs):
                config = {**default_config, **transition_configs[i-1]}
            else:
                config = default_config
            
            # Apply appropriate transition
            transition_type = config.get('type', 'fade')
            duration = config.get('duration', 1.0)
            
            success = False
            if transition_type == 'cross_dissolve':
                success = create_cross_dissolve_transition(
                    current_video, next_video, temp_output, duration
                )
            elif transition_type == 'slide':
                direction = config.get('direction', 'left')
                success = create_slide_transition(
                    current_video, next_video, temp_output, duration, direction
                )
            elif transition_type == 'wipe':
                wipe_type = config.get('wipe_type', 'horizontal')
                success = create_wipe_transition(
                    current_video, next_video, temp_output, duration, wipe_type
                )
            else:  # fade or fallback
                # For fade, just concatenate with fade effects on individual videos
                fade_out_video = os.path.join(temp_dir, f"fade_out_{i}.mp4")
                fade_in_video = os.path.join(temp_dir, f"fade_in_{i}.mp4")
                
                # Apply fade out to current video
                apply_fade_transition(current_video, fade_out_video, 0, duration)
                # Apply fade in to next video
                apply_fade_transition(next_video, fade_in_video, duration, 0)
                
                # Simple concatenation
                concat_list_path = os.path.join(temp_dir, f"concat_{i}.txt")
                with open(concat_list_path, 'w') as f:
                    f.write(f"file '{os.path.abspath(fade_out_video)}'\n")
                    f.write(f"file '{os.path.abspath(fade_in_video)}'\n")
                
                cmd = [
                    "ffmpeg", "-hide_banner", "-nostats", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list_path,
                    "-c", "copy",
                    temp_output
                ]
                
                run(cmd, check=True)
                success = os.path.exists(temp_output) and os.path.getsize(temp_output) > 0
            
            if not success:
                print(f"Failed to create transition {i}, falling back to concatenation")
                # Fallback: simple concatenation
                concat_list_path = os.path.join(temp_dir, f"fallback_{i}.txt")
                with open(concat_list_path, 'w') as f:
                    f.write(f"file '{os.path.abspath(current_video)}'\n")
                    f.write(f"file '{os.path.abspath(next_video)}'\n")
                
                cmd = [
                    "ffmpeg", "-hide_banner", "-nostats", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list_path,
                    "-c", "copy",
                    temp_output
                ]
                
                run(cmd, check=True)
            
            current_video = temp_output
        
        # Copy final result
        shutil.copy(current_video, output_video)
        
        # Cleanup temporary files
        try:
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        except:
            pass
        
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0
        
    except Exception as e:
        print(f"Error applying transitions to video segments: {e}")
        return False


# =========================
# Lightweight Animations System
# =========================

def create_animated_lower_third(text: str, subtitle: str = "", output_path: str = "lower_third.mp4",
                               duration: float = 5.0, width: int = 1920, height: int = 1080,
                               animation_type: str = "slide_in") -> bool:
    """Create an animated lower third graphic.
    
    Args:
        text: Main text (e.g., speaker name)
        subtitle: Subtitle text (e.g., title/role)
        output_path: Output video path
        duration: Duration in seconds
        width: Video width
        height: Video height
        animation_type: Animation type ("slide_in", "fade_in", "typewriter")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create transparent background
        bg_color = "#00000000"  # Transparent
        
        # Define lower third positioning
        lt_height = height // 6  # Lower third takes 1/6 of screen height
        lt_y = height - lt_height - 50  # Position near bottom with margin
        
        # Text styling
        main_font_size = 48
        sub_font_size = 32
        text_color = "white"
        bg_bar_color = "#1a1a2e"
        accent_color = "#00d4ff"
        
        if animation_type == "slide_in":
            # Slide in from left
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [bg]drawbox=x=max(0\,min({width}\,{width}*t/{duration}-{width})):y={lt_y}:w={width//2}:h={lt_height}:color={bg_bar_color}:t=fill[bg_with_bar];
            [bg_with_bar]drawbox=x=max(0\,min({width}\,{width}*t/{duration}-{width})):y={lt_y}:w=5:h={lt_height}:color={accent_color}:t=fill[bg_with_accent];
            [bg_with_accent]drawtext=text='{text}':fontsize={main_font_size}:fontcolor={text_color}:x=max(-{width}\,{width}*t/{duration}-{width}+20):y={lt_y+10}:enable='gte(t,0.2)'[with_main_text];
            [with_main_text]drawtext=text='{subtitle}':fontsize={sub_font_size}:fontcolor={text_color}:x=max(-{width}\,{width}*t/{duration}-{width}+20):y={lt_y+main_font_size+15}:enable='gte(t,0.4)'[out]
            """
        elif animation_type == "fade_in":
            # Fade in effect
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [bg]drawbox=x=50:y={lt_y}:w={width//2}:h={lt_height}:color={bg_bar_color}:t=fill:enable='gte(t,0)'[bg_with_bar];
            [bg_with_bar]drawbox=x=50:y={lt_y}:w=5:h={lt_height}:color={accent_color}:t=fill:enable='gte(t,0)'[bg_with_accent];
            [bg_with_accent]drawtext=text='{text}':fontsize={main_font_size}:fontcolor={text_color}:x=70:y={lt_y+10}:alpha='min(1\,t/0.5)':enable='gte(t,0.2)'[with_main_text];
            [with_main_text]drawtext=text='{subtitle}':fontsize={sub_font_size}:fontcolor={text_color}:x=70:y={lt_y+main_font_size+15}:alpha='min(1\,t/0.8)':enable='gte(t,0.4)'[out]
            """
        else:  # typewriter
            # Typewriter effect (simplified)
            char_count = len(text)
            chars_per_sec = max(1, char_count / 2)  # Type over 2 seconds
            
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [bg]drawbox=x=50:y={lt_y}:w={width//2}:h={lt_height}:color={bg_bar_color}:t=fill[bg_with_bar];
            [bg_with_bar]drawbox=x=50:y={lt_y}:w=5:h={lt_height}:color={accent_color}:t=fill[bg_with_accent];
            [bg_with_accent]drawtext=text='{text}':fontsize={main_font_size}:fontcolor={text_color}:x=70:y={lt_y+10}:enable='gte(t,0.2)'[with_main_text];
            [with_main_text]drawtext=text='{subtitle}':fontsize={sub_font_size}:fontcolor={text_color}:x=70:y={lt_y+main_font_size+15}:enable='gte(t,1.0)'[out]
            """
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "lavfi",
            "-i", f"color=c={bg_color}:s={width}x{height}:d={duration}",
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264",
            "-pix_fmt", "yuva420p",  # Support transparency
            "-t", str(duration),
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating animated lower third: {e}")
        return False


def create_logo_reveal_animation(logo_path: str, output_path: str = "logo_reveal.mp4",
                                duration: float = 3.0, width: int = 1920, height: int = 1080,
                                animation_type: str = "zoom_in") -> bool:
    """Create an animated logo reveal.
    
    Args:
        logo_path: Path to logo image
        output_path: Output video path
        duration: Duration in seconds
        width: Video width
        height: Video height
        animation_type: Animation type ("zoom_in", "fade_in", "slide_in")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(logo_path):
            print(f"Logo file not found: {logo_path}")
            return False
        
        # Create transparent background
        bg_color = "#00000000"
        
        # Logo positioning (center)
        logo_size = min(width, height) // 3  # Logo takes 1/3 of smaller dimension
        
        if animation_type == "zoom_in":
            # Zoom in from small to normal size
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [1:v]scale={logo_size}:{logo_size}:force_original_aspect_ratio=decrease[logo_sized];
            [logo_sized]scale='iw*min(1,max(0.1,(t-0.5)/1.5))':'ih*min(1,max(0.1,(t-0.5)/1.5))'[logo_scaled];
            [bg][logo_scaled]overlay=(W-w)/2:(H-h)/2:enable='gte(t,0.5)'[out]
            """
        elif animation_type == "fade_in":
            # Fade in effect
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [1:v]scale={logo_size}:{logo_size}:force_original_aspect_ratio=decrease[logo_sized];
            [logo_sized]format=rgba,colorchannelmixer=aa='min(1,max(0,(t-0.5)/1.0))'[logo_faded];
            [bg][logo_faded]overlay=(W-w)/2:(H-h)/2:enable='gte(t,0.5)'[out]
            """
        else:  # slide_in
            # Slide in from top
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [1:v]scale={logo_size}:{logo_size}:force_original_aspect_ratio=decrease[logo_sized];
            [bg][logo_sized]overlay=(W-w)/2:'max(-h,(H-h)/2-h+h*min(1,(t-0.5)/1.0))':enable='gte(t,0.5)'[out]
            """
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "lavfi",
            "-i", f"color=c={bg_color}:s={width}x{height}:d={duration}",
            "-i", logo_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264",
            "-pix_fmt", "yuva420p",
            "-t", str(duration),
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating logo reveal animation: {e}")
        return False


def create_karaoke_style_subtitles(subtitle_data: List[Dict], output_path: str = "karaoke_subs.mp4",
                                  width: int = 1920, height: int = 1080,
                                  font_size: int = 48, highlight_color: str = "#ffaa00") -> bool:
    """Create karaoke-style animated subtitles.
    
    Args:
        subtitle_data: List of subtitle dicts with 'text', 'start', 'end', 'words' (optional)
        output_path: Output video path
        width: Video width
        height: Video height
        font_size: Font size
        highlight_color: Color for highlighted words
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not subtitle_data:
            return False
        
        # Calculate total duration
        total_duration = max(sub['end'] for sub in subtitle_data)
        
        # Create transparent background
        bg_color = "#00000000"
        text_color = "white"
        
        # Build complex filter for animated subtitles
        filter_parts = [f"color=c={bg_color}:s={width}x{height}:d={total_duration}[bg]"]
        
        current_input = "[bg]"
        output_count = 0
        
        for i, sub in enumerate(subtitle_data):
            start_time = sub['start']
            end_time = sub['end']
            text = sub['text'].replace("'", "\\'").replace(":", "\\:")
            
            # Position subtitles at bottom
            y_pos = height - 150
            
            # Basic subtitle with fade in/out
            fade_duration = 0.3
            
            # Create fade in/out alpha expression
            alpha_expr = f"if(lt(t,{start_time}),0,if(lt(t,{start_time + fade_duration}),(t-{start_time})/{fade_duration},if(lt(t,{end_time - fade_duration}),1,max(0,({end_time}-t)/{fade_duration}))))"
            
            filter_parts.append(
                f"{current_input}drawtext=text='{text}':fontsize={font_size}:fontcolor={text_color}:"
                f"x=(w-text_w)/2:y={y_pos}:alpha='{alpha_expr}':enable='between(t,{start_time},{end_time})'[sub{i}]"
            )
            
            current_input = f"[sub{i}]"
            output_count += 1
        
        # Final output
        filter_complex = ";".join(filter_parts)
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "lavfi",
            "-i", f"color=c={bg_color}:s={width}x{height}:d={total_duration}",
            "-filter_complex", filter_complex,
            "-map", current_input,
            "-c:v", "libx264",
            "-pix_fmt", "yuva420p",
            "-t", str(total_duration),
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating karaoke-style subtitles: {e}")
        return False


def overlay_animation_on_video(base_video: str, animation_video: str, output_video: str,
                              position: str = "overlay", blend_mode: str = "normal") -> bool:
    """Overlay an animation on top of a base video.
    
    Args:
        base_video: Path to base video
        animation_video: Path to animation video (with transparency)
        output_video: Path to output video
        position: Overlay position ("overlay", "lower_third", "top")
        blend_mode: Blend mode ("normal", "multiply", "screen")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(base_video) or not os.path.exists(animation_video):
            return False
        
        # Get video dimensions and duration
        base_duration = ffprobe_duration(base_video)
        anim_duration = ffprobe_duration(animation_video)
        
        if base_duration <= 0 or anim_duration <= 0:
            return False
        
        # Position calculations
        if position == "lower_third":
            overlay_expr = "overlay=0:H-h"
        elif position == "top":
            overlay_expr = "overlay=0:0"
        else:  # overlay (center or default)
            overlay_expr = "overlay=(W-w)/2:(H-h)/2"
        
        # Handle different blend modes
        if blend_mode == "multiply":
            blend_filter = ",blend=all_mode=multiply"
        elif blend_mode == "screen":
            blend_filter = ",blend=all_mode=screen"
        else:
            blend_filter = ""  # Normal overlay
        
        # Loop animation if it's shorter than base video
        if anim_duration < base_duration:
            loop_count = int(base_duration / anim_duration) + 1
            animation_filter = f"[1:v]loop={loop_count}:size=1:start=0[anim_looped];"
            animation_input = "[anim_looped]"
        else:
            animation_filter = ""
            animation_input = "[1:v]"
        
        filter_complex = f"{animation_filter}[0:v]{animation_input}{overlay_expr}{blend_filter}[outv]"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", base_video,
            "-i", animation_video,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "0:a?",  # Copy audio from base video if available
            "-c:a", "copy",
            "-t", str(base_duration),
            output_video
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_video) and os.path.getsize(output_video) > 0
        
    except Exception as e:
        print(f"Error overlaying animation on video: {e}")
        return False


def create_text_animation(text: str, output_path: str = "text_animation.mp4",
                         duration: float = 3.0, width: int = 1920, height: int = 1080,
                         animation_type: str = "typewriter", font_size: int = 72) -> bool:
    """Create animated text effects.
    
    Args:
        text: Text to animate
        output_path: Output video path
        duration: Duration in seconds
        width: Video width
        height: Video height
        animation_type: Animation type ("typewriter", "fade_in", "slide_up", "bounce")
        font_size: Font size
    
    Returns:
        True if successful, False otherwise
    """
    try:
        bg_color = "#00000000"  # Transparent
        text_color = "white"
        
        # Escape special characters
        escaped_text = text.replace("'", "\\'").replace(":", "\\:")
        
        if animation_type == "typewriter":
            # Typewriter effect using text expansion
            char_count = len(text)
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [bg]drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor={text_color}:
            x=(w-text_w)/2:y=(h-text_h)/2:enable='gte(t,0)'[out]
            """
        elif animation_type == "fade_in":
            # Fade in effect
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [bg]drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor={text_color}:
            x=(w-text_w)/2:y=(h-text_h)/2:alpha='min(1,t/1.5)'[out]
            """
        elif animation_type == "slide_up":
            # Slide up from bottom
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [bg]drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor={text_color}:
            x=(w-text_w)/2:y='h-text_h*(t/1.5)':enable='gte(t,0)'[out]
            """
        else:  # bounce
            # Bounce effect
            filter_complex = f"""
            color=c={bg_color}:s={width}x{height}:d={duration}[bg];
            [bg]drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor={text_color}:
            x=(w-text_w)/2:y='(h-text_h)/2-20*sin(2*PI*t)':enable='gte(t,0)'[out]
            """
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "lavfi",
            "-i", f"color=c={bg_color}:s={width}x{height}:d={duration}",
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264",
            "-pix_fmt", "yuva420p",
            "-t", str(duration),
            output_path
        ]
        
        run(cmd, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error creating text animation: {e}")
        return False


# =========================
# Audio/Scene analysis helpers (from original)
# =========================

def detect_silences(path: str, silence_threshold_db: float = -40.0, min_silence_ms: int = 600) -> List[Tuple[float, float]]:
    """Enhanced silence detection with configurable parameters."""
    args = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
        f"silencedetect=noise={silence_threshold_db}dB:duration={min_silence_ms/1000.0}",
        "-f", "null", "-"
    ]
    p = run(args, check=True)
    silences: List[Tuple[float, float]] = []
    start: Optional[float] = None
    for line in (p.stderr or "").splitlines():
        if "silence_start:" in line:
            try:
                start = float(line.split("silence_start:")[-1].strip())
            except Exception:
                start = None
        if "silence_end:" in line and start is not None:
            try:
                end_part = line.split("silence_end:")[-1]
                end = float(end_part.split("|")[0].strip())
                silences.append((start, end))
                start = None
            except Exception:
                pass
    return silences


def detect_introduction_segment(video_path: str, max_intro_duration: float = 30.0, min_intro_duration: float = 30.0) -> Tuple[float, float]:
    """Detect introduction segment by analyzing voice activity and visual content.
    Note: This doesn't require a specific "intro clip" - it works by analyzing
    the natural patterns in voice activity and visual changes at the beginning of the video.
    
    Args:
        video_path: Path to the video file
        max_intro_duration: Maximum expected introduction duration in seconds
        min_intro_duration: Minimum introduction duration to preserve in seconds
    
    Returns:
        Tuple of (start_time, end_time) for the introduction segment
    """
    try:
        # Get video duration to ensure we don't exceed it
        video_duration = ffprobe_duration(video_path)
        if video_duration <= 0:
            return (0.0, min(min_intro_duration, 30.0))
        
        # Analyze voice activity in the first portion of the video
        analysis_duration = min(max_intro_duration * 1.5, video_duration)  # Analyze a bit more than max
        voice_segments = analyze_voice_activity(video_path, analysis_duration)
        
        # Analyze visual content changes
        visual_changes = analyze_visual_content_changes(video_path, analysis_duration)
        
        # Determine introduction end based on voice and visual analysis
        intro_end = 0.0
        
        # If there's consistent voice activity, use that as a guide
        if voice_segments:
            # Find the first significant gap in voice activity
            for i, (start, end) in enumerate(voice_segments):
                if i > 0:
                    prev_end = voice_segments[i-1][1]
                    gap = start - prev_end
                    if gap > 2.0:  # 2 second gap indicates potential intro end
                        intro_end = prev_end
                        break
            
            # If no significant gap found, use the end of voice activity
            if intro_end == 0.0 and voice_segments:
                intro_end = min(voice_segments[-1][1], max_intro_duration)
        
        # Combine with visual analysis
        if visual_changes and intro_end > 0:
            # Look for visual changes near the voice-detected intro end
            for change_time in visual_changes:
                if abs(change_time - intro_end) < 3.0:  # Within 3 seconds
                    intro_end = change_time
                    break
        
        # Ensure we preserve at least the minimum intro duration
        if intro_end < min_intro_duration:
            intro_end = min(min_intro_duration, video_duration)
        
        # Ensure we don't exceed max intro duration or video duration
        intro_end = min(intro_end, max_intro_duration, video_duration)
        
        return (0.0, intro_end)
    
    except Exception as e:
        print(f"Error detecting introduction: {e}")
        # Fallback: preserve at least min_intro_duration or 30 seconds
        fallback_duration = min(min_intro_duration, 30.0)
        try:
            video_duration = ffprobe_duration(video_path)
            if video_duration > 0:
                fallback_duration = min(fallback_duration, video_duration)
        except:
            pass
        return (0.0, fallback_duration)


def analyze_voice_activity(video_path: str, duration: float) -> List[Tuple[float, float]]:
    """Analyze voice activity in the video to detect speech segments.
    
    Args:
        video_path: Path to the video file
        duration: Duration to analyze in seconds
    
    Returns:
        List of (start_time, end_time) tuples for voice activity segments
    """
    try:
        # Use FFmpeg to detect voice activity with lower threshold for speech
        args = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", video_path,
            "-t", str(duration),
            "-af", "silencedetect=noise=-35dB:duration=0.5",
            "-f", "null", "-"
        ]
        
        p = run(args, check=True)
        
        # Parse silence detection output to find voice segments
        silences = []
        start = None
        
        for line in (p.stderr or "").splitlines():
            if "silence_start:" in line:
                try:
                    start = float(line.split("silence_start:")[-1].strip())
                except Exception:
                    start = None
            elif "silence_end:" in line and start is not None:
                try:
                    end_part = line.split("silence_end:")[-1]
                    end = float(end_part.split("|")[0].strip())
                    silences.append((start, end))
                    start = None
                except Exception:
                    pass
        
        # Convert silences to voice activity segments
        voice_segments = []
        last_end = 0.0
        
        for silence_start, silence_end in silences:
            if silence_start > last_end:
                voice_segments.append((last_end, silence_start))
            last_end = silence_end
        
        # Add final segment if there's voice activity at the end
        if last_end < duration:
            voice_segments.append((last_end, duration))
        
        return voice_segments
    
    except Exception as e:
        print(f"Error analyzing voice activity: {e}")
        return [(0.0, duration)]  # Assume continuous voice activity


def analyze_visual_content_changes(video_path: str, duration: float) -> List[float]:
    """Analyze visual content changes to detect scene transitions.
    
    Args:
        video_path: Path to the video file
        duration: Duration to analyze in seconds
    
    Returns:
        List of timestamps where significant visual changes occur
    """
    try:
        # Use FFmpeg scene detection to find visual changes
        args = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", video_path,
            "-t", str(duration),
            "-vf", "select='gt(scene,0.3)',showinfo",
            "-f", "null", "-"
        ]
        
        p = run(args, check=True)
        
        # Parse scene detection output
        scene_changes = []
        
        for line in (p.stderr or "").splitlines():
            if "pts_time:" in line:
                try:
                    # Extract timestamp from showinfo output
                    pts_time = line.split("pts_time:")[1].split()[0]
                    timestamp = float(pts_time)
                    if timestamp <= duration:
                        scene_changes.append(timestamp)
                except Exception:
                    pass
        
        return sorted(scene_changes)
    
    except Exception as e:
        print(f"Error analyzing visual content: {e}")
        return []  # No scene changes detected


def trim_long_silences(input_path: str, output_path: str, 
                      silence_threshold_db: float = -40.0, 
                      min_silence_ms: int = 1000,
                      max_silence_keep_ms: int = 500) -> bool:
    """Remove long silent gaps, keeping only short pauses for natural flow.
    
    Args:
        input_path: Input video file path
        output_path: Output video file path
        silence_threshold_db: Silence detection threshold in dB
        min_silence_ms: Minimum silence duration to detect (ms)
        max_silence_keep_ms: Maximum silence duration to keep (ms)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Detect introduction segment to preserve it
        intro_start, intro_end = detect_introduction_segment(input_path, max_intro_duration=60.0, min_intro_duration=30.0)
        
        # Detect silences
        silences = detect_silences(input_path, silence_threshold_db, min_silence_ms)
        
        # Filter out silences that occur within the introduction segment
        # This preserves the intro regardless of whether it contains a specific "intro clip"
        # The intro is detected based on voice activity and visual content analysis
        filtered_silences = []
        for start, end in silences:
            # Skip silences that overlap with the introduction
            if end <= intro_start or start >= intro_end:
                filtered_silences.append((start, end))
            # Note: The condition 'start >= intro_end' is already covered in the previous if statement
        
        if not filtered_silences:
            # No long silences found outside introduction, just copy the file
            shutil.copy(input_path, output_path)
            return True
        
        # Get video duration
        total_duration = ffprobe_duration(input_path)
        if total_duration <= 0:
            return False
        
        # Build filter to remove long silences
        max_keep_seconds = max_silence_keep_ms / 1000.0
        filter_parts = []
        
        for start, end in silences:
            silence_duration = end - start
            if silence_duration > max_keep_seconds:
                # Trim this silence to max_keep_seconds
                new_end = start + max_keep_seconds
                filter_parts.append(f"between(t,{start},{new_end})")
            else:
                # Keep this silence as is
                filter_parts.append(f"between(t,{start},{end})")
        
        if filter_parts:
            # Create filter to remove long silences
            silence_filter = "+".join(filter_parts)
            af = f"silenceremove=stop_periods=-1:stop_duration={max_keep_seconds}:stop_threshold={silence_threshold_db}dB"
            
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-y",
                "-i", input_path,
                "-af", af,
                "-c:v", "copy",
                "-movflags", "+faststart",
                output_path
            ]
            
            run(cmd, check=True)
        else:
            # No silences to trim, copy file
            shutil.copy(input_path, output_path)
        
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    except Exception as e:
        print(f"Error trimming silences: {e}")
        # Fallback: copy original file
        try:
            shutil.copy(input_path, output_path)
            return True
        except:
            return False

def invert_intervals(silences: List[Tuple[float, float]], total: float, keep_margin: float = 0.05) -> List[Tuple[float, float]]:
    if total <= 0:
        return []
    if not silences:
        return [(0.0, total)]
    segs: List[Tuple[float, float]] = []
    cursor = 0.0
    for s, e in silences:
        if s > cursor:
            segs.append((max(0.0, cursor - keep_margin), min(s + keep_margin, total)))
        cursor = e
    if cursor < total:
        segs.append((max(0.0, cursor - keep_margin), total))
    merged: List[List[float]] = []
    for a, b in segs:
        if not merged or a > merged[-1][1]:
            merged.append([a, b])
        else:
            merged[-1][1] = max(merged[-1][1], b)
    return [(float(a), float(b)) for a, b in merged]

def detect_scene_scores(path: str) -> List[Tuple[float, float]]:
    if not os.path.exists(path):
        print(f"[WARN] Scene detection: file does not exist: {path}")
        return []
    vf = "select=gt(scene\\,0.0),metadata=print"
    try:
        p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf", vf, "-f", "null", "-"], check=True)
    except Exception as e:
        print(f"[WARN] Scene detection failed for {path}: {e}")
        return []
    scores: List[Tuple[float, float]] = []
    for line in (p.stderr or "").splitlines():
        if "pts_time" in line and "lavfi.scene=" in line:
            try:
                m1 = re.search(r"pts_time:(\d+(?:\.\d+)?)", line)
                m2 = re.search(r"lavfi\.scene=(\d+(?:\.\d+)?)", line)
                if m1 and m2:
                    t = float(m1.group(1))
                    s = float(m2.group(1))
                    scores.append((t, s))
            except Exception:
                pass
    return scores

# =========================
# Whisper transcription + scoring (attempt to use faster_whisper if installed)
# =========================

def transcribe_segments(input_path: str, model_size: str = "small") -> List[Dict]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return []
    device = "cpu"
    compute_type = "auto"
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception:
        return []
    try:
        segments, _ = model.transcribe(input_path, beam_size=5)
    except Exception:
        return []
    out: List[Dict] = []
    for s in segments:
        out.append({"start": float(getattr(s, "start", 0.0)), "end": float(getattr(s, "end", 0.0)), "text": (getattr(s, "text", "") or "").strip()})
    return out

def find_phrase_boundaries(text: str) -> List[int]:
    """
    Find natural phrase boundaries within text to avoid cutting mid-phrase.
    Returns list of character positions where phrases naturally break.
    """
    if not text:
        return []
    
    boundaries = []
    
    # Common phrase boundary indicators
    phrase_markers = [
        # Conjunctions and transitions
        r'\b(and|but|or|so|yet|for|nor)\s+',
        r'\b(however|therefore|moreover|furthermore|nevertheless|meanwhile|consequently)\s+',
        r'\b(in addition|on the other hand|for example|for instance|in fact|as a result)\s+',
        r'\b(first|second|third|finally|lastly|next|then|after that|before that)\s+',
        
        # Prepositional phrases
        r'\b(in|on|at|by|for|with|without|through|during|before|after|since|until)\s+the\s+',
        r'\b(because of|due to|thanks to|according to|instead of|in spite of)\s+',
        
        # Relative clauses
        r'\b(which|that|who|whom|whose|where|when|why)\s+',
        
        # Pause indicators
        r'[,;:]\s+',
        r'\s+[-–—]\s+',  # Dashes
        r'\s*\([^)]*\)\s*',  # Parenthetical phrases
        
        # Natural breathing points
        r'\b(well|now|so|okay|alright|you know|I mean|like)\s+',
    ]
    
    for pattern in phrase_markers:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            boundaries.append(match.end())
    
    # Remove duplicates and sort
    boundaries = sorted(list(set(boundaries)))
    return boundaries

def group_transcript_into_paragraphs(segments: List[Dict], max_gap_s: float = 0.8,
                                     min_chars_threshold: int = 160) -> List[Dict]:
    """
    Group Whisper transcript segments into larger paragraphs using a max gap.
    A paragraph is formed by merging consecutive segments when the temporal gap
    between them is <= max_gap_s. Paragraphs help avoid mid-paragraph cuts.
    """
    if not segments:
        return []
    # Ensure segments are sorted by start time
    segs = sorted(segments, key=lambda s: float(s.get("start", 0.0)))
    paragraphs: List[Dict] = []
    cur_text = []
    cur_start = segs[0]["start"]
    cur_end = segs[0]["end"]
    cur_text.append(segs[0].get("text", ""))
    for s in segs[1:]:
        s_start = float(s.get("start", 0.0))
        s_end = float(s.get("end", 0.0))
        gap = s_start - cur_end
        if gap <= max_gap_s:
            # Merge into current paragraph
            cur_end = max(cur_end, s_end)
            cur_text.append(s.get("text", ""))
        else:
            # Finalize previous paragraph
            paragraphs.append({
                "start": float(cur_start),
                "end": float(cur_end),
                "text": (" ".join(t for t in cur_text)).strip(),
                "is_long": len("".join(cur_text)) >= min_chars_threshold or (cur_end - cur_start) >= 8.0
            })
            # Start a new paragraph
            cur_start = s_start
            cur_end = s_end
            cur_text = [s.get("text", "")]
    # Append final paragraph
    paragraphs.append({
        "start": float(cur_start),
        "end": float(cur_end),
        "text": (" ".join(t for t in cur_text)).strip(),
        "is_long": len("".join(cur_text)) >= min_chars_threshold or (cur_end - cur_start) >= 8.0
    })
    return paragraphs

def _nearest_silence_end_before(silences: List[Tuple[float, float]], t: float) -> Optional[float]:
    """Return the silence end time immediately before t, if any."""
    candidate = None
    best_delta = float("inf")
    for s_start, s_end in silences:
        if s_end <= t:
            delta = t - s_end
            if delta < best_delta:
                best_delta = delta
                candidate = s_end
    return candidate

def _nearest_silence_start_after(silences: List[Tuple[float, float]], t: float) -> Optional[float]:
    """Return the silence start time immediately after t, if any."""
    candidate = None
    best_delta = float("inf")
    for s_start, s_end in silences:
        if s_start >= t:
            delta = s_start - t
            if delta < best_delta:
                best_delta = delta
                candidate = s_start
    return candidate

def adjust_segment_boundaries_for_speech(video_path: str, segments: List[Dict], max_extend: float = 5.0) -> List[Dict]:
    """
    Adjust segment boundaries to avoid cutting during speech.
    Extends segments to natural speech breaks, phrase boundaries, or silence periods.
    """
    if not segments:
        return segments
    
    # Get transcript and silence data once for efficiency
    transcript = transcribe_segments(video_path)
    silences = detect_silences(video_path)
    video_duration = ffprobe_duration(video_path)
    paragraphs = group_transcript_into_paragraphs(transcript) if transcript else []
    min_pause_to_cut_s = 0.4  # require at least ~400ms quiet when snapping to silences
    
    adjusted_segments = []
    
    for i, segment in enumerate(segments):
        start_time = segment["start"]
        end_time = segment["end"]
        
        # Adjust start boundary to avoid cutting into speech
        new_start = start_time
        if transcript:
            # Look for speech that starts before our segment but continues into it
            for tx_seg in transcript:
                if (tx_seg["start"] < start_time < tx_seg["end"] and 
                    start_time - tx_seg["start"] <= max_extend):
                    
                    # First try to find a phrase boundary before our start time
                    text = tx_seg["text"]
                    phrase_boundaries = find_phrase_boundaries(text)
                    
                    if phrase_boundaries:
                        # Calculate approximate time positions of phrase boundaries
                        segment_duration = tx_seg["end"] - tx_seg["start"]
                        text_length = len(text)
                        
                        best_boundary_time = tx_seg["start"]  # Default to segment start
                        
                        for boundary_pos in reversed(phrase_boundaries):  # Check from end to start
                            # Estimate time position of this phrase boundary
                            time_ratio = boundary_pos / text_length if text_length > 0 else 0
                            boundary_time = tx_seg["start"] + (segment_duration * time_ratio)
                            
                            # If this boundary is before our start and within extend limit
                            if (boundary_time < start_time and 
                                start_time - boundary_time <= max_extend):
                                best_boundary_time = boundary_time
                                break
                        
                        new_start = max(0, best_boundary_time)
                    else:
                        # No phrase boundaries found, move to beginning of speech segment
                        new_start = max(0, tx_seg["start"])
                    break
            
            # Paragraph-aware start snap: if start lies inside a paragraph, prefer snapping to
            # the paragraph start or the nearest prior silence end (if available)
            if new_start == start_time and paragraphs:
                for para in paragraphs:
                    if para["start"] < start_time < para["end"]:
                        # Allow larger extend for longer paragraphs
                        max_ext_para = max_extend if not para.get("is_long") else min(10.0, (para["end"] - para["start"]) * 0.6)
                        prior_sil_end = _nearest_silence_end_before(silences, start_time)
                        if prior_sil_end is not None and (start_time - prior_sil_end) <= max_ext_para and (start_time - prior_sil_end) >= min_pause_to_cut_s:
                            new_start = prior_sil_end
                        elif (start_time - para["start"]) <= max_ext_para:
                            new_start = para["start"]
                        break

            # If no transcript/paragraph adjustment, try to align with silence end
            if new_start == start_time:
                for sil_start, sil_end in silences:
                    if (sil_end <= start_time <= sil_end + max_extend):
                        new_start = sil_end
                        break
        
        # Adjust end boundary to avoid cutting during speech
        new_end = end_time
        if transcript:
            # Look for speech that continues beyond our segment end
            for tx_seg in transcript:
                if (tx_seg["start"] < end_time < tx_seg["end"]):
                    # Check if extending to end of speech is reasonable
                    potential_end = tx_seg["end"]
                    if potential_end - end_time <= max_extend:
                        # If speech ends with sentence punctuation, extend to there
                        if tx_seg["text"].strip().endswith(('.', '!', '?', ':', ';')):
                            new_end = min(video_duration, potential_end)
                        else:
                            # Look for phrase boundaries within this segment
                            text = tx_seg["text"]
                            phrase_boundaries = find_phrase_boundaries(text)
                            
                            if phrase_boundaries:
                                # Calculate approximate time positions of phrase boundaries
                                segment_duration = tx_seg["end"] - tx_seg["start"]
                                text_length = len(text)
                                
                                for boundary_pos in phrase_boundaries:
                                    # Estimate time position of this phrase boundary
                                    time_ratio = boundary_pos / text_length if text_length > 0 else 0
                                    boundary_time = tx_seg["start"] + (segment_duration * time_ratio)
                                    
                                    # If this boundary is after our current end and within extend limit
                                    if (boundary_time > end_time and 
                                        boundary_time - end_time <= max_extend):
                                        new_end = min(video_duration, boundary_time)
                                        break

            # Paragraph-aware end snap: if end lies inside a paragraph, prefer snapping
            # to the paragraph end or the nearest following silence start
            if new_end == end_time and paragraphs:
                for para in paragraphs:
                    if para["start"] < end_time < para["end"]:
                        max_ext_para = max_extend if not para.get("is_long") else min(10.0, (para["end"] - para["start"]) * 0.6)
                        next_sil_start = _nearest_silence_start_after(silences, end_time)
                        if next_sil_start is not None and (next_sil_start - end_time) <= max_ext_para and (next_sil_start - end_time) >= min_pause_to_cut_s:
                            new_end = min(video_duration, next_sil_start)
                        elif (para["end"] - end_time) <= max_ext_para:
                            new_end = min(video_duration, para["end"]) 
                        break
            
            # If end still unchanged, consider next transcript segment that starts soon and ends at punctuation
            if new_end == end_time and transcript:
                for next_tx in transcript:
                    if next_tx["start"] >= end_time and (next_tx["start"] - end_time) <= max_extend:
                        if next_tx["text"].strip().endswith(('.', '!', '?', ':', ';')):
                            new_end = min(video_duration, next_tx["end"])
                        break
            
            # If no transcript adjustment, try to align with silence start
            if new_end == end_time:
                for sil_start, sil_end in silences:
                    if (end_time <= sil_start <= end_time + max_extend):
                        new_end = min(video_duration, sil_start)
                        break
        
        # Create adjusted segment
        adjusted_segment = segment.copy()
        # Clamp boundaries to sane ranges and avoid inversions
        new_start = max(0.0, min(new_start, video_duration))
        new_end = max(new_start + 0.05, min(new_end, video_duration))  # ensure at least 50ms duration
        adjusted_segment["start"] = new_start
        adjusted_segment["end"] = new_end
        
        # Update duration and recalculate score if boundaries changed
        if new_start != start_time or new_end != end_time:
            duration_change = (new_end - new_start) - (end_time - start_time)
            adjusted_segment["duration_adjusted"] = duration_change
            
            # Slightly boost score for speech-aware segments
            if "score" in adjusted_segment:
                adjusted_segment["score"] *= 1.05
            
            # Log the adjustment for debugging
            if new_start != start_time:
                adjusted_segment["start_adjusted"] = f"{start_time:.2f}→{new_start:.2f}"
            if new_end != end_time:
                adjusted_segment["end_adjusted"] = f"{end_time:.2f}→{new_end:.2f}"
        
        adjusted_segments.append(adjusted_segment)
    
    return adjusted_segments

def build_highlight_candidates(
    video_path: str,
    keywords: List[str],
    silence_db: float,
    min_sil_ms: int,
    min_len: float,
    max_len: float,
    use_ai_analysis: bool = True
) -> List[Dict]:
    total = ffprobe_duration(video_path)
    if total <= 0:
        return []
    sil = detect_silences(video_path, silence_db, min_sil_ms)
    voiced = invert_intervals(sil, total, keep_margin=0.05)
    scene_events = detect_scene_scores(video_path)
    tx = transcribe_segments(video_path)
    def scene_boost(a: float, b: float) -> float:
        return sum(s for t, s in scene_events if a <= t <= b)
    lower_kws = [k.strip().lower() for k in (keywords or []) if k.strip()]
    def kw_score(a: float, b: float) -> Tuple[float, str]:
        if not tx or not lower_kws:
            return 0.0, ""
        texts: List[str] = []
        for seg in tx:
            if seg["end"] >= a and seg["start"] <= b:
                texts.append(seg["text"])
        joined = " ".join(texts).lower()
        score = 0.0
        hits: List[str] = []
        for kw in lower_kws:
            cnt = joined.count(kw)
            if cnt > 0:
                score += KEYWORD_BOOST_SCORE * min(cnt, KEYWORD_MATCH_MAX_COUNT)
                hits.append(f"{kw}×{cnt}")
        score += min(len(joined) / 200.0, 2.0)
        reason = f"KW[{', '.join(hits)}]" if hits else ""
        return score, reason
    cands: List[Dict] = []
    for (a, b) in voiced:
        length = b - a
        # Reduced minimum length requirement to preserve more content
        if length < min_len * 0.5:  # Allow segments that are at least 50% of min_len
            continue
        # Reduced stride to capture more content with less gaps
        stride = max(min_len * 0.5, (min_len + max_len) / 4.0)  # Much smaller stride
        t = a
        while t + min_len <= b:
            e = min(b, t + max_len)
            if e - t >= min_len:
                sb = scene_boost(t, e)
                ksc, why = kw_score(t, e)
                base_score = (0.6 * ksc) + (0.4 * min(sb, SCENE_BOOST_MAX_SCORE))
                
                # Get text for this segment
                segment_text = ""
                if tx:
                    texts = []
                    for seg in tx:
                        if seg["end"] >= t and seg["start"] <= e:
                            texts.append(seg["text"])
                    segment_text = " ".join(texts).strip()
                
                # Apply AI analysis if enabled
                if use_ai_analysis:
                    ai_analysis = calculate_ai_content_score(video_path, t, e, segment_text, base_score)
                    final_score = ai_analysis["final_score"]
                    why = f"{why} AI[{ai_analysis['ai_score']:.2f}]"
                else:
                    final_score = base_score
                
                cands.append({
                    "start": t, 
                    "end": e, 
                    "score": final_score, 
                    "why": why,
                    "text": segment_text,
                    "source": video_path
                })
            # Much smaller step to preserve more content
            t += stride * 0.3  # Reduced from 0.75 to 0.3 for better coverage
    if scene_events:
        top_scenes = sorted(scene_events, key=lambda x: x[1], reverse=True)[:10]
        for t, s in top_scenes:
            a = max(0.0, t - max_len / 2)
            e = min(total, t + max_len / 2)
            if e - a >= min_len:
                sb = scene_boost(a, e)
                ksc, why = kw_score(a, e)
                base_score = (0.6 * ksc) + (0.4 * min(sb, SCENE_BOOST_MAX_SCORE)) + 0.5
                
                # Get text for this segment
                segment_text = ""
                if tx:
                    texts = []
                    for seg in tx:
                        if seg["end"] >= a and seg["start"] <= e:
                            texts.append(seg["text"])
                    segment_text = " ".join(texts).strip()
                
                # Apply AI analysis if enabled
                if use_ai_analysis:
                    ai_analysis = calculate_ai_content_score(video_path, a, e, segment_text, base_score)
                    final_score = ai_analysis["final_score"]
                    why = f"{why} scene-peak AI[{ai_analysis['ai_score']:.2f}]"
                else:
                    final_score = base_score
                
                cands.append({
                    "start": a, 
                    "end": e, 
                    "score": final_score, 
                    "why": why,
                    "text": segment_text,
                    "source": video_path
                })
    cands.sort(key=lambda x: x["score"], reverse=True)
    kept: List[Dict] = []
    for c in cands:
        # Allow moderate overlap to preserve more content
        significant_overlap = False
        for k in kept:
            # Calculate overlap duration
            overlap_start = max(c["start"], k["start"])
            overlap_end = min(c["end"], k["end"])
            if overlap_end > overlap_start:
                overlap_duration = overlap_end - overlap_start
                c_duration = c["end"] - c["start"]
                k_duration = k["end"] - k["start"]
                # Only reject if overlap is more than 60% of either segment
                if overlap_duration > 0.6 * min(c_duration, k_duration):
                    significant_overlap = True
                    break
        if not significant_overlap:
            kept.append(c)
        # Increased limit from 120 to 200 for even better coverage
        if len(kept) > 200:
            break
    
    # If we have very few candidates, add more overlapping ones as fallback
    if len(kept) < 50:  # Increased threshold from 30 to 50
        overlapping_candidates = []
        for c in cands:
            if c not in kept:
                overlapping_candidates.append(c)
        # Add up to 100 overlapping candidates for fallback (increased from 50)
        kept.extend(overlapping_candidates[:100])
    
    # Apply speech-aware boundary adjustments to prevent cutting during speech
    if kept:
        kept = adjust_segment_boundaries_for_speech(video_path, kept, max_extend=3.0)
    
    kept.sort(key=lambda x: x["start"])
    return kept

# =========================
# PRO helpers: dedupe, story builder, overlays, CTA, broadcast audio
# =========================

def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def frame_phash(video_path: str, t: float = 1.0) -> Optional[str]:
    """Extract frame and compute phash if possible (Pillow+imagehash required)."""
    if imagehash is None or Image is None:
        return None
    tmp = tempfile.mktemp(suffix=".jpg")
    try:
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-ss", str(max(0.1, t)),
            "-i", video_path, "-frames:v", "1", "-q:v", "2", "-y", tmp
        ]
        run(cmd, check=True)
        if not os.path.exists(tmp):
            return None
        img = Image.open(tmp).convert("RGB")
        h = str(imagehash.phash(img))
        img.close() # Close the image file handle
        return h
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def analyze_audio_quality(video_path: str, start_time: float, end_time: float) -> float:
    """Analyze audio quality of a segment (loudness, clarity, noise level)."""
    try:
        # Extract audio segment and analyze
        temp_audio = tempfile.mktemp(suffix=".wav")
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-ss", str(start_time), "-t", str(end_time - start_time),
            "-i", video_path, "-vn", "-ac", "1", "-ar", "16000",
            "-f", "wav", temp_audio
        ]
        run(cmd, check=True)
        
        if not os.path.exists(temp_audio):
            return 0.5  # Default score if extraction fails
            
        # Analyze loudness and dynamic range
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", temp_audio,
            "-af", "loudnorm=print_format=json", "-f", "null", "-"
        ]
        result = run(cmd, check=True)
        
        # Parse loudness data
        loudness_score = 0.5
        dynamic_range_score = 0.5
        
        for line in result.stderr.split('\n'):
            if '"input_loudness"' in line:
                try:
                    loudness = float(line.split(':')[1].strip().rstrip(','))
                    # Good loudness range is typically -16 to -12 LUFS
                    if -16 <= loudness <= -12:
                        loudness_score = 1.0
                    elif -20 <= loudness <= -8:
                        loudness_score = 0.8
                    else:
                        loudness_score = 0.4
                except:
                    pass
            elif '"input_dynamic_range"' in line:
                try:
                    dr = float(line.split(':')[1].strip().rstrip(','))
                    # Good dynamic range is typically 8-15 dB
                    if 8 <= dr <= 15:
                        dynamic_range_score = 1.0
                    elif 5 <= dr <= 20:
                        dynamic_range_score = 0.7
                    else:
                        dynamic_range_score = 0.4
                except:
                    pass
        
        # Clean up temp file
        try:
            os.remove(temp_audio)
        except:
            pass
            
        return (loudness_score + dynamic_range_score) / 2.0
        
    except Exception:
        return 0.5  # Default score on error

def analyze_visual_appeal(video_path: str, start_time: float, end_time: float) -> float:
    """Enhanced visual appeal analysis with motion detection, color analysis, and composition scoring."""
    try:
        # Extract multiple frames for better analysis
        segment_duration = end_time - start_time
        frame_times = []
        
        if segment_duration <= 3:
            frame_times = [start_time + segment_duration / 2]
        elif segment_duration <= 10:
            frame_times = [start_time + segment_duration * 0.25, start_time + segment_duration * 0.75]
        else:
            frame_times = [start_time + segment_duration * 0.2, start_time + segment_duration * 0.5, start_time + segment_duration * 0.8]
        
        total_scores = []
        
        for frame_time in frame_times:
            temp_frame = tempfile.mktemp(suffix=".jpg")
            
            # Extract frame
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-y",
                "-ss", str(frame_time), "-i", video_path,
                "-frames:v", "1", "-q:v", "2", temp_frame
            ]
            self.run_tracked_subprocess(cmd, check=True)
            
            if not os.path.exists(temp_frame):
                continue
                
            # Enhanced frame analysis with multiple metrics
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-i", temp_frame,
                "-vf", "signalstats,colorspace=bt709:iall=bt601-6-625:fast=1", "-f", "null", "-"
            ]
            result = run(cmd, check=True)
            
            brightness_score = 0.5
            contrast_score = 0.5
            saturation_score = 0.5
            
            for line in result.stderr.split('\n'):
                if 'lavfi.signalstats.YAVG' in line:
                    try:
                        yavg = float(line.split('=')[1].strip())
                        # Improved brightness scoring with smoother curves
                        if 0.35 <= yavg <= 0.65:
                            brightness_score = 1.0
                        elif 0.25 <= yavg <= 0.75:
                            brightness_score = 0.8
                        elif 0.15 <= yavg <= 0.85:
                            brightness_score = 0.6
                        else:
                            brightness_score = 0.3
                    except:
                        pass
                elif 'lavfi.signalstats.YDIF' in line:
                    try:
                        ydif = float(line.split('=')[1].strip())
                        # Enhanced contrast scoring
                        if ydif > 0.15:
                            contrast_score = 1.0
                        elif ydif > 0.08:
                            contrast_score = 0.8
                        elif ydif > 0.04:
                            contrast_score = 0.6
                        else:
                            contrast_score = 0.3
                    except:
                        pass
                elif 'lavfi.signalstats.UAVG' in line or 'lavfi.signalstats.VAVG' in line:
                    try:
                        # Color saturation analysis
                        chroma_val = abs(float(line.split('=')[1].strip()) - 0.5)
                        if chroma_val > 0.1:
                            saturation_score = 1.0
                        elif chroma_val > 0.05:
                            saturation_score = 0.7
                        else:
                            saturation_score = 0.4
                    except:
                        pass
            
            # Clean up temp file
            try:
                os.remove(temp_frame)
            except:
                pass
            
            # Combine scores with weighted importance
            frame_score = (brightness_score * 0.4 + contrast_score * 0.4 + saturation_score * 0.2)
            total_scores.append(frame_score)
        
        if not total_scores:
            return 0.5
            
        # Motion analysis bonus
        motion_score = analyze_motion_appeal(video_path, start_time, end_time)
        
        # Average frame scores with motion bonus
        base_score = sum(total_scores) / len(total_scores)
        final_score = min(1.0, base_score * 0.8 + motion_score * 0.2)
        
        return final_score
        
    except Exception:
        return 0.5

def analyze_motion_appeal(video_path: str, start_time: float, end_time: float) -> float:
    """Analyze motion and scene changes for visual appeal."""
    try:
        # Use scene detection to measure visual dynamics
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats",
            "-ss", str(start_time), "-t", str(end_time - start_time),
            "-i", video_path,
            "-vf", "select=gt(scene\,0.3),showinfo", "-f", "null", "-"
        ]
        result = run(cmd, check=True)
        
        # Count scene changes
        scene_changes = result.stderr.count('Parsed_showinfo')
        segment_duration = end_time - start_time
        
        # Calculate motion score based on scene change frequency
        if segment_duration > 0:
            changes_per_second = scene_changes / segment_duration
            if 0.1 <= changes_per_second <= 0.5:  # Optimal range
                return 1.0
            elif 0.05 <= changes_per_second <= 0.8:
                return 0.7
            elif changes_per_second > 0:
                return 0.5
        
        return 0.3
        
    except Exception:
        return 0.5

def analyze_speech_content(text: str, duration: float) -> float:
    """Analyze speech content quality and engagement."""
    if not text or not text.strip():
        return 0.2  # Low score for no speech
    
    text_lower = text.lower().strip()
    word_count = len(text_lower.split())
    
    # Base score from word density (optimal is ~150-200 words per minute)
    words_per_minute = (word_count / duration) * 60 if duration > 0 else 0
    if 120 <= words_per_minute <= 250:
        density_score = 1.0
    elif 80 <= words_per_minute <= 300:
        density_score = 0.7
    else:
        density_score = 0.4
    
    # Engagement keyword analysis
    engagement_score = 0.0
    engagement_count = 0
    for keyword in ENGAGEMENT_KEYWORDS:
        if keyword in text_lower:
            engagement_count += 1
            engagement_score += 0.1
    
    # Cap engagement boost
    engagement_score = min(engagement_score, 1.0)
    
    # Sentence structure analysis (simple heuristic)
    sentences = text.split('.')
    avg_sentence_length = word_count / len(sentences) if sentences else 0
    if 8 <= avg_sentence_length <= 20:
        structure_score = 1.0
    elif 5 <= avg_sentence_length <= 30:
        structure_score = 0.7
    else:
        structure_score = 0.5
    
    return (density_score * 0.4 + engagement_score * 0.4 + structure_score * 0.2)

def analyze_technical_quality(video_path: str, start_time: float, end_time: float) -> float:
    """Analyze technical quality (resolution, frame rate, compression)."""
    try:
        # Get video properties
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,bit_rate",
            "-of", "csv=p=0", video_path
        ]
        result = run(cmd, check=True)
        
        if not result.stdout:
            return 0.5
            
        parts = result.stdout.strip().split(',')
        if len(parts) < 3:
            return 0.5
            
        width = int(parts[0]) if parts[0].isdigit() else 0
        height = int(parts[1]) if parts[1].isdigit() else 0
        frame_rate_str = parts[2] if len(parts) > 2 else "0/1"
        
        # Calculate frame rate
        try:
            if '/' in frame_rate_str:
                num, den = frame_rate_str.split('/')
                frame_rate = float(num) / float(den) if float(den) != 0 else 0
            else:
                frame_rate = float(frame_rate_str)
        except:
            frame_rate = 0
            
        # Score resolution
        if width >= 1920 and height >= 1080:
            resolution_score = 1.0
        elif width >= 1280 and height >= 720:
            resolution_score = 0.8
        elif width >= 854 and height >= 480:
            resolution_score = 0.6
        else:
            resolution_score = 0.3
            
        # Score frame rate
        if frame_rate >= 30:
            framerate_score = 1.0
        elif frame_rate >= 24:
            framerate_score = 0.8
        elif frame_rate >= 15:
            framerate_score = 0.6
        else:
            framerate_score = 0.4
            
        return (resolution_score + framerate_score) / 2.0
        
    except Exception:
        return 0.5

def calculate_ai_content_score(video_path: str, start_time: float, end_time: float, 
                             text: str, base_score: float = 0.0) -> Dict:
    """Calculate comprehensive AI-driven content score for a video segment."""
    duration = end_time - start_time
    
    # Analyze different aspects
    audio_quality = analyze_audio_quality(video_path, start_time, end_time)
    visual_appeal = analyze_visual_appeal(video_path, start_time, end_time)
    speech_content = analyze_speech_content(text, duration)
    technical_quality = analyze_technical_quality(video_path, start_time, end_time)
    
    # Calculate engagement score based on content
    engagement_score = 0.5  # Base score
    if text:
        text_lower = text.lower()
        for keyword in ENGAGEMENT_KEYWORDS:
            if keyword in text_lower:
                engagement_score += 0.1
    engagement_score = min(engagement_score, 1.0)
    
    # Weighted final score with lenient boost for duration requirements
    ai_score = (
        audio_quality * AUDIO_QUALITY_WEIGHT +
        visual_appeal * VISUAL_APPEAL_WEIGHT +
        speech_content * SPEECH_CONTENT_WEIGHT +
        engagement_score * ENGAGEMENT_WEIGHT +
        technical_quality * TECHNICAL_QUALITY_WEIGHT
    )
    
    # Apply a boost to help segments meet minimum duration requirements
    ai_score_boosted = min(1.0, ai_score * 1.15)  # 15% boost, capped at 1.0
    
    # Combine with base score (more balanced weighting)
    final_score = (ai_score_boosted * 0.6) + (base_score * 0.4)
    
    return {
        "final_score": final_score,
        "ai_score": ai_score_boosted,
        "base_score": base_score,
        "audio_quality": audio_quality,
        "visual_appeal": visual_appeal,
        "speech_content": speech_content,
        "engagement": engagement_score,
        "technical_quality": technical_quality,
        "duration": duration,
        "text": text
    }

def analyze_optimal_segment_lengths(video_path: str, target_total_duration: float) -> Tuple[float, float]:
    """
    Analyze video content to determine optimal min and max segment lengths.
    FAVORS LONGER SEGMENTS for better content coverage and engagement.
    
    Args:
        video_path: Path to the video file
        target_total_duration: Target total duration for the final video
        
    Returns:
        Tuple of (min_length, max_length) in seconds
    """
    try:
        # Get video duration
        total_duration = ffprobe_duration(video_path)
        if total_duration <= 0:
            return 8.0, 25.0  # Increased default fallback
        
        # Analyze audio characteristics
        audio_props = audio_props(video_path)
        avg_loudness = audio_props.get("avg_loudness", -20.0)
        dynamic_range = audio_props.get("dynamic_range", 10.0)
        
        # Analyze visual characteristics
        visual_stats = analyze_visual_appeal(video_path, 0, total_duration)
        avg_brightness = visual_stats.get("avg_brightness", 0.5)
        avg_contrast = visual_stats.get("avg_contrast", 0.5)
        
        # Analyze speech patterns
        transcript = transcribe_segments(video_path)
        if transcript:
            # Calculate average speech segment length
            speech_lengths = [seg["end"] - seg["start"] for seg in transcript]
            avg_speech_length = sum(speech_lengths) / len(speech_lengths) if speech_lengths else 5.0
            
            # Calculate speech density
            total_speech_time = sum(speech_lengths)
            speech_density = total_speech_time / total_duration
        else:
            avg_speech_length = 5.0
            speech_density = 0.3
        
        # Determine optimal segment lengths based on content analysis
        # FAVORING LONGER SEGMENTS for better content coverage
        
        # Base lengths on target total duration - INCREASED for longer segments
        if target_total_duration <= 60:  # Short video (1 min)
            base_min = 6.0   # Increased from 4.0
            base_max = 18.0  # Increased from 12.0
        elif target_total_duration <= 300:  # Medium video (5 min)
            base_min = 10.0  # Increased from 6.0
            base_max = 25.0  # Increased from 18.0
        elif target_total_duration <= 900:  # Long video (15 min)
            base_min = 18.0  # Increased from 12.0 for longer segments
            base_max = 45.0  # Increased from 35.0 for longer segments
        elif target_total_duration <= 1800:  # Very long video (30 min)
            base_min = 25.0  # Increased from 15.0
            base_max = 60.0  # Increased from 45.0
        else:  # Extremely long video
            base_min = 35.0  # Increased from 20.0
            base_max = 90.0  # Increased from 60.0
        
        # Adjust based on speech characteristics - FAVOR LONGER SEGMENTS
        if speech_density > 0.7:  # High speech density
            # Keep segments reasonably long even for speech-heavy content
            base_min = max(5.0, base_min * 0.9)  # Reduced penalty from 0.8
            base_max = max(12.0, base_max * 0.9)  # Reduced penalty from 0.8
        elif speech_density < 0.3:  # Low speech density
            # Even longer segments for visual content
            base_min = min(30.0, base_min * 1.4)  # Increased from 1.3
            base_max = min(90.0, base_max * 1.4)  # Increased from 1.3
        
        # Adjust based on audio characteristics - FAVOR LONGER SEGMENTS
        if dynamic_range > 15:  # High dynamic range
            # Keep segments longer to capture audio changes
            base_min = max(4.0, base_min * 0.95)  # Reduced penalty from 0.9
            base_max = max(15.0, base_max * 0.95)  # Reduced penalty from 0.9
        
        # Adjust based on visual characteristics - FAVOR LONGER SEGMENTS
        if avg_contrast > 0.7:  # High contrast (action/visual interest)
            # Keep segments longer for dynamic content
            base_min = max(4.0, base_min * 0.9)  # Reduced penalty from 0.85
            base_max = max(18.0, base_max * 0.9)  # Reduced penalty from 0.85
        
        # Ensure reasonable bounds - INCREASED MINIMUMS
        min_length = max(4.0, min(45.0, base_min))  # Increased min from 2.0, max from 30.0
        max_length = max(min_length + 3.0, min(120.0, base_max))  # Increased min gap from 2.0, max from 90.0
        
        # Ensure max is at least 2.5x min for better variety (increased from 2x)
        if max_length < min_length * 2.5:
            max_length = min_length * 2.5
        
        return round(min_length, 1), round(max_length, 1)
        
    except Exception as e:
        # Fallback to longer defaults
        return 8.0, 25.0  # Increased from 6.0, 18.0

def select_best_segments_from_multiple_videos(all_candidates: List[Dict], target_duration: float, 
                                             max_segments: int = 100) -> List[Dict]:
    """Intelligently select the best segments from multiple videos based on AI analysis scores.
    ENSURES ALL VIDEOS ARE USED and prioritizes longer segments for better content coverage."""
    if not all_candidates:
        return []
    
    # Group candidates by source video
    candidates_by_source = {}
    for candidate in all_candidates:
        source = candidate.get("source", "")
        if source not in candidates_by_source:
            candidates_by_source[source] = []
        candidates_by_source[source].append(candidate)
    
    # Ensure we have at least one segment from each source video
    total_sources = len(candidates_by_source)
    print(f"[PRO] Found {total_sources} source videos to ensure coverage")
    
    # Enhanced scoring algorithm with multiple quality factors
    def segment_score(candidate):
        base_score = candidate.get("score", 0.0)
        duration = candidate["end"] - candidate["start"]
        
        # Duration optimization (sweet spot around 8-15 seconds)
        if 8 <= duration <= 15:
            duration_boost = 0.25  # 25% boost for optimal length
        elif 5 <= duration <= 20:
            duration_boost = 0.15  # 15% boost for good length
        elif 3 <= duration <= 25:
            duration_boost = 0.05  # 5% boost for acceptable length
        else:
            duration_boost = -0.1  # Penalty for too short or too long
        
        # Content diversity bonus based on transcript uniqueness
        text = candidate.get("text", "")
        diversity_bonus = 0.0
        if text:
            # Bonus for unique keywords and phrases
            unique_words = len(set(text.lower().split()))
            if unique_words > 10:
                diversity_bonus = 0.1
            elif unique_words > 5:
                diversity_bonus = 0.05
        
        # Technical quality bonus
        tech_score = candidate.get("technical_quality", 0.5)
        tech_bonus = (tech_score - 0.5) * 0.2  # Up to 10% bonus/penalty
        
        # Visual appeal bonus
        visual_score = candidate.get("visual_appeal", 0.5)
        visual_bonus = (visual_score - 0.5) * 0.15  # Up to 7.5% bonus/penalty
        
        # Combine all factors
        total_multiplier = 1.0 + duration_boost + diversity_bonus + tech_bonus + visual_bonus
        return base_score * max(0.5, total_multiplier)  # Ensure minimum score
    
    sorted_candidates = sorted(all_candidates, key=segment_score, reverse=True)
    
    selected_segments = []
    total_duration = 0.0
    used_sources = set()  # Track which source videos we've used
    
    # First pass: Ensure at least one segment from each source video
    for source, source_candidates in candidates_by_source.items():
        if source in used_sources:
            continue
            
        # Get the best segment from this source
        best_from_source = max(source_candidates, key=lambda x: x.get("score", 0.0))
        
        # Check for overlap with already selected segments
        overlaps = False
        for selected in selected_segments:
            if not (best_from_source["end"] <= selected["start"] or best_from_source["start"] >= selected["end"]):
                overlaps = True
                break
        
        if not overlaps:
            selected_segments.append(best_from_source)
            total_duration += best_from_source["end"] - best_from_source["start"]
            used_sources.add(source)
            print(f"[PRO] Ensured coverage: Added segment from {os.path.basename(source)} ({best_from_source['start']:.1f}-{best_from_source['end']:.1f}s)")
    
    # Second pass: Select highest-scoring segments, ensuring variety across sources
    for candidate in sorted_candidates:
        if len(selected_segments) >= max_segments or total_duration >= target_duration * 2.0:  # Allow 100% overflow
            break
            
        # Skip if already selected
        if candidate in selected_segments:
            continue
            
        # Check for overlap with already selected segments
        overlaps = False
        for selected in selected_segments:
            if not (candidate["end"] <= selected["start"] or candidate["start"] >= selected["end"]):
                overlaps = True
                break
        
        if not overlaps:
            selected_segments.append(candidate)
            total_duration += candidate["end"] - candidate["start"]
            used_sources.add(candidate.get("source", ""))
    
    # Third pass: If we need more content, add segments from unused sources
    if total_duration < target_duration * 0.9:  # If we're below 90% of target
        for candidate in sorted_candidates:
            if len(selected_segments) >= max_segments or total_duration >= target_duration * 2.0:
                break
                
            if candidate in selected_segments:
                continue
                
            # Check for overlap
            overlaps = False
            for selected in selected_segments:
                if not (candidate["end"] <= selected["start"] or candidate["start"] >= selected["end"]):
                    overlaps = True
                    break
            
            if not overlaps:
                selected_segments.append(candidate)
                total_duration += candidate["end"] - candidate["start"]
    
    # Fourth pass: If still too short, add any non-overlapping segments until we reach target
    if total_duration < target_duration:
        for candidate in sorted_candidates:
            if candidate in selected_segments:
                continue
                
            # Check for overlap
            overlaps = False
            for selected in selected_segments:
                if not (candidate["end"] <= selected["start"] or candidate["start"] >= selected["end"]):
                    overlaps = True  # Fix: Changed from False to True to prevent repeating segments
                    break
            
            if not overlaps:
                selected_segments.append(candidate)
                total_duration += candidate["end"] - candidate["start"]
                if total_duration >= target_duration:
                    break
    
    # Fifth pass: If still too short, be more aggressive and allow some overlap
    if total_duration < target_duration * 0.95:  # If we're below 95% of target
        for candidate in sorted_candidates:
            if candidate in selected_segments:
                continue
                
            # Allow segments with minimal overlap (up to 2 seconds)
            max_overlap = 2.0
            overlaps_too_much = False
            for selected in selected_segments:
                overlap_start = max(candidate["start"], selected["start"])
                overlap_end = min(candidate["end"], selected["end"])
                if overlap_end > overlap_start and (overlap_end - overlap_start) > max_overlap:
                    overlaps_too_much = True
                    break
            
            if not overlaps_too_much:
                selected_segments.append(candidate)
                total_duration += candidate["end"] - candidate["start"]
                if total_duration >= target_duration:
                    break
    
    # Final check: Ensure we're using all available source videos
    final_used_sources = set(seg.get("source", "") for seg in selected_segments)
    unused_sources = set(candidates_by_source.keys()) - final_used_sources
    
    if unused_sources:
        print(f"[PRO] ⚠️  WARNING: {len(unused_sources)} source videos not used in final selection")
        for unused in list(unused_sources)[:3]:  # Show first 3 unused sources
            print(f"[PRO]   - {os.path.basename(unused)}")
        if len(unused_sources) > 3:
            print(f"[PRO]   ... and {len(unused_sources) - 3} more")
    else:
        print(f"[PRO] ✅ All {len(candidates_by_source)} source videos are represented in final selection")
    
    # Sort selected segments by their original timing for better flow
    selected_segments.sort(key=lambda x: (x.get("source", ""), x["start"]))
    
    return selected_segments

def build_storyline_from_candidates(candidates: List[Dict], transcript_map: Dict[Tuple[float,float], str], total_target: float) -> List[Dict]:
    if not candidates:
        return []
    for c in candidates:
        a, b = c["start"], c["end"]
        dur = b - a
        text = transcript_map.get((round(a,2), round(b,2)), "")
        kw_boost = 0.0
        for kw in ("subscribe", "like", "tip", "trick", "hack", "important", "how to", "best", "mistake", "warning"):
            if kw in text.lower():
                kw_boost += 0.8
        c["_dur"] = dur
        c["_text"] = text
        c["_value"] = c.get("score", 0.0) + kw_boost + min(dur/10.0, 0.6)
    short_candidates = [c for c in candidates if c["_dur"] <= 12.0]
    if short_candidates:
        hook = max(short_candidates, key=lambda x: x["_value"])
    else:
        hook = max(candidates, key=lambda x: x["_value"])
    remaining = [c for c in candidates if not (c["start"] >= hook["start"] and c["end"] <= hook["end"])]
    remaining_sorted = sorted(remaining, key=lambda x: (-x["_value"], x["start"]))
    ordered = [hook]
    total = hook["_dur"]
    for c in remaining_sorted:
        if total >= total_target:
            break
        overlap = any(not (c["end"] <= o["start"] or c["start"] >= o["end"]) for o in ordered)
        if overlap:
            continue
        ordered.append(c)
        total += c["_dur"]
    return ordered

def get_system_font() -> str:
    """Get a cross-platform font path with proper escaping for FFmpeg"""
    if os.name == 'nt':  # Windows
        return "C\\\\Windows\\\\Fonts\\\\arial.ttf"
    else:  # Linux/Unix
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def get_system_font_bold() -> str:
    """Get a cross-platform bold font path with proper escaping for FFmpeg"""
    if os.name == 'nt':  # Windows
        return "C\\\\Windows\\\\Fonts\\\\arialbd.ttf"
    else:  # Linux/Unix
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def add_animated_title(input_path: str, text: str, out_path: str, fontsize=48, pos_y="h*0.12", duration_fade=0.6, vf_extra: Optional[str] = None) -> bool:
    safe_text = text.replace(":", "\\:").replace("'", "\\'")
    draw_filter = (
        f"drawtext=fontfile={get_system_font_bold()}:"
        f"text='{safe_text}':"
        f"fontsize={fontsize}:"
        f"x=(w-text_w)/2:y={pos_y}:"
        f"fontcolor=white@1.0:"
        f"enable='between(t,0,{duration_fade+3})':"
        f"alpha='if(lt(t,{duration_fade}),t/{duration_fade}, if(lt(t,{duration_fade+2}),1.0, 1.0-(t-{duration_fade+2})/{duration_fade}))'"
    )
    vf_final = f"{draw_filter},{vf_extra}" if vf_extra else draw_filter
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-i", input_path,
        "-vf", vf_final,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "copy", out_path
    ]
    run(cmd, check=True)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0

def get_lower_third_filter(name: str = "", title: str = "") -> Optional[str]:
    if not name and not title:
        return None
    txt = f"{name}  |  {title}" if name and title else (name or title)
    draw = (
        f"drawtext=fontfile={get_system_font()}:text='{txt}':"
        f"fontsize=28:x=40:y=h-(text_h*3):fontcolor=white:box=1:boxcolor=black@0.35:boxborderw=12"
    )
    return draw

def add_lower_third(input_path: str, out_path: str, name: str = "", title: str = "") -> bool:
    filter_str = get_lower_third_filter(name, title)
    if not filter_str:
        shutil.copy(input_path, out_path)
        return True
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "copy", out_path
    ]
    run(cmd, check=True)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0

def generate_cta_clip(out_dir: str, width=1920, height=1080, duration=4.0, text="Subscribe for more!") -> Optional[str]:
    img = os.path.join(out_dir, "cta_card.png")
    mp4 = os.path.join(out_dir, f"cta_{uuid.uuid4().hex[:6]}.mp4")
    try:
        if Image is not None:
            from PIL import ImageDraw, ImageFont, Image as PILImage
            im = PILImage.new("RGB", (width, height), color=(11, 20, 26))
            draw = ImageDraw.Draw(im)
            try:
                fnt = ImageFont.truetype(get_system_font_bold(), 96)
            except Exception:
                fnt = None
            if fnt:
                w, h = draw.textsize(text, font=fnt)
            else:
                w, h = draw.textsize(text)
            draw.text(((width-w)/2, (height-h)/2), text, font=fnt, fill=(255,255,255))
            im.save(img, "PNG")
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-y",
                "-loop", "1", "-i", img, "-t", str(duration),
                "-vf", f"scale={width}:{height}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-shortest", mp4
            ]
            run(cmd, check=True)
            if os.path.exists(mp4):
                return mp4
            return None
        else:
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-y",
                "-f", "lavfi", "-i", f"color=c=0b141a:s={width}x{height}:d={duration}",
                "-vf", f"drawtext=fontfile={get_system_font_bold()}:text='{text}':fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2:fontcolor=white",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", mp4
            ]
            run(cmd, check=True)
            if os.path.exists(mp4):
                return mp4
            return None
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(img):
                os.remove(img)
        except Exception:
            pass

def broadcast_audio_chain(input_path: str, output_path: str) -> bool:
    tmp = output_path + ".tmp_audio.mp4"
    # Gentler audio processing to reduce artifacts
    af = (
        "highpass=f=60,lowpass=f=18000,"  # Less aggressive filtering
        "compand=attacks=0.1:decays=0.5:points=-80/-80|-20/-12|0/-6|20/0"  # Gentler compression
    )
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-i", input_path,
        "-af", af,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000",  # Higher quality audio
        tmp
    ]
    run(cmd, check=True)
    if not os.path.exists(tmp):
        return False
    ok = loudness_normalize(tmp, output_path, i_lufs=-14.0)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    return ok and os.path.exists(output_path)

def balance_segments_across_videos(selected_segments: List[Dict], target_duration: float, 
                                   all_candidates: List[Dict]) -> List[Dict]:
    """
    Balance segment selection across multiple videos to ensure fair representation.
    This function ensures that no single video dominates the final selection.
    """
    if not selected_segments or not all_candidates:
        return selected_segments
    
    # Group candidates by source video
    candidates_by_source = {}
    for candidate in all_candidates:
        source = candidate.get("source", "")
        if source not in candidates_by_source:
            candidates_by_source[source] = []
        candidates_by_source[source].append(candidate)
    
    if len(candidates_by_source) <= 1:
        return selected_segments  # No balancing needed for single video
    
    # Calculate current distribution
    current_distribution = {}
    for seg in selected_segments:
        source = seg.get("source", "")
        if source not in current_distribution:
            current_distribution[source] = {"count": 0, "duration": 0.0}
        current_distribution[source]["count"] += 1
        current_distribution[source]["duration"] += seg["end"] - seg["start"]
    
    # Calculate target distribution (roughly equal representation)
    total_sources = len(candidates_by_source)
    target_segments_per_source = max(1, len(selected_segments) // total_sources)
    target_duration_per_source = target_duration / total_sources
    
    print(f"[PRO] Balancing segments across {total_sources} videos...")
    print(f"[PRO] Target: ~{target_segments_per_source} segments per video, ~{int(target_duration_per_source)}s per video")
    
    # Check if any video is over-represented
    over_represented = []
    under_represented = []
    
    for source, stats in current_distribution.items():
        if stats["count"] > target_segments_per_source * 1.5:  # 50% over target
            over_represented.append(source)
        elif stats["count"] < target_segments_per_source * 0.5:  # 50% under target
            under_represented.append(source)
    
    if not over_represented and not under_represented:
        print(f"[PRO] ✅ Segment distribution is already well-balanced")
        return selected_segments
    
    # Try to balance by replacing some over-represented segments with under-represented ones
    balanced_segments = selected_segments.copy()
    
    for over_source in over_represented:
        if not under_represented:
            break
            
        # Find segments from over-represented source that could be replaced
        over_segments = [seg for seg in balanced_segments if seg.get("source") == over_source]
        over_segments.sort(key=lambda x: x.get("score", 0.0))  # Sort by score (worst first)
        
        # Try to replace lower-scoring segments
        for over_seg in over_segments[:2]:  # Try to replace up to 2 segments
            if not under_represented:
                break
                
            # Find best replacement from under-represented sources
            best_replacement = None
            best_score = 0.0
            
            for under_source in under_represented:
                under_candidates = [c for c in all_candidates if c.get("source") == under_source and c not in balanced_segments]
                if not under_candidates:
                    continue
                    
                # Check for overlap
                for candidate in under_candidates:
                    overlaps = False
                    for seg in balanced_segments:
                        if seg != over_seg and not (candidate["end"] <= seg["start"] or candidate["start"] >= seg["end"]):
                            overlaps = True
                            break
                    
                    if not overlaps and candidate.get("score", 0.0) > best_score:
                        best_replacement = candidate
                        best_score = candidate.get("score", 0.0)
            
            if best_replacement:
                # Replace the segment
                balanced_segments.remove(over_seg)
                balanced_segments.append(best_replacement)
                
                # Update distribution tracking
                current_distribution[over_source]["count"] -= 1
                current_distribution[over_source]["duration"] -= (over_seg["end"] - over_seg["start"])
                
                under_source = best_replacement.get("source", "")
                if under_source not in current_distribution:
                    current_distribution[under_source] = {"count": 0, "duration": 0.0}
                current_distribution[under_source]["count"] += 1
                current_distribution[under_source]["duration"] += (best_replacement["end"] - best_replacement["start"])
                
                print(f"[PRO] Balanced: Replaced segment from {os.path.basename(over_source)} with segment from {os.path.basename(under_source)}")
                
                # Recalculate under/over representation
                over_represented = []
                under_represented = []
                for source, stats in current_distribution.items():
                    if stats["count"] > target_segments_per_source * 1.5:
                        over_represented.append(source)
                    elif stats["count"] < target_segments_per_source * 0.5:
                        under_represented.append(source)
                break
    
    # Final distribution report
    print(f"[PRO] Final segment distribution:")
    for source, stats in current_distribution.items():
        print(f"[PRO]   {os.path.basename(source)}: {stats['count']} segments, {int(stats['duration'])}s")
    
    return balanced_segments

# =========================
# AI Music Generation
# =========================

def analyze_video_mood_and_style(video_path: str, segments: List[Dict]) -> Dict:
    """Analyze video content to determine appropriate music style and mood."""
    try:
        # Initialize with default values in case analysis fails
        mood_indicators = {
            "energetic": 0.0,
            "calm": 0.0,
            "dramatic": 0.0,
            "upbeat": 0.5,  # Default to upbeat as fallback
            "melancholic": 0.0
        }
        
        style_indicators = {
            "electronic": 0.5,  # Default to electronic as fallback
            "acoustic": 0.0,
            "orchestral": 0.0,
            "ambient": 0.0
        }
        
        # Validate segments input
        if not isinstance(segments, list) or len(segments) == 0:
            print("[WARNING] No segments provided for mood analysis, using defaults")
            return {"mood": "upbeat", "style": "electronic"}
        
        # Analyze text content for mood indicators
        all_text = ""
        for segment in segments:
            if isinstance(segment, dict):
                text = segment.get("text", "").lower()
                all_text += text + " "
    
        # Mood analysis based on keywords
        energetic_keywords = ["amazing", "incredible", "awesome", "exciting", "fast", "quick", "action"]
        calm_keywords = ["peaceful", "calm", "relaxing", "gentle", "soft", "quiet"]
        dramatic_keywords = ["dramatic", "intense", "powerful", "strong", "important", "critical"]
        upbeat_keywords = ["happy", "fun", "great", "wonderful", "fantastic", "positive"]
        melancholic_keywords = ["sad", "emotional", "touching", "moving", "deep", "serious"]
        
        for keyword in energetic_keywords:
            if keyword in all_text:
                mood_indicators["energetic"] += 0.1
        for keyword in calm_keywords:
            if keyword in all_text:
                mood_indicators["calm"] += 0.1
        for keyword in dramatic_keywords:
            if keyword in all_text:
                mood_indicators["dramatic"] += 0.1
        for keyword in upbeat_keywords:
            if keyword in all_text:
                mood_indicators["upbeat"] += 0.1
        for keyword in melancholic_keywords:
            if keyword in all_text:
                mood_indicators["melancholic"] += 0.1
                
        # Ensure we have at least some mood values
        if sum(mood_indicators.values()) < 0.1:
            mood_indicators["upbeat"] = 0.5  # Default to upbeat if no keywords matched
        
        # Analyze visual content (simplified)
        try:
            # Get average brightness and contrast from segments
            total_brightness = 0.0
            total_contrast = 0.0
            segment_count = 0
            
            # Limit to first 5 segments to avoid excessive processing
            for segment in segments[:5]:
                try:
                    if not isinstance(segment, dict) or 'start' not in segment or 'end' not in segment:
                        continue
                        
                    mid_time = (segment["start"] + segment["end"]) / 2
                    temp_frame = tempfile.mktemp(suffix=".jpg")
                    
                    cmd = [
                        "ffmpeg", "-hide_banner", "-nostats", "-y",
                        "-ss", str(mid_time), "-i", video_path,
                        "-frames:v", "1", "-q:v", "2", temp_frame
                    ]
                    run(cmd, check=True, timeout=10)  # Add timeout to prevent hanging
                    
                    if os.path.exists(temp_frame):
                        cmd = [
                            "ffmpeg", "-hide_banner", "-nostats", "-i", temp_frame,
                            "-vf", "signalstats", "-f", "null", "-"
                        ]
                        result = run(cmd, check=True, timeout=10, capture_output=True, text=True)
                        
                        stderr = result.stderr if hasattr(result, 'stderr') else ''
                        for line in stderr.split('\n'):
                            if 'lavfi.signalstats.YAVG' in line:
                                try:
                                    brightness = float(line.split('=')[1].strip())
                                    total_brightness += brightness
                                    segment_count += 1
                                except (ValueError, IndexError):
                                    pass
                            elif 'lavfi.signalstats.YDIF' in line:
                                try:
                                    contrast = float(line.split('=')[1].strip())
                                    total_contrast += contrast
                                except (ValueError, IndexError):
                                    pass
                    
                    # Clean up
                    try:
                        if os.path.exists(temp_frame):
                            os.remove(temp_frame)
                    except:
                        pass
                        
                except Exception as e:
                    print(f"[WARNING] Error analyzing segment: {e}")
                    continue
            
            if segment_count > 0:
                avg_brightness = total_brightness / segment_count
                avg_contrast = total_contrast / segment_count
                
                # Adjust mood based on visual characteristics
                if avg_brightness > 0.6:
                    mood_indicators["energetic"] += 0.2
                    mood_indicators["upbeat"] += 0.2
                elif avg_brightness < 0.3:
                    mood_indicators["melancholic"] += 0.2
                    mood_indicators["dramatic"] += 0.2
                
                if avg_contrast > 0.1:
                    mood_indicators["dramatic"] += 0.2
                    style_indicators["orchestral"] += 0.2
                else:
                    mood_indicators["calm"] += 0.2
                    style_indicators["ambient"] += 0.2
                    
        except Exception as e:
            print(f"[WARNING] Visual content analysis failed: {e}")
            # Set default values if visual analysis fails
            style_indicators["electronic"] = 0.5
        
        # Determine dominant mood and style
        dominant_mood = max(mood_indicators, key=mood_indicators.get)
        dominant_style = max(style_indicators, key=style_indicators.get)
        
        return {
            "mood": dominant_mood,
            "style": dominant_style,
            "mood_scores": mood_indicators,
            "style_scores": style_indicators,
            "confidence": max(mood_indicators.values()) + max(style_indicators.values())
        }
        
    except Exception as e:
        print(f"[WARNING] Video mood analysis failed: {e}")
        # Return default values if analysis fails
        return {
            "mood": "upbeat",
            "style": "electronic",
            "mood_scores": {"upbeat": 1.0},
            "style_scores": {"electronic": 1.0},
            "confidence": 0.5
        }

def generate_ai_music_gru(video_duration: float, mood_analysis: Dict, output_path: str) -> bool:
    """Generate AI music using a lightweight GRU with improved synthesis and streaming write.
    - Dynamically selects sample rate to reduce memory for long videos
    - Applies smooth fade-in/out and gentle EQ/processing on transcode
    - Streams WAV in blocks to avoid large allocations
    Returns True on success; falls back to other generators if unavailable."""
    try:
        import numpy as np
        import wave
        import math
        import tempfile
        import os
        import hashlib
        import shutil

        # Duration and sample settings (dynamic SR for memory efficiency)
        safe_duration = min(max(float(video_duration), 1.0), 600.0)
        if safe_duration > 300:
            sr = 16000
        elif safe_duration > 180:
            sr = 22050
        else:
            sr = 32000
        n_samples = int(safe_duration * sr)
        control_rate = 25.0  # 25 control steps per second
        steps = max(1, int(safe_duration * control_rate))

        # Extract mood/style features
        mood = str(mood_analysis.get("mood", "upbeat"))
        style = str(mood_analysis.get("style", "electronic"))
        tempo_map = {"energetic": 140, "calm": 80, "dramatic": 100, "upbeat": 120, "melancholic": 90}
        style_map = {"electronic": 1.0, "acoustic": 0.6, "orchestral": 0.5, "ambient": 0.4}
        tempo = tempo_map.get(mood, 100)
        freq_base = 440.0 if mood in ("energetic", "upbeat") else (330.0 if mood == "dramatic" else 220.0)
        style_val = style_map.get(style, 0.8)
        tempo_norm = (tempo - 60.0) / (160.0 - 60.0)  # ~0..1

        # Seed RNG deterministically from mood/style for reproducible outputs per content
        seed_int = int(hashlib.sha256((mood + "|" + style).encode()).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed=seed_int)

        # Tiny GRU parameters
        input_dim = 3
        hidden_dim = 8
        output_dim = 2  # [freq_mod, amp_mod]
        Wz = rng.standard_normal((hidden_dim, input_dim)) * 0.5
        Uz = rng.standard_normal((hidden_dim, hidden_dim)) * 0.5
        bz = np.zeros(hidden_dim)
        Wr = rng.standard_normal((hidden_dim, input_dim)) * 0.5
        Ur = rng.standard_normal((hidden_dim, hidden_dim)) * 0.5
        br = np.zeros(hidden_dim)
        Wh = rng.standard_normal((hidden_dim, input_dim)) * 0.5
        Uh = rng.standard_normal((hidden_dim, hidden_dim)) * 0.5
        bh = np.zeros(hidden_dim)
        Wy = rng.standard_normal((output_dim, hidden_dim)) * 0.4
        by = np.zeros(output_dim)

        def sigmoid(x):
            return 1.0 / (1.0 + np.exp(-x))

        # Build a constant input feature vector with slight noise per step
        base_x = np.array([style_val, tempo_norm, 0.5], dtype=np.float32)
        h = np.zeros(hidden_dim, dtype=np.float32)
        freq_env = np.zeros(steps, dtype=np.float32)
        amp_env = np.zeros(steps, dtype=np.float32)

        for ti in range(steps):
            x = base_x + 0.02 * rng.standard_normal(input_dim)
            z = sigmoid(Wz @ x + Uz @ h + bz)
            r = sigmoid(Wr @ x + Ur @ h + br)
            h_tilde = np.tanh(Wh @ x + Uh @ (r * h) + bh)
            h = (1.0 - z) * h + z * h_tilde
            y = Wy @ h + by  # 2-dim output
            # Map to frequency (Hz) and amplitude (0..1)
            freq = np.clip(freq_base * (1.0 + 0.55 * np.tanh(y[0])), 120.0, 1000.0)
            amp = np.clip(0.18 + 0.28 * sigmoid(y[1] + 0.5 * tempo_norm), 0.05, 0.45)
            # Add gentle rhythmic modulation tied to tempo
            mod = 0.06 * math.sin(2 * math.pi * (ti / control_rate) * (tempo / 60.0))
            freq_env[ti] = float(np.clip(freq * (1.0 + mod), 120.0, 1200.0))
            amp_env[ti] = float(np.clip(amp * (1.0 + 0.5 * mod), 0.03, 0.6))

        # Prepare streaming synthesis
        t_env = np.linspace(0.0, safe_duration, steps, dtype=np.float64)
        block = 65536  # ~2s at 32kHz
        tmp_wav = tempfile.mktemp(suffix=".wav")
        with wave.open(tmp_wav, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sr)

            phi_state = 0.0
            written = 0
            while written < n_samples:
                remain = n_samples - written
                bs = block if remain > block else remain
                # Time for current block
                t_block = np.linspace(written / sr, (written + bs) / sr, bs, endpoint=False, dtype=np.float64)
                # Interpolate envelopes
                freq_b = np.interp(t_block, t_env, freq_env)
                amp_b = np.interp(t_block, t_env, amp_env)
                # Smooth global fade-in/out
                fade_in_s = 0.8
                fade_out_s = 1.0
                fade_in = np.clip(t_block / fade_in_s, 0.0, 1.0)
                fade_out = np.clip((safe_duration - t_block) / fade_out_s, 0.0, 1.0)
                amp_b *= np.minimum(fade_in, fade_out)
                # Integrate instantaneous frequency into phase
                phi_b = phi_state + 2.0 * np.pi * np.cumsum(freq_b) / float(sr)
                # Primary and a subtle secondary oscillator for richness
                audio_b = amp_b * np.sin(phi_b)
                audio_b += 0.15 * amp_b * np.sin(phi_b * 0.5)
                # Optional ambient noise bed for ambient style
                if style == "ambient":
                    audio_b += 0.02 * rng.standard_normal(bs)
                # Stereo and PCM conversion
                chunk_stereo = np.stack([audio_b, audio_b], axis=-1)
                pcm = (np.clip(chunk_stereo, -1.0, 1.0) * 32767.0).astype(np.int16)
                wf.writeframes(pcm.tobytes())
                # Advance state
                phi_state = float(phi_b[-1])
                written += bs

        # Build ffmpeg binary path (fallback to local ffmpeg.exe if not on PATH)
        ffmpeg_bin = "ffmpeg"
        try:
            import shutil as _sh
            if _sh.which("ffmpeg") is None:
                local_ff = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
                if os.path.exists(local_ff):
                    ffmpeg_bin = local_ff
        except Exception:
            pass

        # Mood/style-aware audio processing chain on transcode
        af_chain = "highpass=f=60,lowpass=f=10000"
        if mood in ("energetic", "upbeat"):
            af_chain += ",acompressor=threshold=-20dB:ratio=3:attack=5:release=40"
        elif mood == "ambient":
            af_chain += ",aecho=0.6:0.5:100:0.3"
        elif mood == "dramatic":
            af_chain += ",aecho=0.6:0.4:60:0.2"

        res = run([
            ffmpeg_bin, "-hide_banner", "-nostats", "-y",
            "-i", tmp_wav,
            "-af", af_chain,
            "-c:a", "aac", "-b:a", "128k",
            "-ar", "44100", "-ac", "2",
            output_path
        ], check=False, timeout=180)

        try:
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)
        except Exception:
            pass

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0 and (res is None or res.returncode == 0)

    except ImportError:
        # numpy not available; caller should fallback
        return False
    except Exception as e:
        print(f"[WARNING] GRU music generation failed: {e}")
        return False


def generate_ai_music(video_duration: float, mood_analysis: Dict, output_path: str) -> bool:
    """Generate AI music based on video analysis. Prefer GRU-based synthesis; fallback to FFmpeg."""
    try:
        import subprocess  # Ensure subprocess is imported for TimeoutExpired exception
        import shutil

        # Caching: reuse previous AI music for same mood/style and similar duration
        def _ai_music_cache_dir() -> str:
            base = os.path.join(os.path.dirname(__file__), "generated_music")
            try:
                os.makedirs(base, exist_ok=True)
            except Exception:
                pass
            return base

        def _ai_music_cache_key(dur: float, ma: Dict) -> str:
            bucket = int(min(max(dur, 1.0), 600.0) // 5) * 5  # 5s buckets
            mood = str(ma.get("mood", "upbeat"))
            style = str(ma.get("style", "electronic"))
            return hashlib.sha1(f"{mood}|{style}|{bucket}".encode()).hexdigest()

        # Validate input parameters
        if not isinstance(video_duration, (int, float)) or video_duration <= 0:
            print(f"[ERROR] Invalid video duration: {video_duration}")
            emit_log("PRO", f"AI music generation failed: Invalid video duration {video_duration}")
            return False
            
        if not isinstance(mood_analysis, dict):
            print(f"[WARNING] Invalid mood analysis data, using defaults")
            mood_analysis = {"mood": "upbeat", "style": "electronic"}
            
        mood = mood_analysis.get("mood", "upbeat")
        style = mood_analysis.get("style", "electronic")
        print(f"[INFO] Generating AI music: mood={mood}, style={style}, duration={video_duration:.2f}s")
        print(f"[INFO] Generating AI music based on content analysis...")

        # Check cache first
        cache_dir = _ai_music_cache_dir()
        cache_fp = os.path.join(cache_dir, f"{_ai_music_cache_key(video_duration, mood_analysis)}.mp3")
        try:
            if os.path.exists(cache_fp):
                cached_dur = ffprobe_duration(cache_fp)
                # Accept cache if close enough (within ~2% or 1s)
                if cached_dur >= max(1.0, min(video_duration * 0.98, video_duration - 1.0)):
                    shutil.copy2(cache_fp, output_path)
                    print(f"[INFO] Reused cached AI music: {os.path.basename(cache_fp)}")
                    return True
        except Exception:
            pass

        # First try GRU-based synthesis
        try:
            if generate_ai_music_gru(video_duration, mood_analysis, output_path):
                print(f"[INFO] AI music (GRU) generation successful: {output_path}")
                # Store in cache
                try:
                    shutil.copy2(output_path, cache_fp)
                except Exception:
                    pass
                return True
            else:
                print(f"[INFO] GRU path unavailable or failed; falling back to FFmpeg synthesis")
        except Exception as e:
            print(f"[WARNING] GRU path error: {e}; falling back to FFmpeg synthesis")
        
        # Define music parameters based on mood and style for FFmpeg fallback
        if mood == "energetic":
            tempo = 140
            frequency_base = 440  # A4
        elif mood == "calm":
            tempo = 80
            frequency_base = 220  # A3
        elif mood == "dramatic":
            tempo = 100
            frequency_base = 330  # E4
        elif mood == "upbeat":
            tempo = 120
            frequency_base = 440  # A4
        else:  # melancholic
            tempo = 90
            frequency_base = 220  # A3
        
        # Limit duration to prevent FFmpeg issues
        safe_duration = min(video_duration, 600)  # Max 10 minutes to prevent issues
        
        # Use simpler audio filters for better compatibility
        if style == "electronic":
            af = "volume=0.3"
        elif style == "acoustic":
            af = "volume=0.25"
        elif style == "orchestral":
            af = "volume=0.2"
        else:  # ambient
            af = "volume=0.15"
        
        # Generate the music using FFmpeg's audio sources with more robust settings
        audio_input = f"sine=frequency={frequency_base}:duration={safe_duration},sine=frequency={frequency_base*1.25}:duration={safe_duration}[a1][a2];[a1][a2]amix=inputs=2:duration=longest"
        
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-f", "lavfi",
            "-i", audio_input,
            "-af", f"{af},highpass=f=80,lowpass=f=8000",  # Add basic EQ
            "-c:a", "aac", "-b:a", "128k",
            "-ar", "44100", "-ac", "2",
            "-t", str(safe_duration),
            output_path
        ]
        
        print(f"[INFO] Running FFmpeg for AI music generation (fallback)")
        try:
            result = run(cmd, check=False, timeout=300)
            if result.returncode != 0:
                print(f"[WARNING] Complex audio generation failed, trying simple fallback")
                simple_cmd = [
                    "ffmpeg", "-hide_banner", "-nostats", "-y",
                    "-f", "lavfi",
                    "-i", f"sine=frequency={frequency_base}:duration={safe_duration}",
                    "-af", af,
                    "-c:a", "aac", "-b:a", "128k",
                    "-ar", "44100", "-ac", "2",
                    "-t", str(safe_duration),
                    output_path
                ]
                result = run(simple_cmd, check=False, timeout=300)
                if result.returncode != 0:
                    print(f"[ERROR] FFmpeg fallback also failed with code {result.returncode}")
                    print(f"[INFO] AI music generation failed; continuing without music.")
                    return False
        except subprocess.TimeoutExpired:
            print(f"[ERROR] FFmpeg command timed out after 300 seconds")
            print(f"[INFO] AI music generation failed; continuing without music.")
            return False
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"[INFO] AI music generation successful: {output_path}")
            print(f"[INFO] AI music generation completed successfully")
            # Store in cache for reuse
            try:
                shutil.copy2(output_path, cache_fp)
            except Exception:
                pass
            return True
        else:
            print(f"[ERROR] AI music output missing or empty: {output_path}")
            print(f"[INFO] AI music generation failed; continuing without music.")
            return False
        
    except Exception as e:
        print(f"[ERROR] AI music generation failed: {e}")
        print(f"[INFO] AI music generation failed; continuing without music.")
        return False

def add_ai_generated_music(video_path: str, segments: List[Dict], output_path: str) -> bool:
    """Add AI-generated background music to video based on content analysis."""
    try:
        # Analyze video content for music style
        mood_analysis = analyze_video_mood_and_style(video_path, segments)
        
        # Get video duration
        video_duration = ffprobe_duration(video_path)
        if video_duration <= 0:
            return False
        
        # Generate AI music
        temp_music = tempfile.mktemp(suffix=".mp3")
        if not generate_ai_music(video_duration, mood_analysis, temp_music):
            return False
        
        # Add music to video with ducking
        return add_music_ducked(video_path, temp_music, output_path)
        
    except Exception as e:
        print(f"[ERROR] Adding AI music failed: {e}")
        return False
    finally:
        # Clean up temp music file
        try:
            if 'temp_music' in locals() and os.path.exists(temp_music):
                os.remove(temp_music)
        except:
            pass

def analyze_transition_compatibility(prev_path: str, next_path: str) -> Dict:
    """Analyze compatibility between two video segments for transition selection."""
    try:
        # Get visual similarity by comparing end frame of prev with start frame of next
        prev_hash = frame_phash(prev_path, ffprobe_duration(prev_path) - 0.5)
        next_hash = frame_phash(next_path, 0.5)
        
        visual_similarity = 0.0
        if prev_hash and next_hash and imagehash:
            try:
                prev_img_hash = imagehash.hex_to_hash(prev_hash)
                next_img_hash = imagehash.hex_to_hash(next_hash)
                visual_similarity = 1.0 - (prev_img_hash - next_img_hash) / 64.0
            except:
                visual_similarity = 0.0
        
        # Analyze audio continuity
        prev_audio_props = audio_props(prev_path)
        next_audio_props = audio_props(next_path)
        
        audio_continuity = 0.5  # default
        if prev_audio_props and next_audio_props:
            # Compare volume levels and frequency characteristics
            vol_diff = abs(prev_audio_props.get('volume', 0) - next_audio_props.get('volume', 0))
            audio_continuity = max(0.0, 1.0 - vol_diff / 20.0)  # Normalize volume difference
        
        # Analyze scene energy and motion
        prev_scenes = detect_scene_scores(prev_path)
        next_scenes = detect_scene_scores(next_path)
        
        prev_energy = sum(s for _, s in prev_scenes) / max(1, len(prev_scenes))
        next_energy = sum(s for _, s in next_scenes) / max(1, len(next_scenes))
        
        energy_difference = abs(prev_energy - next_energy)
        energy_level = (prev_energy + next_energy) / 2
        
        # Analyze motion at transition points
        prev_motion = analyze_motion_appeal(prev_path, max(0, ffprobe_duration(prev_path) - 2), ffprobe_duration(prev_path))
        next_motion = analyze_motion_appeal(next_path, 0, min(2, ffprobe_duration(next_path)))
        
        motion_compatibility = 1.0 - abs(prev_motion - next_motion) / 10.0
        
        return {
            'visual_similarity': max(0.0, min(1.0, visual_similarity)),
            'audio_continuity': max(0.0, min(1.0, audio_continuity)),
            'energy_level': energy_level,
            'energy_difference': energy_difference,
            'motion_compatibility': max(0.0, min(1.0, motion_compatibility)),
            'prev_energy': prev_energy,
            'next_energy': next_energy
        }
    except Exception as e:
        # Fallback to basic analysis
        prev_scenes = detect_scene_scores(prev_path)
        next_scenes = detect_scene_scores(next_path)
        prev_energy = sum(s for _, s in prev_scenes) / max(1, len(prev_scenes))
        next_energy = sum(s for _, s in next_scenes) / max(1, len(next_scenes))
        
        return {
            'visual_similarity': 0.3,
            'audio_continuity': 0.5,
            'energy_level': (prev_energy + next_energy) / 2,
            'energy_difference': abs(prev_energy - next_energy),
            'motion_compatibility': 0.5,
            'prev_energy': prev_energy,
            'next_energy': next_energy
        }

def choose_transition(prev_path: str, next_path: str, opts: Dict, prev_dur: float, next_dur: float) -> str:
    """Enhanced transition selection based on comprehensive video analysis."""
    short_thresh = float(opts.get("jumpcut_threshold_s", 3.0))
    avoid_speech_cuts = bool(opts.get("no_cut_during_speech", True))
    # Check silence proximity near boundaries to avoid cutting during speech
    near_silence_window = float(opts.get("silence_snap_window_s", 0.6))
    prev_silences = []
    next_silences = []
    try:
        prev_silences = detect_silences(prev_path, silence_threshold_db=-40.0, min_silence_ms=500)
    except Exception:
        prev_silences = []
    try:
        next_silences = detect_silences(next_path, silence_threshold_db=-40.0, min_silence_ms=500)
    except Exception:
        next_silences = []

    def _has_silence_near_end(sils: List[Tuple[float,float]], dur: float, window: float) -> bool:
        for s_start, s_end in sils:
            if 0 <= (dur - s_end) <= window:
                return True
        return False

    def _has_silence_near_start(sils: List[Tuple[float,float]], window: float) -> bool:
        for s_start, s_end in sils:
            if 0 <= s_start <= window:
                return True
        return False

    prev_end_has_silence = _has_silence_near_end(prev_silences, prev_dur, near_silence_window)
    next_start_has_silence = _has_silence_near_start(next_silences, near_silence_window)
    
    # For very short clips, prefer cuts only if silence exists at both sides
    if min(prev_dur, next_dur) <= short_thresh:
        if avoid_speech_cuts and (not prev_end_has_silence or not next_start_has_silence):
            return "fade" if (prev_end_has_silence or next_start_has_silence) else "crossfade"
        return "cut"
    
    # Analyze transition compatibility
    compat = analyze_transition_compatibility(prev_path, next_path)
    
    # Decision matrix based on multiple factors
    visual_sim = compat['visual_similarity']
    audio_cont = compat['audio_continuity']
    energy_level = compat['energy_level']
    energy_diff = compat['energy_difference']
    motion_compat = compat['motion_compatibility']
    
    # High visual similarity suggests a cut or very subtle transition,
    # but avoid hard cuts if boundaries are inside speech
    if visual_sim > 0.7:
        if avoid_speech_cuts and (not prev_end_has_silence or not next_start_has_silence):
            return "fade"
        return "cut"
    
    # High energy with good motion compatibility - use dynamic transitions
    if energy_level > 4.0 and motion_compat > 0.6:
        if energy_diff < 1.0:  # Similar energy levels
            return "slideright" if visual_sim < 0.4 else "fade"
        else:  # Different energy levels
            return "slidedown" if compat['next_energy'] > compat['prev_energy'] else "slideup"
    
    # Medium energy with good audio continuity - use smooth transitions
    elif energy_level > 2.0 and audio_cont > 0.6:
        if visual_sim > 0.4:
            return "fade"
        else:
            return "crossfade" if motion_compat > 0.5 else "fade"
    
    # Low energy or poor compatibility - use gentle transitions
    elif energy_level > 1.0:
        if audio_cont > 0.7:
            return "fade"
        else:
            return "fadeblack"
    
    # Very low energy or major discontinuity - use black transition
    else:
        return "fadeblack"

def export_thumbnails(input_path: str, out_dir: str, max_count: int = 3) -> list:
    """Export up to max_count evenly spaced thumbnails from the video."""
    os.makedirs(out_dir, exist_ok=True)
    thumbs = []
    try:
        dur = ffprobe_duration(input_path)
        if dur <= 0:
            return []
        step = dur / (max_count + 1)
        for i in range(1, max_count + 1):
            ts = step * i
            outp = os.path.join(out_dir, f"thumb_{i:02d}.jpg")
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-y",
                "-ss", str(ts), "-i", input_path,
                "-frames:v", "1",
                "-q:v", "2",
                outp
            ]
            run(cmd, check=True)
            if os.path.exists(outp):
                thumbs.append(outp)
        return thumbs
    except Exception:
        return thumbs


# =========================
# ProcessorThread (QThread) - replaced with Pro pipeline
# =========================

def apply_video_filters(input_path: str, output_path: str, video_filters: List[str], audio_copy: bool = True) -> bool:
    """Enhanced video filter application with intelligent processing and quality optimization."""
    if not os.path.exists(input_path):
        return False
        
    if not video_filters:
        return shutil.copy(input_path, output_path) if os.path.exists(input_path) else False
    
    # Enhanced filter processing with automatic quality detection
    enhanced_filters = []
    
    # Add automatic enhancement filters based on content analysis
    auto_enhance_filters = get_auto_enhancement_filters(input_path)
    enhanced_filters.extend(auto_enhance_filters)
    
    # Add user-specified filters
    enhanced_filters.extend(video_filters)
    
    # Optimize filter chain for better performance
    optimized_filters = optimize_filter_chain(enhanced_filters)
    
    filter_complex_str = ""
    vf_chain_str = ""
    
    # Separate complex filters from simple ones
    logo_filter = None
    simple_filters = []
    
    for f in optimized_filters:
        if f.startswith("[1]") or "overlay" in f:
            logo_filter = f
        else:
            simple_filters.append(f)
            
    if logo_filter:
        filter_complex_str = logo_filter
        if simple_filters:
            filter_complex_str += f",[v]{','.join(simple_filters)}[v_out]"
    elif simple_filters:
        vf_chain_str = ",".join(simple_filters)
        
    args = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-i", input_path,
    ]
    
    if filter_complex_str:
        args += ["-filter_complex", filter_complex_str, "-map", "[v_out]" if simple_filters and logo_filter else "[v]"]
    elif vf_chain_str:
        args += ["-vf", vf_chain_str]
    
    if audio_copy and has_audio_stream(input_path):
        args += ["-map", "0:a", "-c:a", "copy"]
    
    # Enhanced encoding settings for better quality
    args += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", 
        "-preset", "medium", "-crf", "20",  # Better quality settings
        "-profile:v", "high", "-level", "4.1",
        "-movflags", "+faststart", "-y", output_path
    ]
    
    run(args, check=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0

def get_auto_enhancement_filters(video_path: str) -> List[str]:
    """Automatically determine enhancement filters based on video analysis."""
    filters = []
    
    try:
        # Analyze video properties
        width, height = ffprobe_dimensions(video_path)
        
        # Add denoising for lower quality videos
        if width < 1280 or height < 720:
            filters.append("hqdn3d=2:1:2:1")  # Denoise filter
            
        # Add sharpening for soft videos
        filters.append("unsharp=5:5:0.8:3:3:0.4")  # Subtle sharpening
        
        # Color enhancement
        filters.append("eq=contrast=1.1:brightness=0.02:saturation=1.1")  # Slight color boost
        
        # Stabilization for shaky footage (light)
        filters.append("deshake=x=-1:y=-1:w=-1:h=-1:rx=16:ry=16")
        
        return filters
        
    except Exception:
        # Fallback basic enhancement
        return ["unsharp=5:5:0.5:3:3:0.3", "eq=contrast=1.05:saturation=1.05"]

def optimize_filter_chain(filters: List[str]) -> List[str]:
    """Optimize filter chain for better performance and quality."""
    if not filters:
        return filters
        
    optimized = []
    
    # Group similar filters together for efficiency
    color_filters = []
    spatial_filters = []
    other_filters = []
    
    for f in filters:
        if any(keyword in f for keyword in ['eq=', 'colorbalance', 'hue', 'curves']):
            color_filters.append(f)
        elif any(keyword in f for keyword in ['unsharp', 'hqdn3d', 'deshake', 'scale']):
            spatial_filters.append(f)
        else:
            other_filters.append(f)
    
    # Optimal order: spatial -> color -> other
    optimized.extend(spatial_filters)
    optimized.extend(color_filters)
    optimized.extend(other_filters)
    
    return optimized

class ProcessorThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(str)

    def __init__(self, input_paths: List[str], out_dir: str, opts: dict):
        super().__init__()
        self.input_paths = input_paths[:]  # ordered list
        self.out_dir = out_dir
        self.opts = dict(opts or {})
        # default pro options if missing
        self.opts.setdefault("avoid_repeats", True)
        self.opts.setdefault("auto_branding", True)
        self.opts.setdefault("broadcast_chain", True)
        self.opts.setdefault("cta_text", "Subscribe for more!")
        self.opts.setdefault("presenter_name", "")
        self.opts.setdefault("hook_text", "You need to see this!")
        self._stop = False
        self._current_process = None  # Track current subprocess for immediate termination

    def request_stop(self):
        self._stop = True
        # Immediately terminate any running subprocess
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    self._current_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    self._current_process.kill()
                    self._current_process.wait()
            except Exception as e:
                print(f"[DEBUG] Error terminating process: {e}")

    def check_stop(self) -> bool:
        return self._stop or self.isInterruptionRequested()

    def run_tracked_subprocess(self, cmd: List[str], timeout: int = 7200, check: bool = False) -> subprocess.CompletedProcess:
        """Run a subprocess with tracking for immediate cancellation."""
        if self.check_stop():
            raise subprocess.CalledProcessError(1, cmd, "Process cancelled")
        
        try:
            parts = cmd
            print(f"[DEBUG] run_tracked: Executing: {' '.join(parts)}")
            
            # Start the process and track it
            self._current_process = subprocess.Popen(
                parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = self._current_process.communicate(timeout=timeout)
                returncode = self._current_process.returncode
                
                # Clear the tracked process
                self._current_process = None
                
                if stderr:
                    truncated = (stderr[:1000] + '...') if len(stderr) > 1000 else stderr
                    print(f"[DEBUG] run_tracked: STDERR: {truncated}")
                
                result = subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
                
                if check and returncode != 0:
                    raise subprocess.CalledProcessError(returncode, cmd, stdout, stderr)
                
                return result
                
            except subprocess.TimeoutExpired:
                self._current_process.terminate()
                try:
                    self._current_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._current_process.kill()
                    self._current_process.wait()
                self._current_process = None
                raise
                
        except Exception as e:
            self._current_process = None
            if self.check_stop():
                print(f"[DEBUG] Process cancelled: {' '.join(cmd)}")
                raise subprocess.CalledProcessError(1, cmd, "Process cancelled")
            print(f"[DEBUG] run_tracked: Exception: {e}")
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr=str(e))

    def emit_log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.log.emit(f"[{ts}] {text}")

    def run(self):
        try:
            if not have_ffmpeg():
                self.emit_log("ERROR: ffmpeg/ffprobe not found on PATH.")
                self.finished.emit("Error - ffmpeg missing")
                return

            os.makedirs(self.out_dir, exist_ok=True)
            self.emit_log(f"[PRO] Output folder: {self.out_dir}")

            if self.check_stop():
                self.finished.emit("Canceled")
                return

            # First, combine all selected videos in order (top to bottom)
            self.emit_log("[PRO] Combining all selected videos in order...")
            
            # Filter out missing files
            valid_inputs = []
            for src in self.input_paths:
                if os.path.exists(src):
                    valid_inputs.append(src)
                else:
                    self.emit_log(f"[PRO] Skipping missing file: {src}")
            
            if not valid_inputs:
                self.finished.emit("Error: No valid input files found.")
                return
            
            # Combine all videos into a single file
            combined_video_path = os.path.join(self.out_dir, "combined_input.mp4")
            self.emit_log(f"[PRO] Combining {len(valid_inputs)} videos into single file...")
            
            if not combine_videos_in_order(valid_inputs, combined_video_path, self.emit_log):
                self.finished.emit("Error: Failed to combine input videos.")
                return
            
            self.emit_log(f"[PRO] Successfully combined videos: {combined_video_path}")
            self.progress.emit(10)
            
            # Now standardize the combined video to mezz format (1080p60, yuv420p, AAC)
            self.emit_log("[PRO] Standardizing combined video (1080p60, yuv420p, AAC)...")
            mezz_path = os.path.join(self.out_dir, "mezz_combined.mp4")
            
            if self.check_stop():
                self.finished.emit("Canceled")
                return
                
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-i", combined_video_path,
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                      "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p",
                "-r", "60",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-q:a", "2", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", "-y", mezz_path
            ]
            run(cmd, check=True)
            
            if not (os.path.exists(mezz_path) and os.path.getsize(mezz_path) > 0):
                self.finished.emit("Error: Failed to standardize combined video.")
                return
                
            self.emit_log(f"[PRO] Standardized combined video: {mezz_path}")
            
            # Detect introduction segment in the combined video
            self.emit_log("[PRO] Detecting introduction segment in combined video...")
            intro_start, intro_end = detect_introduction_segment(mezz_path, max_intro_duration=60.0, min_intro_duration=30.0)
            self.emit_log(f"[PRO] Introduction segment detected: {intro_start:.2f}s - {intro_end:.2f}s (preserving at least 30s)")
            
            # Trim long silences while preserving the intro
            if self.opts.get("trim_silences", True):
                self.emit_log("[PRO] Trimming long silences while preserving introduction...")
                silence_trimmed_path = os.path.join(self.out_dir, "silence_trimmed.mp4")
                if trim_long_silences(mezz_path, silence_trimmed_path, 
                                    silence_threshold_db=float(self.opts.get("silence_db", -40)),
                                    min_silence_ms=int(self.opts.get("min_sil_ms", 1000))):
                    mezz_path = silence_trimmed_path
                    self.emit_log(f"[PRO] Successfully trimmed silences while preserving introduction")
                else:
                    self.emit_log(f"[PRO] Failed to trim silences, continuing with original video")
            else:
                self.emit_log("[PRO] Silence trimming disabled, skipping")
                
            mezz = [mezz_path]  # Single combined video for processing
            self.progress.emit(15)

            # Per-clip analysis -> candidates + transcripts
            self.emit_log("[PRO] Analyzing combined video (silence, scene, transcript, candidates)...")
            all_candidates: List[Dict] = []
            transcript_map: Dict[Tuple[float,float], str] = {}
            
            # Get target duration for AI segment length analysis
            min_total = float(self.opts.get("min_total_length", 0.0)) or 0.0
            max_total = float(self.opts.get("max_total_length", 120.0)) or 120.0
            target_total = (min_total + max_total) / 2 if min_total > 0 else max_total
            
            # Process the single combined video
            mclip = mezz[0]  # Single combined video
            if self.check_stop():
                self.finished.emit("Canceled")
                return
            self.emit_log("[PRO] Finding candidates in combined video...")
            
            # Determine segment lengths (AI or manual)
            if self.opts.get("ai_segment_lengths", False):
                ai_min_len, ai_max_len = analyze_optimal_segment_lengths(mclip, target_total)
                self.emit_log(f"[PRO] AI determined segment lengths: {ai_min_len}s - {ai_max_len}s")
                min_len = ai_min_len
                max_len = ai_max_len
            else:
                min_len = float(self.opts.get("min_seg_s", 6.0))
                max_len = float(self.opts.get("max_seg_s", 18.0))
            
            self.emit_log(f"[PRO] Building highlight candidates (min: {min_len}s, max: {max_len}s)...")
            cands = build_highlight_candidates(
                mclip,
                keywords=self.opts.get("keywords") or [],
                silence_db=float(self.opts.get("silence_db", -40)),
                min_sil_ms=int(self.opts.get("min_sil_ms", 600)),
                min_len=min_len,
                max_len=max_len,
                use_ai_analysis=self.opts.get("use_ai_analysis", True),
            )
            total_candidate_duration = sum(c["end"] - c["start"] for c in cands)
            self.emit_log(f"[PRO] Found {len(cands)} candidates (total: {int(total_candidate_duration)}s available)")
            if len(cands) < 20:
                self.emit_log(f"[PRO] ⚠️  Low candidate count may affect ability to reach target duration")
            elif total_candidate_duration < min_total * 0.8:
                self.emit_log(f"[PRO] ⚠️  Available content ({int(total_candidate_duration)}s) may be insufficient for target ({int(min_total)}s)")
            # attach transcripts if whisper available
            segs = []
            try:
                segs = transcribe_segments(
                    mclip,
                    model_size=self.opts.get("model", "small"),
                    language=self.opts.get("language", "en")  # "en" or "ro"
                )

            except Exception:
                segs = []
            for c in cands:
                a = c["start"]; b = c["end"]
                joined = []
                for s in segs:
                    if not (s["end"] < a or s["start"] > b):
                        joined.append(s.get("text",""))
                txt = " ".join(joined).strip()
                c["text"] = txt
                transcript_map[(round(a,2), round(b,2))] = txt
                c["source"] = mclip
                all_candidates.append(c)
            if not cands:
                dur = ffprobe_duration(mclip)
                a = max(0.0, dur / 2 - 7.5)
                b = min(dur, a + 15.0)
                c = {"start": a, "end": b, "score": 0.1, "text": "", "why": "fallback", "source": mclip}
                all_candidates.append(c)
            self.progress.emit(20)

            if self.check_stop():
                self.finished.emit("Canceled")
                return

            # Perform deduplication after videos are combined
            should_deduplicate = self.opts.get("avoid_repeats", True)
            if should_deduplicate:
                self.emit_log("[PRO] Deduplicating candidates (semantic + visual optional)...")
                unique = []
                seen_texts = []
                seen_phashes = set()
                for c in all_candidates:
                    txt = (c.get("text") or "").lower().strip()
                    skip = False
                    for t in seen_texts:
                        if t and text_similarity(t, txt) > TEXT_SIMILARITY_THRESHOLD:
                            skip = True
                            break
                    if skip:
                        continue
                    ph = None
                    try:
                        ph = frame_phash(c["source"], t=max(0.5, c["start"]+0.5))
                    except Exception:
                        ph = None
                    if ph and ph in seen_phashes:
                        continue
                    unique.append(c)
                    if txt:
                        seen_texts.append(txt)
                    if ph:
                        seen_phashes.add(ph)
                all_candidates = unique
                self.emit_log(f"[PRO] {len(all_candidates)} candidates remain after dedupe.")
            

            if self.check_stop():
                self.finished.emit("Canceled")
                return

            # Target duration already calculated above for AI segment length analysis
            self.emit_log(f"[PRO] AI-driven segment selection to target between {int(min_total)}s and {int(max_total)}s (target: {int(target_total)}s)...")
            
            # Use intelligent selection for multiple videos
            if len(mezz) > 1 and self.opts.get("multi_video_analysis", True):
                self.emit_log(f"[PRO] Analyzing {len(mezz)} input videos for best segments...")
                self.emit_log(f"[PRO] Total candidates available: {len(all_candidates)}")
                
                # Calculate total potential duration from all candidates
                total_potential_duration = sum(c["end"] - c["start"] for c in all_candidates)
                self.emit_log(f"[PRO] Total potential duration from all candidates: {int(total_potential_duration)}s")
                self.emit_log(f"[PRO] Target duration: {int(target_total)}s")
                
                if total_potential_duration < target_total:
                    self.emit_log(f"[PRO] ⚠️  WARNING: Total potential duration ({int(total_potential_duration)}s) is below target ({int(target_total)}s)")
                    self.emit_log(f"[PRO] This may result in shorter final video than desired")
                
                ordered_segments = select_best_segments_from_multiple_videos(all_candidates, target_total)
                if not ordered_segments:
                    self.emit_log("[PRO] AI selection failed; using top chronological picks.")
                    ordered_segments = sorted(all_candidates, key=lambda x: x.get("score",0.0), reverse=True)[:6]
            else:
                # Single video - use traditional storyline building
                self.emit_log(f"[PRO] Single video processing with {len(all_candidates)} candidates...")
                # Calculate total potential duration from all candidates
                total_potential_duration = sum(c["end"] - c["start"] for c in all_candidates)
                self.emit_log(f"[PRO] Total potential duration from all candidates: {int(total_potential_duration)}s")
                self.emit_log(f"[PRO] Target duration: {int(target_total)}s")
                if total_potential_duration < target_total:
                    self.emit_log(f"[PRO] ⚠️  WARNING: Total potential duration ({int(total_potential_duration)}s) is below target ({int(target_total)}s)")
                    self.emit_log(f"[PRO] This may result in shorter final video than desired")
                ordered_segments = build_storyline_from_candidates(all_candidates, transcript_map, total_target=target_total)
                if not ordered_segments:
                    self.emit_log("[PRO] Storyline failed; using top chronological picks.")
                    ordered_segments = sorted(all_candidates, key=lambda x: x.get("score",0.0), reverse=True)[:6]

            # Apply speech-aware boundary adjustments to prevent cutting during speech
            if ordered_segments:
                self.emit_log("[PRO] Applying speech-aware boundary adjustments to prevent cutting during speech...")
                # Group segments by source video for efficient processing
                segments_by_source = {}
                for seg in ordered_segments:
                    source = seg.get("source", mezz_path)
                    if source not in segments_by_source:
                        segments_by_source[source] = []
                    segments_by_source[source].append(seg)
                
                # Apply adjustments per source video
                adjusted_segments = []
                for source, segs in segments_by_source.items():
                    adjusted = adjust_segment_boundaries_for_speech(source, segs, max_extend=4.0)
                    adjusted_segments.extend(adjusted)
                
                # Update ordered_segments with adjusted boundaries
                ordered_segments = sorted(adjusted_segments, key=lambda x: (x.get("source", ""), x["start"]))
                
                # Log adjustments made with detailed information
                adjustments_made = sum(1 for seg in ordered_segments if seg.get("duration_adjusted", 0) != 0)
                phrase_adjustments = sum(1 for seg in ordered_segments if seg.get("start_adjusted") or seg.get("end_adjusted"))
                
                if adjustments_made > 0:
                    self.emit_log(f"[PRO] ✓ Adjusted {adjustments_made} segment boundaries to avoid cutting during speech")
                    if phrase_adjustments > 0:
                        self.emit_log(f"[PRO] ✓ Applied phrase-aware boundary detection to {phrase_adjustments} segments")
                        # Log specific adjustments for debugging
                        for seg in ordered_segments:
                            if seg.get("start_adjusted") or seg.get("end_adjusted"):
                                adjustments = []
                                if seg.get("start_adjusted"):
                                    adjustments.append(f"start {seg['start_adjusted']}")
                                if seg.get("end_adjusted"):
                                    adjustments.append(f"end {seg['end_adjusted']}")
                                self.emit_log(f"[PRO]   Segment {seg['start']:.1f}s: {', '.join(adjustments)}")
                else:
                    self.emit_log("[PRO] ✓ No speech boundary adjustments needed")
            
            # Ensure at least min_total length by adding more candidates if needed
            total_dur = sum(seg["end"] - seg["start"] for seg in ordered_segments)
            self.emit_log(f"[PRO] Selection after speech adjustments: {int(total_dur)}s from {len(ordered_segments)} segments")
            
            if total_dur < min_total:
                self.emit_log(f"[PRO] Storyline too short ({int(total_dur)}s). Adding more highlights until ≥ {int(min_total)}s...")
                
                # First pass: Add non-overlapping segments
                extra = sorted(all_candidates, key=lambda x: (-x.get("score",0.0), x["start"]))
                added_count = 0
                for c in extra:
                    if c not in ordered_segments:
                        # check overlap
                        overlap = any(not (c["end"] <= o["start"] or c["start"] >= o["end"]) for o in ordered_segments)
                        if overlap:
                            continue
                        ordered_segments.append(c)
                        total_dur += c["end"] - c["start"]
                        added_count += 1
                        self.emit_log(f"[PRO] Added segment {added_count}: {c['start']:.1f}-{c['end']:.1f}s (total: {int(total_dur)}s)")
                        if total_dur >= min_total:
                            break
                
                # Second pass: If still too short, allow minimal overlap (up to 2 seconds)
                if total_dur < min_total:
                    self.emit_log(f"[PRO] Still too short ({int(total_dur)}s). Allowing minimal overlap to reach {int(min_total)}s...")
                    for c in extra:
                        if c not in ordered_segments:
                            # Check for excessive overlap (more than 2 seconds)
                            max_overlap = 2.0
                            overlaps_too_much = False
                            for o in ordered_segments:
                                overlap_start = max(c["start"], o["start"])
                                overlap_end = min(c["end"], o["end"])
                                if overlap_end > overlap_start and (overlap_end - overlap_start) > max_overlap:
                                    overlaps_too_much = True
                                    break
                            
                            if not overlaps_too_much:
                                ordered_segments.append(c)
                                total_dur += c["end"] - c["start"]
                                added_count += 1
                                self.emit_log(f"[PRO] Added overlapping segment {added_count}: {c['start']:.1f}-{c['end']:.1f}s (total: {int(total_dur)}s)")
                                if total_dur >= min_total:
                                    break
                
                # Third pass: If still too short, be very aggressive and allow more overlap
                if total_dur < min_total:
                    self.emit_log(f"[PRO] Still too short ({int(total_dur)}s). Being aggressive to reach {int(min_total)}s...")
                    for c in extra:
                        if c not in ordered_segments:
                            # Allow up to 5 seconds overlap for very long targets
                            max_overlap = 5.0
                            overlaps_too_much = False
                            for o in ordered_segments:
                                overlap_start = max(c["start"], o["start"])
                                overlap_end = min(c["end"], o["end"])
                                if overlap_end > overlap_start and (overlap_end - overlap_start) > max_overlap:
                                    overlaps_too_much = True
                                    break
                            
                            if not overlaps_too_much:
                                ordered_segments.append(c)
                                total_dur += c["end"] - c["start"]
                                added_count += 1
                                self.emit_log(f"[PRO] Added aggressive segment {added_count}: {c['start']:.1f}-{c['end']:.1f}s (total: {int(total_dur)}s)")
                                if total_dur >= min_total:
                                    break
                
                # Fourth pass: If still too short, lower quality threshold and add any remaining segments
                if total_dur < min_total:
                    self.emit_log(f"[PRO] Still too short ({int(total_dur)}s). Lowering quality threshold for fallback segments...")
                    # Sort all candidates by start time instead of score for better coverage
                    fallback_candidates = sorted(all_candidates, key=lambda x: x["start"])
                    for c in fallback_candidates:
                        if c not in ordered_segments:
                            # Allow significant overlap for fallback (up to 8 seconds)
                            max_overlap = 8.0
                            overlaps_too_much = False
                            for o in ordered_segments:
                                overlap_start = max(c["start"], o["start"])
                                overlap_end = min(c["end"], o["end"])
                                if overlap_end > overlap_start and (overlap_end - overlap_start) > max_overlap:
                                    overlaps_too_much = True
                                    break
                            
                            if not overlaps_too_much:
                                ordered_segments.append(c)
                                total_dur += c["end"] - c["start"]
                                added_count += 1
                                self.emit_log(f"[PRO] Added fallback segment {added_count}: {c['start']:.1f}-{c['end']:.1f}s (total: {int(total_dur)}s)")
                                if total_dur >= min_total:
                                    break
                
                # Final emergency fallback: Create longer segments from existing videos if needed
                if total_dur < min_total:
                    self.emit_log(f"[PRO] ⚠️  Emergency fallback: Creating longer segments to reach minimum duration...")
                    shortage = min_total - total_dur
                    self.emit_log(f"[PRO] Need {int(shortage)}s more content. Extending existing segments...")
                    
                    # Try to extend existing segments or create new ones from source videos
                    for video_path in mezz:
                        if total_dur >= min_total:
                            break
                        video_duration = ffprobe_duration(video_path)
                        if video_duration > 30:  # Only use videos longer than 30s
                            # Create a longer fallback segment from middle of video
                            segment_length = min(60.0, shortage, video_duration - 10)  # Up to 60s or remaining shortage
                            start_time = max(5.0, (video_duration - segment_length) / 2)
                            end_time = start_time + segment_length
                            
                            fallback_segment = {
                                "start": start_time,
                                "end": end_time,
                                "score": 0.05,  # Very low score to indicate fallback
                                "text": "[Emergency fallback content]",
                                "why": "emergency_fallback",
                                "source": video_path
                            }
                            
                            ordered_segments.append(fallback_segment)
                            total_dur += segment_length
                            shortage -= segment_length
                            self.emit_log(f"[PRO] Added emergency segment: {start_time:.1f}-{end_time:.1f}s from {os.path.basename(video_path)} (total: {int(total_dur)}s)")
                            
                            if shortage <= 0:
                                break
                
                if total_dur < min_total:
                    self.emit_log(f"[PRO] ⚠️  WARNING: Could not reach minimum duration despite all fallbacks. Final: {int(total_dur)}s (target: {int(min_total)}s)")
                    self.emit_log(f"[PRO] Consider reducing min_total_length or using longer source videos.")
                else:
                    self.emit_log(f"[PRO] ✅ Successfully reached minimum duration: {int(total_dur)}s")
            
            # Also ensure we don't exceed max_total by too much
            if total_dur > max_total * 1.2:  # Allow 20% overflow
                self.emit_log(f"[PRO] Trimming selection to avoid excessive length (current: {int(total_dur)}s, max: {int(max_total)}s)")
                # Sort by score and keep top segments until we're under max
                ordered_segments.sort(key=lambda x: x.get("score", 0.0), reverse=True)
                trimmed_segments = []
                current_dur = 0.0
                for seg in ordered_segments:
                    seg_dur = seg["end"] - seg["start"]
                    if current_dur + seg_dur <= max_total:
                        trimmed_segments.append(seg)
                        current_dur += seg_dur
                    else:
                        break
                ordered_segments = trimmed_segments
                total_dur = current_dur
                self.emit_log(f"[PRO] Trimmed to {int(total_dur)}s from {len(ordered_segments)} segments")

            # Final sort by time
            ordered_segments.sort(key=lambda x: x["start"])
            
            # Final duration check and logging
            final_duration = sum(seg["end"] - seg["start"] for seg in ordered_segments)
            self.emit_log(f"[PRO] Final selection: {len(ordered_segments)} segments, total duration: {int(final_duration)}s")
            if min_total > 0 and final_duration < min_total:
                self.emit_log(f"[PRO] ⚠️  WARNING: Final duration ({int(final_duration)}s) is below minimum target ({int(min_total)}s)")
            elif final_duration > max_total * 1.1:
                self.emit_log(f"[PRO] ⚠️  WARNING: Final duration ({int(final_duration)}s) exceeds maximum target ({int(max_total)}s) by more than 10%")
            else:
                self.emit_log(f"[PRO] ✅ Duration target achieved: {int(final_duration)}s (target: {int(min_total)}s - {int(max_total)}s)")

            # Render selected trimmed parts
            self.emit_log("[PRO] Rendering selected parts...")
            tmp_dir = os.path.join(self.out_dir, f"_pro_tmp_{uuid.uuid4().hex[:6]}")
            os.makedirs(tmp_dir, exist_ok=True)
            rendered_parts: List[str] = []
            for i, seg in enumerate(ordered_segments, 1):
                if self.check_stop():
                    self.finished.emit("Canceled")
                    return
                s = seg["start"]; e = seg["end"]
                src = seg["source"]
                current_vf_extra: List[str] = []
                # lower third if branding enabled
                if self.opts.get("auto_branding", True):
                    name = self.opts.get("presenter_name", "")
                    title = seg.get("why", "")
                    lt_filter = get_lower_third_filter(name=name, title=title)
                    if lt_filter:
                        current_vf_extra.append(lt_filter)
                
                outp = os.path.join(tmp_dir, f"part_{i:02d}.mp4")
                ok = trim_out(src, s, e, outp, vf_extra=",".join(current_vf_extra) if current_vf_extra else None)
                if ok:
                    rendered_parts.append(outp)
                    self.emit_log(f"[PRO] Rendered part {i}: {outp} ({s:.1f}-{e:.1f})")
                else:
                    self.emit_log(f"[PRO] Failed to render part {i} ({s:.1f}-{e:.1f})")
                self.progress.emit(int(40 + 30 * (i / max(1, len(ordered_segments)))))

            if not rendered_parts:
                self.finished.emit("Error: No rendered parts.")
                return

            # Create hook intro: short, animated title overlay
            self.emit_log("[PRO] Creating hook intro...")
            hook_clip = rendered_parts[0]
            hook_clip_dur = ffprobe_duration(hook_clip)
            hk_dur = min(10.0, hook_clip_dur)
            hook_trim = os.path.join(tmp_dir, "hook_trim.mp4")
            trim_out(hook_clip, 0.0, min(hk_dur, 8.0), hook_trim)
            title_text = self.opts.get("hook_text", "You need to see this!")
            hook_animated = os.path.join(tmp_dir, "hook_animated.mp4")
            if add_animated_title(hook_trim, title_text, hook_animated):
                first_segment = hook_animated
            else:
                first_segment = hook_trim

            # Assemble timeline with adaptive transitions - OPTIMIZED VERSION
            self.emit_log("[PRO] Assembling timeline with optimized transitions...")
            # Batch process transitions for better performance
            if len(rendered_parts) <= 1:
                assembled = first_segment
            else:
                # Use batch processing for better performance
                assembled = self.batch_assemble_timeline(rendered_parts, tmp_dir, first_segment)
                if not assembled:
                    self.emit_log("[PRO] Batch assembly failed, falling back to simple concat...")
                    # Fallback: simple concatenation without transitions
                    assembled = self.simple_concat_timeline(rendered_parts, tmp_dir, first_segment)

            self.progress.emit(78)

            # Background music: prefer provided file; otherwise generate AI music by default
            music_fp = self.opts.get("music_path")
            if music_fp and isinstance(music_fp, str) and os.path.exists(music_fp):
                self.emit_log("[PRO] Adding background music with ducking...")
                music_out = os.path.join(self.out_dir, "with_music.mp4")
                if add_music_ducked(assembled, music_fp, music_out):
                    assembled = music_out
                    self.emit_log("[PRO] BGM added and ducked.")
                else:
                    self.emit_log("[PRO] BGM ducking failed; continuing without music.")
            else:
                self.emit_log("[PRO] Generating AI music based on content analysis...")
                ai_music_out = os.path.join(self.out_dir, "with_ai_music.mp4")
                if add_ai_generated_music(assembled, ordered_segments, ai_music_out):
                    assembled = ai_music_out
                    self.emit_log("[PRO] AI-generated music added successfully.")
                else:
                    self.emit_log("[PRO] AI music generation failed; continuing without music.")

            # Broadcast audio chain
            if self.opts.get("broadcast_chain", True):
                self.emit_log("[PRO] Applying broadcast audio chain...")
                bc_out = os.path.join(self.out_dir, "broadcast_audio.mp4")
                if broadcast_audio_chain(assembled, bc_out):
                    assembled = bc_out
                    self.emit_log("[PRO] Broadcast chain applied.")
                else:
                    self.emit_log("[PRO] Broadcast chain failed; keeping existing audio.")

            # Logo watermark
            if self.opts.get("auto_branding", True):
                logo = self.opts.get("logo_path", "")
                if logo and os.path.exists(logo):
                    self.emit_log("[PRO] Overlaying logo...")
                    wm_out = os.path.join(self.out_dir, "with_logo.mp4")
                    if overlay_logo(assembled, logo, wm_out, position=self.opts.get("logo_pos", "tr")):
                        assembled = wm_out

            # CTA card append
            if self.opts.get("auto_branding", True):
                # pick outro text based on language
                if self.opts.get("language", "en") == "ro":
                    outro_text = "Abonează-te pentru mai mult!"
                else:
                    outro_text = "Subscribe for more!"

                cta_mp4 = generate_cta_clip(self.out_dir, text=self.opts.get("cta_text", outro_text))

                if cta_mp4 and os.path.exists(cta_mp4):
                    self.emit_log("[PRO] Appending CTA end-screen...")
                    tmp_final = os.path.join(self.out_dir, "final_with_cta.mp4")
                    if concat_hard_cut(assembled, cta_mp4, tmp_final):
                        assembled = tmp_final

            self.progress.emit(92)

            # Exports in requested aspects
            self.emit_log("[PRO] Exporting formats...")
            exp_map = {
                "16:9": ("export_16x9.mp4", "16:9", 1920),
                "9:16": ("export_9x16.mp4", "9:16", 1080),
                "1:1": ("export_1x1.mp4", "1:1", 1080),
            }
            for asp in self.opts.get("exports", ["16:9"]):
                if asp in exp_map:
                    name, a, w = exp_map[asp]
                    outp = os.path.join(self.out_dir, name)
                    ok = export_aspect(assembled, outp, aspect=a, width=w)
                    if ok:
                        self.emit_log(f"[PRO] Exported {a}: {outp}")
                    else:
                        self.emit_log(f"[PRO] Export {a} failed.")

            # Thumbnails
            self.emit_log("[PRO] Generating thumbnails...")
            thumbs = export_thumbnails(assembled, os.path.join(self.out_dir, "thumbnails"), max_count=3)
            for t in thumbs:
                self.emit_log(f"[PRO] Thumbnail: {t}")

            self.progress.emit(100)
            self.emit_log("[PRO] All done.")
            self.finished.emit(f"OK: pro outputs in {self.out_dir}")

            # === Ensure a clear final output file ===
            final_output = os.path.join(self.out_dir, "final_output.mp4")
            # If the last step was not broadcast audio, run it now
            if not (assembled.endswith("broadcast_audio.mp4") and os.path.exists(assembled)):
                self.emit_log(f"[PRO] Finalizing: applying broadcast audio chain to {assembled}...")
                if not broadcast_audio_chain(assembled, final_output):
                    self.emit_log("[ERROR] Broadcast audio processing failed, copying assembled file as final output.")
                    shutil.copy(assembled, final_output)
                else:
                    self.emit_log(f"[PRO] Final video with broadcast audio saved as: {final_output}")
            else:
                # Already broadcast audio, just copy/rename
                shutil.copy(assembled, final_output)
                self.emit_log(f"[PRO] Final video saved as: {final_output}")

            # === Ensure last segment does not end during speech ===
            if ordered_segments:
                last_seg = ordered_segments[-1]
                video_path = last_seg.get("source")
                orig_end = last_seg["end"]
                max_extend = 10.0  # seconds
                new_end = orig_end
                # Try transcript first
                tx = transcribe_segments(video_path)
                if tx:
                    # Find the last transcript segment that starts after orig_end but within max_extend
                    for seg in tx:
                        if seg["start"] >= orig_end and seg["start"] <= orig_end + max_extend:
                            # If this segment ends with a sentence-ending punctuation, use its end
                            if seg["text"].strip().endswith(('.', '!', '?')):
                                new_end = min(seg["end"], orig_end + max_extend)
                                break
                # If no transcript or no sentence end found, try silence detection
                if new_end == orig_end:
                    silences = detect_silences(video_path)
                    for s_start, s_end in silences:
                        if s_start >= orig_end and s_start <= orig_end + max_extend:
                            new_end = s_start
                            break
                # Only extend, never shorten
                if new_end > orig_end:
                    self.emit_log(f"[PRO] Extending last segment from {orig_end:.2f}s to {new_end:.2f}s to avoid ending during speech.")
                    ordered_segments[-1]["end"] = new_end
                else:
                    self.emit_log(f"[PRO] Last segment end unchanged at {orig_end:.2f}s.")

        except Exception as exc:
            self.emit_log(f"[PRO] Exception: {exc}")
            self.finished.emit(f"Error: {exc}")

    def batch_assemble_timeline(self, rendered_parts: List[str], tmp_dir: str, first_segment: str) -> Optional[str]:
        """Optimized batch timeline assembly with minimal transitions"""
        try:
            # For very long videos, limit transitions to improve performance
            max_transitions = min(20, len(rendered_parts) // 3)  # Max 20 transitions or 1 per 3 segments
            
            if len(rendered_parts) <= max_transitions:
                # Use simple concatenation for shorter videos
                return self.simple_concat_timeline(rendered_parts, tmp_dir, first_segment)
            
            # Smart transition selection: only add transitions at major scene changes
            transition_points = self.select_smart_transition_points(rendered_parts, max_transitions)
            
            # Batch process with selected transitions
            return self.process_smart_transitions(rendered_parts, transition_points, tmp_dir, first_segment)
            
        except Exception as e:
            self.emit_log(f"[PRO] Batch assembly error: {e}")
            return None
    
    def select_smart_transition_points(self, rendered_parts: List[str], max_transitions: int) -> List[int]:
        """Select optimal points for transitions based on content analysis"""
        if len(rendered_parts) <= 2:
            return []
        
        # Analyze content for natural break points
        break_points = []
        
        # Always add transition at the beginning (after hook)
        break_points.append(1)
        
        # Add transitions at major content changes (every 3-5 segments)
        step = max(3, len(rendered_parts) // max_transitions)
        for i in range(step, len(rendered_parts) - 1, step):
            if i not in break_points:
                break_points.append(i)
        
        # Ensure we don't exceed max transitions
        if len(break_points) > max_transitions:
            break_points = break_points[:max_transitions]
        
        return sorted(break_points)
    
    def process_smart_transitions(self, rendered_parts: List[str], transition_points: List[int], 
                                tmp_dir: str, first_segment: str) -> Optional[str]:
        """Process timeline with smart transitions at selected points"""
        try:
            current = first_segment
            current_dur = ffprobe_duration(first_segment)
            
            for i in range(1, len(rendered_parts)):
                if self.check_stop():
                    self.finished.emit("Canceled")
                    return None
                
                next_segment = rendered_parts[i]
                next_dur = ffprobe_duration(next_segment)
                
                # Only add transition if this is a selected transition point
                if i in transition_points:
                    # Choose the best transition for these clips
                    trans_kind = choose_transition(current, next_segment, getattr(self, 'opts', {}), current_dur, next_dur)
                    transition_out = os.path.join(tmp_dir, f"transition_{i:02d}.mp4")
                    if trans_kind == "cut":
                        if concat_hard_cut(current, next_segment, transition_out):
                            current = transition_out
                            current_dur = ffprobe_duration(transition_out)
                            self.emit_log(f"[PRO] Added cut at segment {i}")
                        else:
                            current = next_segment
                            current_dur = next_dur
                    else:
                        # Map crossfade alias to fade transition
                        trans_style = "fade" if trans_kind == "crossfade" or trans_kind == "fadeblack" else trans_kind
                        if self.quick_crossfade(current, next_segment, transition_out, current_dur, next_dur, transition=trans_style):
                            current = transition_out
                            current_dur = ffprobe_duration(transition_out)
                            self.emit_log(f"[PRO] Added {trans_style} transition at segment {i}")
                        else:
                            # Fallback: if transition fails, try hard cut as last resort
                            if concat_hard_cut(current, next_segment, transition_out):
                                current = transition_out
                                current_dur = ffprobe_duration(transition_out)
                                self.emit_log(f"[PRO] Transition failed; used hard cut at segment {i}")
                            else:
                                current = next_segment
                                current_dur = next_dur
                else:
                    # Simple concatenation for non-transition points
                    concat_out = os.path.join(tmp_dir, f"concat_{i:02d}.mp4")
                    try:
                        if concat_hard_cut(current, next_segment, concat_out):
                            current = concat_out
                            current_dur = ffprobe_duration(concat_out)
                            self.emit_log(f"[PRO] Concatenated segment {i} successfully")
                        else:
                            self.emit_log(f"[PRO] Concatenation failed for segment {i}, falling back to batch concatenation")
                            # When individual concatenation fails, use fallback method with all segments
                            all_segments = [first_segment] + rendered_parts[1:i+1]
                            fallback_result = self.simple_concat_timeline_fallback(all_segments, tmp_dir)
                            if fallback_result:
                                current = fallback_result
                                current_dur = ffprobe_duration(fallback_result)
                                self.emit_log(f"[PRO] Fallback concatenation successful for segments 1-{i}")
                            else:
                                # Last resort: collect all segments for final fallback
                                self.emit_log(f"[PRO] Fallback failed, will use final concatenation method")
                                current = next_segment
                                current_dur = next_dur
                    except Exception as e:
                        self.emit_log(f"[PRO] Error during concatenation of segment {i}: {e}")
                        # Try fallback concatenation when error occurs
                        all_segments = [first_segment] + rendered_parts[1:i+1]
                        fallback_result = self.simple_concat_timeline_fallback(all_segments, tmp_dir)
                        if fallback_result:
                            current = fallback_result
                            current_dur = ffprobe_duration(fallback_result)
                            self.emit_log(f"[PRO] Error recovery successful for segments 1-{i}")
                        else:
                            current = next_segment
                            current_dur = next_dur
                
                # Update progress
                progress_val = 40 + int(30 * (i / len(rendered_parts)))
                self.progress.emit(progress_val)
            
            return current
            
        except Exception as e:
            self.emit_log(f"[PRO] Smart transition processing error: {e}")
            # Final safety net: if all else fails, use basic concatenation to preserve all segments
            try:
                self.emit_log("[PRO] Attempting final fallback concatenation to preserve all segments...")
                final_output = os.path.join(tmp_dir, f"final_emergency_concat_{uuid.uuid4().hex[:8]}.mp4")
                if combine_videos_in_order(rendered_parts, final_output, self.emit_log):
                    self.emit_log("[PRO] Emergency concatenation successful - all segments preserved")
                    return final_output
                else:
                    self.emit_log("[PRO] Emergency concatenation failed")
            except Exception as emergency_e:
                self.emit_log(f"[PRO] Emergency concatenation error: {emergency_e}")
            return None
    
    def quick_crossfade(self, clip_a: str, clip_b: str, output: str, dur_a: float, dur_b: float, transition: str = "fade") -> bool:
        """Enhanced crossfade with better quality for timeline assembly"""
        try:
            # Check if input files exist
            if not (os.path.exists(clip_a) and os.path.exists(clip_b)):
                self.emit_log(f"[PRO] Input file missing: {clip_a if not os.path.exists(clip_a) else clip_b}")
                return False
                
            # Verify durations are valid
            if dur_a <= 0 or dur_b <= 0:
                self.emit_log(f"[PRO] Invalid clip duration: clip_a={dur_a}s, clip_b={dur_b}s")
                return False
            
            # Optimize transition duration for better visual effect
            transition_dur = min(0.8, min(dur_a, dur_b) * 0.15)  # 0.8s or 15% of shorter clip
            
            # Check if audio streams exist in both clips
            has_audio_a = has_audio_stream(clip_a)
            has_audio_b = has_audio_stream(clip_b)
            
            # Build filter complex based on available streams
            video_filter = (
                f"[0:v]format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[v0];"
                f"[1:v]format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[v1];"
                f"[v0][v1]xfade=transition={transition}:duration={transition_dur}:offset={max(0, dur_a - transition_dur)}[v]"
            )
            
            audio_filter = ""
            if has_audio_a and has_audio_b:
                audio_filter = (
                    f";[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
                    f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
                    f"[a0][a1]acrossfade=d={transition_dur}:curve1=tri:curve2=tri[a]"
                )
            elif has_audio_a:
                audio_filter = f";[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a]"
            elif has_audio_b:
                audio_filter = f";[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a]"
            
            fc = video_filter + audio_filter
            
            # Build command with appropriate mapping
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-i", clip_a, "-i", clip_b,
                "-filter_complex", fc, "-map", "[v]"
            ]
            
            # Add audio mapping if available
            if has_audio_a or has_audio_b:
                cmd.extend(["-map", "[a]"])
            
            # Add encoding parameters
            cmd.extend([
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18"
            ])
            
            # Add audio encoding parameters if needed
            if has_audio_a or has_audio_b:
                cmd.extend(["-c:a", "aac", "-b:a", "320k", "-ar", "48000"])
            
            # Add output file
            cmd.extend(["-movflags", "+faststart", "-y", output])
            
            # Run command with timeout
            self.emit_log(f"[PRO] Running crossfade for clips of duration {dur_a:.2f}s and {dur_b:.2f}s")
            self.run_tracked_subprocess(cmd, check=True, timeout=300)  # 5 minute timeout
            
            if os.path.exists(output) and os.path.getsize(output) > 0:
                self.emit_log(f"[PRO] Crossfade successful: {os.path.basename(output)}")
                return True
            else:
                self.emit_log(f"[PRO] Crossfade output missing or empty: {output}")
                return False
            
        except Exception as e:
            self.emit_log(f"[PRO] Quick crossfade failed: {e}")
            return False
    
    def simple_concat_timeline(self, rendered_parts: List[str], tmp_dir: str, first_segment: str) -> Optional[str]:
        """Enhanced concatenation with better quality control"""
        try:
            if len(rendered_parts) == 1:
                return first_segment
            
            # For shorter videos (less than 5 segments), use filter_complex for better quality
            if len(rendered_parts) < 5:
                return self.enhanced_concat_timeline(rendered_parts, tmp_dir, first_segment)
            
            # For longer videos, use concat demuxer for efficiency
            # Create concat file for batch processing
            concat_file = os.path.join(tmp_dir, "concat_list.txt")
            with open(concat_file, 'w', encoding='utf-8') as f:
                f.write(f"file '{first_segment}'\n")
                for part in rendered_parts[1:]:
                    f.write(f"file '{part}'\n")
            
            # Batch concatenate all segments with better encoding
            output_path = os.path.join(tmp_dir, "assembled_timeline.mp4")
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-f", "concat", "-safe", "0",
                "-i", concat_file, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                "-movflags", "+faststart", "-y", output_path
            ]
            
            self.run_tracked_subprocess(cmd, check=True, timeout=600)  # 10 minute timeout
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.emit_log("[PRO] Simple concatenation completed successfully")
                return output_path
            else:
                return None
                
        except Exception as e:
            self.emit_log(f"[PRO] Simple concat error: {e}")
            return None
            
    def enhanced_concat_timeline(self, rendered_parts: List[str], tmp_dir: str, first_segment: str) -> Optional[str]:
        """High-quality concatenation using filter_complex for shorter videos"""
        try:
            all_parts = [first_segment] + rendered_parts[1:]
            output_path = os.path.join(tmp_dir, "enhanced_timeline.mp4")
            
            # Build complex filter for high-quality concatenation
            inputs = []
            for i, part in enumerate(all_parts):
                inputs.extend(["-i", part])
            
            # Create filter_complex string
            filter_parts = []
            for i in range(len(all_parts)):
                filter_parts.append(f"[{i}:v]format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[v{i}]")
                filter_parts.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
            
            # Concatenate video and audio streams
            v_streams = "".join([f"[v{i}]" for i in range(len(all_parts))])
            a_streams = "".join([f"[a{i}]" for i in range(len(all_parts))])
            filter_parts.append(f"{v_streams}concat=n={len(all_parts)}:v=1:a=0[vout]")
            filter_parts.append(f"{a_streams}concat=n={len(all_parts)}:v=0:a=1[aout]")
            
            filter_complex = ";".join(filter_parts)
            
            # Build and run command
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats"
            ] + inputs + [
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                "-movflags", "+faststart", "-y", output_path
            ]
            
            self.run_tracked_subprocess(cmd, check=True, timeout=900)  # 15 minute timeout
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.emit_log("[PRO] Enhanced concatenation completed successfully")
                return output_path
            else:
                # Fallback to simple concat if enhanced fails
                self.emit_log("[PRO] Enhanced concat failed, falling back to simple concat")
                return self.simple_concat_timeline_fallback(all_parts, tmp_dir)
                
        except Exception as e:
            self.emit_log(f"[PRO] Enhanced concat failed: {e}")
            # Fallback to simple concat method
            return self.simple_concat_timeline_fallback(all_parts, tmp_dir)
            
    def simple_concat_timeline_fallback(self, all_parts: List[str], tmp_dir: str) -> Optional[str]:
        """Fallback method for concatenation using copy codec for maximum compatibility"""
        try:
            # Create concat file for batch processing
            concat_file = os.path.join(tmp_dir, "concat_fallback.txt")
            with open(concat_file, 'w', encoding='utf-8') as f:
                for part in all_parts:
                    f.write(f"file '{part}'\n")
            
            # Batch concatenate all segments with copy codec
            output_path = os.path.join(tmp_dir, "fallback_timeline.mp4")
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats", "-f", "concat", "-safe", "0",
                "-i", concat_file, "-c", "copy", "-movflags", "+faststart", "-y", output_path
            ]
            
            self.run_tracked_subprocess(cmd, check=True, timeout=600)  # 10 minute timeout
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.emit_log("[PRO] Fallback concatenation completed successfully")
                return output_path
            else:
                return None
                
        except Exception as e:
            self.emit_log(f"[PRO] Fallback concat failed: {e}")
            # Ultimate fallback: use combine_videos_in_order to preserve all segments
            try:
                self.emit_log("[PRO] Attempting ultimate fallback concatenation...")
                ultimate_output = os.path.join(tmp_dir, f"ultimate_fallback_{uuid.uuid4().hex[:8]}.mp4")
                if combine_videos_in_order(all_parts, ultimate_output, self.emit_log):
                    self.emit_log("[PRO] Ultimate fallback concatenation successful")
                    return ultimate_output
                else:
                    self.emit_log("[PRO] Ultimate fallback concatenation failed")
            except Exception as ultimate_e:
                self.emit_log(f"[PRO] Ultimate fallback error: {ultimate_e}")
            return None

# =========================
# GUI (mostly unchanged, Pro pipeline is default)
# =========================

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Smart YouTube Editor — Pro Mode")
        self.showFullScreen()

        self.setStyleSheet("""
            QWidget {
                background-color: #07101a;
                color: #e6eef3;
                font-family: 'Inter', 'Segoe UI', Roboto, Arial, sans-serif;
                font-size: 11pt;
            }
            QGroupBox {
                background-color: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.04);
                border-radius: 10px;
                margin-top: 8px;
                padding: 10px;
                color: #e6eef3;
            }
            QTabWidget::pane {
                background: transparent;
                border: none;
            }
            QTabBar::tab {
                background: rgba(255,255,255,0.01);
                color: #bcd9df;
                padding: 8px 14px;
                border-radius: 8px;
                margin: 2px;
                min-width: 90px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #00acc1, stop:1 #3dd2e0);
                color: #021217;
                font-weight: 600;
            }
            QPushButton {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #0f8f96, stop:1 #00acc1);
                color: #021217;
                border-radius: 8px;
                padding: 8px 14px;
                border: none;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #12a7ad, stop:1 #1dcad6);
                color: #021217;
                outline: 1px solid rgba(61,210,224,0.18);
            }
            QPushButton:pressed {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #088789, stop:1 #008f98);
            }
            QPushButton[flat="true"], QPushButton[flat="1"] {
                background: transparent;
                color: #bcd9df;
                border: 1px solid rgba(255,255,255,0.03);
            }
            QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QComboBox, QSpinBox {
                background-color: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.03);
                border-radius: 8px;
                padding: 8px;
                color: #e6eef3;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: rgba(0,172,193,0.18);
                color: #eaf9fb;
            }
            QTextEdit#log, QPlainTextEdit#log {
                background: #03121a;
                border: 1px solid rgba(255,255,255,0.03);
                border-radius: 8px;
                padding: 10px;
                color: #d7eef0;
            }
            QProgressBar {
                border: 1px solid rgba(255,255,255,0.03);
                border-radius: 10px;
                text-align: center;
                height: 20px;
                background: rgba(255,255,255,0.01);
                color: #cfeff2;
            }
            QProgressBar::chunk {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #00acc1, stop:1 #3dd2e0);
                border-radius: 10px;
            }
        """)

        main_layout = QHBoxLayout(self)

        # Sidebar
        sidebar = QVBoxLayout()
        self.add_btn = QPushButton("Add Videos")
        self.rem_btn = QPushButton("Remove Selected")
        self.up_btn = QPushButton("Move Up")
        self.down_btn = QPushButton("Move Down")

        sidebar.addWidget(self.add_btn)
        sidebar.addWidget(self.rem_btn)
        sidebar.addWidget(self.up_btn)
        sidebar.addWidget(self.down_btn)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(self.list_widget.ExtendedSelection)
        sidebar.addWidget(self.list_widget, 1)

        out_box = QGroupBox("Output Folder")
        out_layout = QHBoxLayout()
        self.output_label = QLineEdit()
        self.output_b = QPushButton("Browse")
        out_layout.addWidget(self.output_label, 1)
        out_layout.addWidget(self.output_b)
        out_box.setLayout(out_layout)
        sidebar.addWidget(out_box)

        main_panel = QVBoxLayout()

        options = QTabWidget()
        options.addTab(self.build_options_tab(), "Options")
        options.addTab(self.build_smart_tab(), "Smart Editing")
        options.addTab(self.build_exports_tab(), "Exports")
        main_panel.addWidget(options, 3)

        log_box = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        font = self.log.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.log.setFont(font)
        log_layout.addWidget(self.log)
        log_box.setLayout(log_layout)
        main_panel.addWidget(log_box, 2)

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.process_b = QPushButton("Start Processing (Pro)")
        self.cancel_b = QPushButton("Cancel")
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.cancel_b)
        bottom.addWidget(self.process_b)
        main_panel.addLayout(bottom)

        main_layout.addLayout(sidebar, 1)
        main_layout.addLayout(main_panel, 3)
        self.setLayout(main_layout)

        # Wire signals
        self.add_btn.clicked.connect(self.add_videos)
        self.rem_btn.clicked.connect(self.remove_selected)
        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)
        self.output_b.clicked.connect(self.browse_output)
        self.process_b.clicked.connect(self.start_process)
        self.cancel_b.clicked.connect(self.cancel_process)

        # AI segment length connections
        self.ai_segment_lengths_cb.toggled.connect(self.on_ai_segment_lengths_toggled)
        self.min_seg.valueChanged.connect(self.update_segment_info_label)
        self.max_seg.valueChanged.connect(self.update_segment_info_label)
        
        # Music checkbox connection
        self.music_cb.toggled.connect(self.on_music_check)
        self.music_b.clicked.connect(self.browse_music)
        
        # Logo and intro/outro connections
        self.logo_b.clicked.connect(self.browse_logo)
        self.intro_b.clicked.connect(self.browse_intro)
        self.outro_b.clicked.connect(self.browse_outro)
        
        # initial UI state
        self.music_label.setEnabled(False)
        self.music_b.setEnabled(False)

        self.proc_thread = None
        
        # Initialize segment info label
        self.update_segment_info_label()

    def build_options_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.sub_cb = QCheckBox("Generate subtitles")
        self.burn_cb = QCheckBox("Burn subtitles")
        layout.addWidget(self.sub_cb)
        layout.addWidget(self.burn_cb)

        row = QHBoxLayout()
        self.music_cb = QCheckBox("Add background music")
        self.music_label = QLineEdit()
        self.music_label.setPlaceholderText("No file selected")
        self.music_b = QPushButton("Browse")
        row.addWidget(self.music_cb, 0)
        row.addWidget(self.music_label, 1)
        row.addWidget(self.music_b, 0)
        layout.addLayout(row)

        # AI Music Generation
        self.ai_music_cb = QCheckBox("Generate AI music based on content")
        self.ai_music_cb.setToolTip("Automatically generate background music that matches the video's mood and style")
        layout.addWidget(self.ai_music_cb)

        row2 = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.lufs_spin = QSpinBox()
        self.lufs_spin.setRange(-40, 0)
        self.lufs_spin.setValue(-14)
        row2.addWidget(QLabel("Whisper model"))
        row2.addWidget(self.model_combo)
        row2.addWidget(QLabel("Target LUFS"))
        row2.addWidget(self.lufs_spin)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.min_total_length = QSpinBox()
        self.min_total_length.setRange(0, 36000)
        self.min_total_length.setValue(0)
        self.max_total_length = QSpinBox()
        self.max_total_length.setRange(0, 36000)
        self.max_total_length.setValue(0)
        self.max_total_label = QLabel("(max: 0s)")
        row3.addWidget(QLabel("Min total (s)"))
        row3.addWidget(self.min_total_length)
        row3.addWidget(QLabel("Max total (s)"))
        row3.addWidget(self.max_total_length)
        row3.addWidget(self.max_total_label)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        self.silence_spin = QSpinBox()
        self.silence_spin.setRange(100, 5000)
        self.silence_spin.setValue(600)
        row4.addWidget(QLabel("Min silence (ms)"))
        row4.addWidget(self.silence_spin)
        layout.addLayout(row4)

        # Logo watermark
        row_logo = QHBoxLayout()
        self.logo_label = QLineEdit(); self.logo_b = QPushButton("Logo…")
        row_logo.addWidget(QLabel("Logo (PNG/SVG)")); row_logo.addWidget(self.logo_label, 1); row_logo.addWidget(self.logo_b)
        layout.addLayout(row_logo)

        # Intro/Outro (kept for optional use but Pro writes CTA automatically)
        row_intro = QHBoxLayout(); self.intro_label = QLineEdit(); self.intro_b = QPushButton("Intro…")
        row_intro.addWidget(QLabel("Intro clip")); row_intro.addWidget(self.intro_label, 1); row_intro.addWidget(self.intro_b)
        layout.addLayout(row_intro)
        row_outro = QHBoxLayout(); self.outro_label = QLineEdit(); self.outro_b = QPushButton("Outro…")
        row_outro.addWidget(QLabel("Outro clip")); row_outro.addWidget(self.outro_label, 1); row_outro.addWidget(self.outro_b)
        layout.addLayout(row_outro)

        # Pro toggles (always pro, but allow toggling some features)
        self.avoid_repeats_cb = QCheckBox("Avoid repeating clips (semantic dedupe)")
        self.avoid_repeats_cb.setChecked(True)
        self.auto_branding_cb = QCheckBox("Auto branding (logo, lower-thirds, CTA)")
        self.auto_branding_cb.setChecked(True)
        self.broadcast_chain_cb = QCheckBox("Broadcast audio chain")
        self.broadcast_chain_cb.setChecked(True)
        layout.addWidget(self.avoid_repeats_cb)
        layout.addWidget(self.auto_branding_cb)
        layout.addWidget(self.broadcast_chain_cb)

        # Jumpcut threshold
        row_jc = QHBoxLayout(); self.jumpcut_spin = QSpinBox(); self.jumpcut_spin.setRange(1, 10); self.jumpcut_spin.setValue(3)
        row_jc.addWidget(QLabel("Jumpcut if clip ≤ (s)")); row_jc.addWidget(self.jumpcut_spin)
        layout.addLayout(row_jc)

        # initial UI state
        self.music_label.setEnabled(False)
        self.music_b.setEnabled(False)
        self.music_cb.toggled.connect(self.on_music_check)
        self.music_b.clicked.connect(self.browse_music)

        self.romanian_cb = QCheckBox("Romanian Transcript & Outro")
        layout.addWidget(self.romanian_cb)

        tab.setLayout(layout)
        return tab

    def build_smart_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.kw_edit = QPlainTextEdit()
        self.kw_edit.setPlaceholderText("Keywords (comma separated)")
        layout.addWidget(QLabel("Keywords (used for scoring/highlights)"))
        layout.addWidget(self.kw_edit)

        # Hook Text (Auto-filled from Reddit title if available)
        self.hook_text_edit = QLineEdit()
        self.hook_text_edit.setPlaceholderText("Hook Text (Title Overlay)")
        # Attempt to pre-fill
        try:
            latest_title = story_picker.get_memorized_title()
            if latest_title:
                self.hook_text_edit.setText(latest_title)
        except Exception:
            pass
            
        layout.addWidget(QLabel("Hook Text (Overlay Title)"))
        layout.addWidget(self.hook_text_edit)

        # AI Content Analysis
        ai_group = QGroupBox("AI Content Analysis")
        ai_layout = QVBoxLayout()
        
        self.use_ai_analysis_cb = QCheckBox("Enable AI-driven content analysis")
        self.use_ai_analysis_cb.setChecked(True)
        self.use_ai_analysis_cb.setToolTip("Use advanced AI analysis to score video segments based on audio quality, visual appeal, speech content, and engagement factors")
        ai_layout.addWidget(self.use_ai_analysis_cb)
        
        self.multi_video_analysis_cb = QCheckBox("Intelligent multi-video selection")
        self.multi_video_analysis_cb.setChecked(True)
        self.multi_video_analysis_cb.setToolTip("When processing multiple videos, intelligently select the best segments from all sources")
        ai_layout.addWidget(self.multi_video_analysis_cb)
        
        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        # AI Segment Length Selection
        ai_segment_group = QGroupBox("AI Segment Length Selection")
        ai_segment_layout = QVBoxLayout()
        
        self.ai_segment_lengths_cb = QCheckBox("AI determines optimal segment lengths")
        self.ai_segment_lengths_cb.setChecked(False)
        self.ai_segment_lengths_cb.setToolTip("Let AI analyze video content to automatically determine the best min/max segment lengths for optimal engagement")
        ai_segment_layout.addWidget(self.ai_segment_lengths_cb)
        
        # Show current segment length settings
        self.segment_info_label = QLabel("Current: Min 6s, Max 18s")
        self.segment_info_label.setStyleSheet("color: #666; font-style: italic;")
        ai_segment_layout.addWidget(self.segment_info_label)
        
        ai_segment_group.setLayout(ai_segment_layout)
        layout.addWidget(ai_segment_group)

        row = QHBoxLayout()
        self.per_clip_target = QSpinBox()
        self.per_clip_target.setRange(10, 600)
        self.per_clip_target.setValue(40)
        self.min_seg = QSpinBox()
        self.min_seg.setRange(1, 180)
        self.min_seg.setValue(6)
        self.max_seg = QSpinBox()
        self.max_seg.setRange(1, 600)
        self.max_seg.setValue(18)
        row.addWidget(QLabel("Target per-clip (s)"))
        row.addWidget(self.per_clip_target)
        row.addWidget(QLabel("Min seg (s)"))
        row.addWidget(self.min_seg)
        row.addWidget(QLabel("Max seg (s)"))
        row.addWidget(self.max_seg)
        layout.addLayout(row)

        # Presenter name & CTA text
        row_meta = QHBoxLayout()
        self.presenter_name = QLineEdit()
        self.presenter_name.setPlaceholderText("Presenter name (for lower-third)")
        self.cta_text = QLineEdit()
        self.cta_text.setPlaceholderText("CTA text for end-screen")
        row_meta.addWidget(QLabel("Presenter"))
        row_meta.addWidget(self.presenter_name)
        row_meta.addWidget(QLabel("CTA"))
        row_meta.addWidget(self.cta_text)
        layout.addLayout(row_meta)

        tab.setLayout(layout)
        return tab

    def build_exports_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.exp_169 = QCheckBox("16:9")
        self.exp_169.setChecked(True)
        self.exp_916 = QCheckBox("9:16")
        self.exp_11 = QCheckBox("1:1")
        layout.addWidget(QLabel("Export formats"))
        layout.addWidget(self.exp_169)
        layout.addWidget(self.exp_916)
        layout.addWidget(self.exp_11)
        tab.setLayout(layout)
        return tab

    def append_log(self, text: str):
        self.log.append(text)
        try:
            self.log.moveCursor(QTextCursor.End)
        except Exception:
            try:
                self.log.ensureCursorVisible()
            except Exception:
                pass

    def add_videos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select video files (in desired order)",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.m4v *.avi *.webm)"
        )
        for f in files:
            if f:
                item = QListWidgetItem(f)
                self.list_widget.addItem(item)
        self.update_max_total_length()

    def remove_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.update_max_total_length()

    def update_max_total_length(self):
        paths = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        total = 0
        for p in paths:
            try:
                total += int(ffprobe_duration(p))
            except Exception:
                pass
        total = max(total, 10)
        self.max_total_length.setMaximum(total)
        if self.max_total_length.value() > total:
            self.max_total_length.setValue(total)
        self.min_total_length.setMaximum(total)
        if self.min_total_length.value() > total:
            self.min_total_length.setValue(total)
        self.max_total_label.setText(f"(max: {total}s)")

    def move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)

    def move_down(self):
        row = self.list_widget.currentRow()
        if 0 <= row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)

    def browse_output(self):
        fn = QFileDialog.getExistingDirectory(self, "Select output directory (choose parent; a folder will be created)")
        if fn:
            self.output_label.setText(fn)

    def browse_music(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Select music file", "", "Audio Files (*.mp3 *.wav *.m4a *.aac)")
        if fn:
            self.music_label.setText(fn)

    def browse_logo(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Select logo image", "", "Images (*.png *.svg *.webp)")
        if fn:
            self.logo_label.setText(fn)

    def browse_intro(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Select intro clip", "", "Video Files (*.mp4 *.mov *.mkv *.m4v *.avi *.webm)")
        if fn:
            self.intro_label.setText(fn)

    def browse_outro(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Select outro clip", "", "Video Files (*.mp4 *.mov *.mkv *.m4v *.avi *.webm)")
        if fn:
            self.outro_label.setText(fn)

    def on_music_check(self):
        checked = self.music_cb.isChecked()
        self.music_label.setEnabled(checked)
        try:
            self.music_b.setEnabled(checked)
        except Exception:
            pass

    def on_ai_segment_lengths_toggled(self):
        """Handle AI segment length checkbox toggle"""
        checked = self.ai_segment_lengths_cb.isChecked()
        self.min_seg.setEnabled(not checked)
        self.max_seg.setEnabled(not checked)
        
        if checked:
            self.segment_info_label.setText("AI will determine optimal segment lengths")
            self.segment_info_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        else:
            self.update_segment_info_label()

    def update_segment_info_label(self):
        """Update the segment info label with current values"""
        min_val = self.min_seg.value()
        max_val = self.max_seg.value()
        self.segment_info_label.setText(f"Current: Min {min_val}s, Max {max_val}s")
        self.segment_info_label.setStyleSheet("color: #666; font-style: italic;")

    def start_process(self):
        paths = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        if not paths:
            self.append_log("Please add at least one input video.")
            return
        out_parent = self.output_label.text().strip() or os.getcwd()
        try:
            os.makedirs(out_parent, exist_ok=True)
        except Exception as e:
            self.append_log(f"Cannot use output directory: {e}")
            return
        out_dir = os.path.join(out_parent, f"ai_edit_pro_{uuid.uuid4().hex[:6]}")
        music = self.music_label.text().strip() if self.music_cb.isChecked() else None
        exports: List[str] = []
        if self.exp_169.isChecked():
            exports.append("16:9")
        if self.exp_916.isChecked():
            exports.append("9:16")
        if self.exp_11.isChecked():
            exports.append("1:1")

        # Fetch hook text from UI (which was auto-filled)
        hook_val = self.hook_text_edit.text().strip()
        default_hook = "Trebuie să vezi asta!" if self.romanian_cb.isChecked() else "You need to see this!"
        hook_text = hook_val if hook_val else default_hook

        opts = {
            "subtitles": self.sub_cb.isChecked(),
            "burn": self.burn_cb.isChecked(),
            "music_path": music,
            "model": self.model_combo.currentText(),
            "target_lufs": self.lufs_spin.value(),
            "min_sil_ms": self.silence_spin.value(),
            "silence_db": -40,
            "exports": exports,
            "keywords": self.kw_edit.toPlainText(),
            "per_clip_target": self.per_clip_target.value(),
            "min_seg_s": self.min_seg.value(),
            "max_seg_s": self.max_seg.value(),
            "min_total_length": self.min_total_length.value(),
            "max_total_length": self.max_total_length.value(),
            "jumpcut_threshold_s": self.jumpcut_spin.value(),
            "ken_burns": True,
            "dialogue_cleanup": True,
            "logo_path": self.logo_label.text().strip(),
            "intro_path": self.intro_label.text().strip(),
            "outro_path": self.outro_label.text().strip(),
            "logo_pos": "tr",
            "avoid_repeats": self.avoid_repeats_cb.isChecked(),
            "auto_branding": self.auto_branding_cb.isChecked(),
            "broadcast_chain": self.broadcast_chain_cb.isChecked(),
            "presenter_name": self.presenter_name.text().strip(),
            "cta_text": self.cta_text.text().strip() or "Subscribe for more!",
            "language": "ro" if self.romanian_cb.isChecked() else "en",
            "hook_text": hook_text,
            # AI Features
            "use_ai_analysis": self.use_ai_analysis_cb.isChecked(),
            "use_ai_music": self.ai_music_cb.isChecked(),
            "multi_video_analysis": self.multi_video_analysis_cb.isChecked(),
            "ai_segment_lengths": self.ai_segment_lengths_cb.isChecked()
        }

        self.process_b.setEnabled(False)
        self.append_log(f"Starting PRO processing of {len(paths)} clip(s)...")
        self.proc_thread = ProcessorThread(paths, out_dir, opts)
        self.proc_thread.progress.connect(self.progress.setValue)
        self.proc_thread.log.connect(self.append_log)
        self.proc_thread.finished.connect(self.process_finished)
        self.proc_thread.start()

    def cancel_process(self):
        if self.proc_thread and self.proc_thread.isRunning():
            self.append_log("🛑 CANCELLING PROCESS IMMEDIATELY...")
            self.proc_thread.request_stop()
            self.proc_thread.requestInterruption()
            
            # Force terminate the thread if it doesn't stop within 3 seconds
            if not self.proc_thread.wait(3000):  # 3 seconds timeout
                self.append_log("⚠️ Force terminating process...")
                self.proc_thread.terminate()
                self.proc_thread.wait()
            
            self.append_log("✅ Process cancelled successfully")
            self.process_b.setEnabled(True)
            self.progress.setValue(0)
        else:
            self.append_log("No process running to cancel")

    def process_finished(self, msg: str):
        self.append_log(f"Finished: {msg}")
        self.process_b.setEnabled(True)
        self.progress.setValue(100)

# =========================
# Entrypoint
# =========================

def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    except Exception:
        pass
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
