import os
import torch
from diffusers import StableDiffusionPipeline
import random
import cv2
import numpy as np
import time
import argparse

class AIVisualGenerator:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.image_pipe = None
        
        # Models
        self.image_model_id = "runwayml/stable-diffusion-v1-5"
        
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
            # Fallback style
            prompt = (
                f"cinematic shot of {topic}, 4k, hyperrealistic, detailed, "
                "peaceful, ambient, national geographic style, 8k uhd, dslr"
            )
            negative_prompt = "text, watermark, blurry, cartoon, drawing, painting, low quality, distortion, ugly"
            h = height if height else 576
            w = width if width else 1024
        
        print(f"🎨 Generating AI Image ({style}) for: {topic}...")
        try:
            image = self.image_pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=30, 
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

    def create_ken_burns_video(self, image_path, output_path, duration=5, fps=24):
        """
        Creates a video from an image with a Ken Burns effect (pan/zoom) using OpenCV.
        """
        print(f"🎥 Creating Ken Burns effect for {duration}s: {os.path.basename(image_path)}")
        
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")
                
            h, w = img.shape[:2]
            
            # Target dimensions (1080p)
            target_w, target_h = 1920, 1080
            
            # Calculate "Cover" dimensions (min scale to cover 1920x1080)
            scale_w = target_w / w
            scale_h = target_h / h
            base_scale = max(scale_w, scale_h)
            
            max_scale = base_scale * 1.15
            resized_w = int(w * max_scale)
            resized_h = int(h * max_scale)
            
            # Ensure resized dimensions are at least target dimensions
            if resized_w < target_w or resized_h < target_h:
                 # Should not happen if base_scale is correct, but safe check
                 pass

            # Movement types
            move_type = random.choice(["zoom_in", "pan_right", "pan_left", "zoom_out"])
            
            if move_type == "zoom_in":
                start_scale = base_scale
                end_scale = base_scale * 1.1
            elif move_type == "zoom_out":
                start_scale = base_scale * 1.1
                end_scale = base_scale
            else:
                start_scale = base_scale * 1.1
                end_scale = base_scale * 1.1
            
            video_writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (target_w, target_h))
            num_frames = int(duration * fps)
            
            # Pre-calc pans
            max_off_x = (w * start_scale) - target_w
            max_off_y = (h * start_scale) - target_h
            
            # Ensure max_off is not negative
            max_off_x = max(0, max_off_x)
            max_off_y = max(0, max_off_y)
            
            # Random start/end offsets
            s_x = random.uniform(0, max_off_x)
            s_y = random.uniform(0, max_off_y)
            e_x = random.uniform(0, max_off_x)
            e_y = random.uniform(0, max_off_y)
            
            # Pre-resize base image for panning (optimization)
            # Only valid if scale is constant
            img_pan_base = None
            
            for i in range(num_frames):
                t = i / max(1, num_frames - 1) # 0.0 to 1.0
                
                # Interpolate scale
                current_scale = start_scale + (end_scale - start_scale) * t
                
                # Resize src to current scale
                curr_w = int(w * current_scale)
                curr_h = int(h * current_scale)
                
                # Optimization: Only resize if scale changes
                if abs(end_scale - start_scale) > 0.001:
                    # Zooming
                    temp = cv2.resize(img, (curr_w, curr_h), interpolation=cv2.INTER_LINEAR)
                    
                    # Center crop 1920x1080 (simpler for zoom)
                    cx, cy = curr_w // 2, curr_h // 2
                    x1 = int(cx - target_w // 2)
                    y1 = int(cy - target_h // 2)
                    
                    # Clamp
                    x1 = max(0, min(x1, curr_w - target_w))
                    y1 = max(0, min(y1, curr_h - target_h))
                    
                    frame = temp[y1:y1+target_h, x1:x1+target_w]
                    
                else:
                    # Panning (Constant scale)
                    if img_pan_base is None:
                         img_pan_base = cv2.resize(img, (curr_w, curr_h), interpolation=cv2.INTER_CUBIC)
                        
                    # Interpolate pos
                    curr_x = int(s_x + (e_x - s_x) * t)
                    curr_y = int(s_y + (e_y - s_y) * t)
                    
                    # Clamp
                    curr_x = max(0, min(curr_x, curr_w - target_w))
                    curr_y = max(0, min(curr_y, curr_h - target_h))
                    
                    frame = img_pan_base[curr_y:curr_y+target_h, curr_x:curr_x+target_w]
                
                # Final safety resize if rounding errors occurred
                if frame.shape[0] != target_h or frame.shape[1] != target_w:
                     frame = cv2.resize(frame, (target_w, target_h))
                     
                video_writer.write(frame)
                
            video_writer.release()
            print(f"✅ Saved Ken Burns video to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Ken Burns Error: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Topic/Prompt for generation")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--mode", default="image", choices=["image", "video", "ken_burns"], help="Generation mode")
    parser.add_argument("--duration", type=float, default=5.0, help="Duration for video modes")
    
    args = parser.parse_args()
    
    gen = AIVisualGenerator()
    
    if args.mode == "image":
        gen.generate_image(args.topic, args.output, style="realistic")
        
    elif args.mode == "ken_burns":
        # 1. Generate Image
        temp_img = args.output.replace(".mp4", "_temp.png")
        if gen.generate_image(args.topic, temp_img, style="realistic"):
            # 2. Apply Ken Burns
            gen.create_ken_burns_video(temp_img, args.output, duration=args.duration)
            # Cleanup
            if os.path.exists(temp_img):
                os.remove(temp_img)
        else:
            print("❌ Image generation failed, cannot create video.")
            
    elif args.mode == "video":
        # Legacy/Fallback: Just generate image for now, or map to ken_burns?
        # The user wanted to replace Wan with Ken Burns.
        # So "video" mode should probably just do Ken Burns too.
        print("ℹ️ Video mode mapped to Ken Burns effect.")
        temp_img = args.output.replace(".mp4", "_temp.png")
        if gen.generate_image(args.topic, temp_img, style="realistic"):
            gen.create_ken_burns_video(temp_img, args.output, duration=args.duration)
            if os.path.exists(temp_img):
                os.remove(temp_img)
