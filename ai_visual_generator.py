import os
import torch
from diffusers import StableDiffusionPipeline, AutoPipelineForTextToVideo
from diffusers.utils import export_to_video
import random
import cv2
import numpy as np

class AIVisualGenerator:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.image_pipe = None
        self.video_pipe = None
        
        # Models
        self.image_model_id = "runwayml/stable-diffusion-v1-5"
        # Using Wan 2.1 1.3B (Efficient, fits in 16GB VRAM, High Quality)
        # Wan 2.2 14B is too large for T4 (16GB). 1.3B is the sweet spot.
        self.video_model_id = "Wan-AI/Wan2.1-T2V-1.3B" 
        
        # Check for M: drive for cache (Local Dev)
        self.cache_dir = None
        if os.path.exists("M:/"):
            self.cache_dir = "M:/huggingface_cache"
            os.makedirs(self.cache_dir, exist_ok=True)
            print(f"🤖 using M: drive for AI models: {self.cache_dir}")
        else:
            print("🤖 Using default cache for AI models")

    def _load_image_pipeline(self):
        if self.image_pipe is not None:
            return

        print("🚀 Loading Stable Diffusion (Text-to-Image)...")
        try:
            if self.device == "cuda":
                torch.cuda.empty_cache()
                
            self.image_pipe = StableDiffusionPipeline.from_pretrained(
                self.image_model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                cache_dir=self.cache_dir,
                use_safetensors=True,
                variant="fp16" if self.device == "cuda" else None,
                safety_checker=None,
                requires_safety_checker=False
            )
            
            if self.device == "cuda":
                self.image_pipe.enable_model_cpu_offload() 
                self.image_pipe.enable_vae_slicing()
            else:
                self.image_pipe.to("cpu")
                
            print("✅ Image Model Loaded")
        except Exception as e:
            print(f"❌ Error loading Image model: {e}")
            raise e

    def _load_video_pipeline(self):
        if self.video_pipe is not None:
            return

        print(f"🚀 Loading Wan 2.1 Video Model ({self.video_model_id})...")
        try:
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            # Load Wan 2.1 T2V
            self.video_pipe = AutoPipelineForTextToVideo.from_pretrained(
                self.video_model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                cache_dir=self.cache_dir,
                variant="fp16" if self.device == "cuda" else None
            )
            
            if self.device == "cuda":
                # Enable CPU offload for 16GB VRAM
                self.video_pipe.enable_model_cpu_offload()
                # self.video_pipe.enable_sequential_cpu_offload() # Use if strictly 8GB
            else:
                self.video_pipe.to("cpu")
                
            print("✅ Wan Video Model Loaded")
        except Exception as e:
            print(f"❌ Error loading Wan model: {e}")
            raise e

    def generate_image(self, topic, output_path, style="minimalist", width=None, height=None):
        self._load_image_pipeline()
        
        if style == "realistic":
            prompt = (
                f"cinematic shot of {topic}, 4k, hyperrealistic, detailed, "
                "peaceful, ambient, national geographic style, 8k uhd, dslr, "
                "beautiful lighting, nature photography"
            )
            negative_prompt = "text, watermark, blurry, cartoon, drawing, painting, low quality, distortion, ugly"
            h = height if height else 576
            w = width if width else 1024
        else:
            prompt = (
                f"minimalist white line art of {topic}, simple scientific diagram style, "
                "white lines on black background, faint grid pattern background, "
                "vector illustration, flat design, cute, calming, high contrast, clean lines, no text"
            )
            negative_prompt = "text, watermark, colorful, complex, realistic, photo, shading, gradient, blurry"
            h = height if height else 512
            w = width if width else 512
        
        print(f"🎨 Generating AI Image ({style}) for: {topic}...")
        try:
            image = self.image_pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=25, 
                guidance_scale=7.5,
                height=h, 
                width=w
            ).images[0]
            image.save(output_path)
            print(f"🖼️ Saved AI image to {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ AI Generation Failed: {e}")
            return None

    def generate_animated_video(self, topic, output_path, duration=5):
        """Generates a genuine AI video using Wan 2.1 (Text-to-Video)."""
        print(f"🎬 Starting Wan 2.1 AI Video Generation for: {topic}")
        
        self._load_video_pipeline()
        
        try:
            print(f"🎥 Generating with Wan 2.1 (T2V 1.3B)...")
            
            prompt = f"Cinematic slow motion shot of {topic}, 4k, hyperrealistic, ambient lighting, smooth motion"
            negative_prompt = "text, watermark, blurry, distortion, morphing, jerky, static"
            
            # Wan 1.3B generates 5s at 480p by default (usually 81 frames or similar)
            # We use 50 inference steps for quality
            frames = self.video_pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=30, # Balanced for speed/quality
                guidance_scale=6.0,
                height=480, 
                width=832 # Standard 16:9 approx
            ).frames[0]
            
            # Export to temp
            temp_path = output_path.replace(".mp4", "_temp.mp4")
            export_to_video(frames, temp_path, fps=16) # Wan usually 16fps
            
            # Upscale/Loop to match requested duration (5-8s)
            # If user wants 8s, we can boomerang or slow down
            # Wan native is ~5s. Boomerang = 10s.
            
            import cv2
            cap = cv2.VideoCapture(temp_path)
            all_frames = []
            while True:
                ret, frame = cap.read()
                if not ret: break
                # Resize to 1080p
                frame = cv2.resize(frame, (1920, 1080), interpolation=cv2.INTER_CUBIC)
                all_frames.append(frame)
            cap.release()
            
            if os.path.exists(temp_path): os.remove(temp_path)
            
            # Create Loop (Boomerang)
            final_frames = all_frames + all_frames[::-1]
            
            # Save final
            # 16fps * 2 = 32fps playback? Or keep 24fps
            # If we have N frames.
            # We want smooth video.
            out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), 24, (1920, 1080))
            for f in final_frames:
                out.write(f)
            out.release()
            
            print(f"✅ Saved Wan AI video to {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Wan Animation Failed: {e}")
            return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--mode", type=str, default="image", choices=["image", "video"])
    args = parser.parse_args()
    
    gen = AIVisualGenerator()
    if args.mode == "video":
        gen.generate_animated_video(args.topic, args.output)
    else:
        gen.generate_image(args.topic, args.output)
