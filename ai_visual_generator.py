import os
import torch
from diffusers import StableDiffusionPipeline
import random

class AIVisualGenerator:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipe = None
        self.model_id = "runwayml/stable-diffusion-v1-5"
        
        # Check for M: drive for cache
        self.cache_dir = None
        if os.path.exists("M:/"):
            self.cache_dir = "M:/huggingface_cache"
            os.makedirs(self.cache_dir, exist_ok=True)
            print(f"🤖 using M: drive for AI models: {self.cache_dir}")
        else:
            print("🤖 Using default cache for AI models")

    def _load_pipeline(self):
        if self.pipe is not None:
            return

        print("🚀 Loading Stable Diffusion (Low VRAM mode)...")
        try:
            # Clear cache
            if self.device == "cuda":
                torch.cuda.empty_cache()
                
            # Load with low memory optimizations
            self.pipe = StableDiffusionPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                cache_dir=self.cache_dir,
                use_safetensors=True,
                variant="fp16" if self.device == "cuda" else None,
                low_cpu_mem_usage=True,
                safety_checker=None, # Save memory
                feature_extractor=None,
                requires_safety_checker=False
            )
            
            if self.device == "cuda":
                # Crucial for 4GB VRAM
                # Use sequential cpu offload for maximum memory saving
                self.pipe.enable_sequential_cpu_offload()
                self.pipe.enable_vae_slicing()
                self.pipe.enable_attention_slicing()
            else:
                self.pipe.to("cpu")
                
            print("✅ AI Model Loaded Successfully")
        except Exception as e:
            print(f"❌ Error loading AI model: {e}")
            raise e

    def generate_image(self, topic, output_path, style="minimalist"):
        self._load_pipeline()
        
        if style == "realistic":
            prompt = (
                f"cinematic shot of {topic}, 4k, hyperrealistic, detailed, "
                "peaceful, ambient, national geographic style, 8k uhd, dslr, "
                "beautiful lighting, nature photography"
            )
            negative_prompt = (
                "text, watermark, blurry, cartoon, drawing, painting, "
                "low quality, distortion, ugly, bad anatomy"
            )
            height = 544
            width = 960
        else:
            # Minimalist Grid Style
            prompt = (
                f"minimalist white line art of {topic}, "
                "simple scientific diagram style, "
                "white lines on black background, "
                "faint grid pattern background, "
                "vector illustration, flat design, cute, calming, "
                "high contrast, clean lines, no text"
            )
            negative_prompt = (
                "text, watermark, colorful, complex, realistic, photo, "
                "shading, gradient, blurry, messy, distorted, "
                "human face, words, signature"
            )
            height = 512
            width = 512
        
        print(f"🎨 Generating AI Image ({style}) for: {topic}...")
        
        try:
            image = self.pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=25, 
                guidance_scale=7.5,
                height=height, 
                width=width
            ).images[0]
            
            image.save(output_path)
            print(f"🖼️ Saved AI image to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ AI Generation Failed: {e}")
            return None

    def generate_animated_video(self, topic, output_path, duration=10):
        """Generates an image and animates it (zoom/pan) to create a video loop."""
        # 1. Generate Image
        temp_img = output_path.replace(".mp4", ".png")
        if not self.generate_image(topic, temp_img, style="realistic"):
            return False
            
        # 2. Animate (Ken Burns Effect)
        print(f"🎥 Animating {topic}...")
        try:
            import cv2
            import numpy as np
            
            # Read image
            img = cv2.imread(temp_img)
            h, w, _ = img.shape
            
            # Setup video writer
            # Output 1080p directly to ensure compatibility
            target_w, target_h = 1920, 1080
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 24
            out = cv2.VideoWriter(output_path, fourcc, fps, (target_w, target_h))
            
            frames = int(duration * fps)
            
            # Zoom parameters
            zoom_factor = 1.1 # 10% zoom over duration
            
            for i in range(frames):
                # Calculate current scale
                scale = 1.0 + (zoom_factor - 1.0) * (i / frames)
                
                # Crop center
                center_x, center_y = w / 2, h / 2
                
                # Size of the crop window
                crop_w = w / scale
                crop_h = h / scale
                
                x1 = int(center_x - crop_w / 2)
                y1 = int(center_y - crop_h / 2)
                x2 = int(center_x + crop_w / 2)
                y2 = int(center_y + crop_h / 2)
                
                # Clamp
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(w, x2); y2 = min(h, y2)
                
                crop = img[y1:y2, x1:x2]
                
                # Resize to target 1080p
                if crop.size > 0:
                    frame = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
                    out.write(frame)
                
            out.release()
            
            # Cleanup temp image
            if os.path.exists(temp_img):
                os.remove(temp_img)
                
            print(f"✅ Saved animated video to {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Animation Failed: {e}")
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
