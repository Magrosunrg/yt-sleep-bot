
import os
import torch
from PIL import Image
import cv2
import numpy as np
from transformers import CLIPProcessor, CLIPModel

# Try to import scenedetect, handle if missing
try:
    import scenedetect
    from scenedetect import VideoManager, SceneManager
    from scenedetect.detectors import ContentDetector
    SCENEDETECT_AVAILABLE = True
    # Check for open_video (v0.6+)
    HAS_OPEN_VIDEO = hasattr(scenedetect, 'open_video')
except ImportError:
    SCENEDETECT_AVAILABLE = False
    HAS_OPEN_VIDEO = False
    print("⚠️ PySceneDetect not found. Using fixed intervals.")

class SceneMatcher:
    def __init__(self, video_path, model_name="openai/clip-vit-base-patch32", device=None):
        self.video_path = video_path
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"⚙️ Initializing SceneMatcher on {self.device}...")
        
        # Load CLIP Model
        try:
            self.model = CLIPModel.from_pretrained(model_name).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            print("✅ CLIP model loaded.")
        except Exception as e:
            print(f"❌ Failed to load CLIP model: {e}")
            self.model = None
            
        self.scenes = [] # List of (start_time, end_time)
        self.embeddings = None # Tensor of shape (N, 512)
        self.virality_scores = None # Tensor of shape (N, 1)

        if self.model:
            self._index_video()

    def _index_video(self):
        """Detects scenes and computes embeddings for them."""
        print("🔍 Detecting scenes (this may take a minute)...")
        self.scenes = self._detect_scenes()
        print(f"   Found {len(self.scenes)} scenes.")
        
        if not self.scenes:
            return

        print("📸 Extracting keyframes and computing embeddings (batched)...")
        
        cap = cv2.VideoCapture(self.video_path)
        batch_size = 8 # Reduced batch size further for safety
        current_batch_images = []
        current_batch_indices = []
        all_embeddings = []
        valid_indices = [] # Indices of scenes that were successfully processed
        
        # Total scenes
        total_scenes = len(self.scenes)
        
        with torch.no_grad():
            for i, (start, end) in enumerate(self.scenes):
                # Extract middle frame
                mid_point = (start + end) / 2
                cap.set(cv2.CAP_PROP_POS_MSEC, mid_point * 1000)
                ret, frame = cap.read()
                
                if ret:
                    # Convert BGR to RGB and resize early to save memory
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    # Resize to 224x224 (CLIP standard) or slightly larger to save RAM before PIL
                    # CLIP usually takes 224 or 336. Let's resize to 320px width to be safe but efficient.
                    h, w, _ = frame.shape
                    new_w = 320
                    new_h = int(h * (320 / w))
                    frame = cv2.resize(frame, (new_w, new_h))
                    
                    current_batch_images.append(Image.fromarray(frame))
                    current_batch_indices.append(i)
                else:
                    pass
                
                # Process batch if full or last scene
                if len(current_batch_images) >= batch_size or (i == total_scenes - 1 and current_batch_images):
                    try:
                        inputs = self.processor(images=current_batch_images, return_tensors="pt", padding=True).to(self.device)
                        image_features = self.model.get_image_features(**inputs)
                        # Normalize
                        image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
                        # Move to CPU to save VRAM
                        all_embeddings.append(image_features.cpu())
                        valid_indices.extend(current_batch_indices)
                    except Exception as e:
                        print(f"⚠️ Batch processing failed: {e}")
                        # If a batch fails, we lose those scenes, but we continue
                    
                    # Clear batch
                    current_batch_images = []
                    current_batch_indices = []
                    
                    # Optional: GC every few batches
                    if i % (batch_size * 10) == 0:
                        import gc
                        gc.collect()

        cap.release()
        
        if all_embeddings:
            self.embeddings = torch.cat(all_embeddings, dim=0).to(self.device) # Move back to device if needed, or keep on CPU if large
            # If embeddings are large, keep on CPU?
            # self.device might be CUDA. If we keep all on CUDA, we might OOM.
            # Let's keep self.embeddings on the device for fast similarity search, 
            # BUT if it's too big, we might want CPU. 2600 * 512 floats is small (5MB). 
            # The IMAGES were the problem.
            
            # Update scenes to only include valid ones
            self.scenes = [self.scenes[i] for i in valid_indices]
            
            # Compute Virality Scores
            self.virality_scores = self._compute_virality_scores()
            
            print(f"✅ Indexed {len(self.scenes)} scenes successfully.")
        else:
            print("⚠️ No embeddings generated.")

    def _detect_scenes(self):
        """
        Uses PySceneDetect to find scenes (cuts). 
        Returns list of (start_seconds, end_seconds).
        If PySceneDetect is missing/fails, returns fixed 2s intervals.
        """
        if not SCENEDETECT_AVAILABLE:
            return self._get_fixed_intervals()

        try:
            # FORCE Legacy method with aggressive downscaling for performance
            # open_video (v0.6+) might be too slow if it doesn't downscale by default
            use_open_video = False # Set to True only if we confirm downscaling works
            
            if use_open_video and HAS_OPEN_VIDEO:
                # open_video is generally more stable and efficient
                video = scenedetect.open_video(self.video_path)
                scene_manager = SceneManager()
                scene_manager.add_detector(ContentDetector(threshold=27.0))
                scene_manager.detect_scenes(video, show_progress=False)
                scene_list = scene_manager.get_scene_list()
            else:
                # Legacy method
                video_manager = VideoManager([self.video_path])
                scene_manager = SceneManager()
                scene_manager.add_detector(ContentDetector(threshold=27.0))

                # Improve processing speed and memory usage
                # Downscale to something small like 100p-140p for detection
                # 1080p / 8 = 135p
                video_manager.set_downscale_factor(downscale_factor=8) 
                
                video_manager.start()
                scene_manager.detect_scenes(frame_source=video_manager)
                scene_list = scene_manager.get_scene_list()
            
            scenes = []
            for scene in scene_list:
                start = scene[0].get_seconds()
                end = scene[1].get_seconds()
                if end - start > 0.5: # Ignore tiny glitches
                    scenes.append((start, end))
            
            video_manager.release()
            
            if not scenes:
                print("⚠️ No scenes detected by PySceneDetect. Using fixed intervals.")
                return self._get_fixed_intervals()
                
            return scenes

        except Exception as e:
            print(f"⚠️ PySceneDetect failed: {e}. Using fixed intervals.")
            return self._get_fixed_intervals()

    def _get_fixed_intervals(self, interval=2.0):
        """Fallback: chop video into fixed chunks."""
        try:
            cap = cv2.VideoCapture(self.video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps
            cap.release()
            
            scenes = []
            curr = 0.0
            while curr < duration:
                scenes.append((curr, min(curr + interval, duration)))
                curr += interval
            return scenes
        except:
            return []

    def _compute_virality_scores(self):
        """
        Computes a 'virality' score for each scene based on visual qualities.
        Compares embeddings against positive and negative viral concepts.
        """
        if self.embeddings is None:
            return None
            
        print("📈 Computing virality scores...")
        
        # Viral Concepts
        pos_prompts = [
            "cinematic masterpiece, high resolution, sharp focus",
            "intense action scene, explosion, fast movement",
            "emotional close-up face, dramatic lighting",
            "vibrant colors, 4k, award winning cinematography",
            "movie trailer highlight, iconic scene"
        ]
        
        neg_prompts = [
            "blurry, out of focus, low quality",
            "black screen, darkness, too dark",
            "closing credits, rolling text, white text on black background",
            "static image, boring, nothing happening",
            "logo, watermark, studio intro"
        ]
        
        with torch.no_grad():
            # Encode prompts
            pos_inputs = self.processor(text=pos_prompts, return_tensors="pt", padding=True).to(self.device)
            neg_inputs = self.processor(text=neg_prompts, return_tensors="pt", padding=True).to(self.device)
            
            pos_embeds = self.model.get_text_features(**pos_inputs)
            neg_embeds = self.model.get_text_features(**neg_inputs)
            
            # Normalize
            pos_embeds = pos_embeds / pos_embeds.norm(p=2, dim=-1, keepdim=True)
            neg_embeds = neg_embeds / neg_embeds.norm(p=2, dim=-1, keepdim=True)
            
            # Mean embedding for concepts
            pos_mean = pos_embeds.mean(dim=0, keepdim=True)
            neg_mean = neg_embeds.mean(dim=0, keepdim=True)
            
            # Similarity
            pos_sim = (self.embeddings @ pos_mean.T) # (N, 1)
            neg_sim = (self.embeddings @ neg_mean.T) # (N, 1)
            
            # Score = Positive - Negative
            scores = pos_sim - neg_sim
            
            # Normalize scores to 0-1 range for easier combination
            scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-6)
            
            return scores

    def find_best_match(self, text_query, top_k=1, viral_boost_descriptions=None, min_start_time=0.0, exclude_intervals=None, max_end_time=None):
        """
        Finds the best matching scene for the text query.
        
        Args:
            text_query (str): The sentence from the script.
            viral_boost_descriptions (list): List of strings describing viral scenes (from Ollama).
                                           Scenes matching these get a massive score boost.
            min_start_time (float): Only consider scenes starting after this time (chronological flow).
            exclude_intervals (list): List of (start, end) tuples to exclude (prevent repetition).
            max_end_time (float): Only consider scenes ending before this time (avoid credits/outro).
        """
        if self.embeddings is None or self.model is None:
            return None
            
        with torch.no_grad():
            # 1. Base Text Match
            inputs = self.processor(text=[text_query], return_tensors="pt", padding=True).to(self.device)
            text_features = self.model.get_text_features(**inputs)
            text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
            
            # Cosine similarity
            base_similarity = (text_features @ self.embeddings.T).squeeze(0) # (N,)
            
            # 2. Viral Quality Boost (General visual appeal)
            final_score = base_similarity
            if self.virality_scores is not None:
                # Weighted combination: 70% relevance, 30% visual appeal
                # Only apply if base similarity is decent (>0.15) to avoid boosting irrelevant beautiful scenes
                mask = (base_similarity > 0.15).float()
                final_score = base_similarity + (self.virality_scores.squeeze(1) * 0.15 * mask)
            
            # 3. Viral Context Boost (Specific famous scenes from Ollama)
            if viral_boost_descriptions:
                # Encode viral descriptions
                v_inputs = self.processor(text=viral_boost_descriptions, return_tensors="pt", padding=True).to(self.device)
                v_feats = self.model.get_text_features(**v_inputs)
                v_feats = v_feats / v_feats.norm(p=2, dim=-1, keepdim=True)
                
                # Sim matrix: (Num_Viral_Descs, Num_Scenes)
                v_sims = v_feats @ self.embeddings.T 
                
                # For each scene, take its max similarity to ANY viral description
                max_v_sim, _ = v_sims.max(dim=0) # (N,)
                
                # Boost scenes that look like famous scenes
                # Only boost if the scene actually looks like the viral concept (>0.22)
                # Increase weight to 0.35 to make them prioritized if they match
                mask_viral = (max_v_sim > 0.22).float()
                final_score = final_score + (max_v_sim * 0.35 * mask_viral)

            # 4. Filter by min_start_time (Chronological Constraint) and max_end_time (Credits filter)
            # Create a mask for valid scenes
            # self.scenes is list of (start, end)
            scene_starts = torch.tensor([s[0] for s in self.scenes], device=self.device)
            scene_ends = torch.tensor([s[1] for s in self.scenes], device=self.device)
            
            time_mask = (scene_starts >= min_start_time).float()
            
            # Apply max_end_time if provided
            if max_end_time is not None:
                end_mask = (scene_ends <= max_end_time).float()
                time_mask = time_mask * end_mask
            
            # 5. Filter by exclude_intervals (No Repetition)
            if exclude_intervals:
                # 1.0 = valid, 0.0 = invalid
                overlap_mask = torch.ones_like(scene_starts)
                
                for ex_start, ex_end in exclude_intervals:
                    # Check if scene overlaps with exclusion zone
                    # Overlap: (SceneStart < ExEnd) and (SceneEnd > ExStart)
                    # We want to find INVALID scenes where this is true
                    
                    # Using tensor logic for speed
                    # invalid if (start < ex_end) & (end > ex_start)
                    invalid = (scene_starts < ex_end) & (scene_ends > ex_start)
                    
                    # Update mask: if invalid is True, set position to 0
                    overlap_mask[invalid] = 0.0
                    
                time_mask = time_mask * overlap_mask
            
            # Apply mask (set invalid scores to -inf)
            final_score = final_score * time_mask + (1 - time_mask) * -1e9
            
            # Get best match
            best_val, best_idx = torch.max(final_score, dim=0)
            
            # If all scores are -inf (no valid scenes after min_time), return None
            if best_val.item() < -100:
                return None
                
            return {
                'start': self.scenes[best_idx][0],
                'end': self.scenes[best_idx][1],
                'score': best_val.item()
            }

    def get_best_crop_center(self, clip_or_frame, aspect_ratio=1.0):
        """
        Determines the best X-coordinate for the center of the crop.
        Uses Face Detection and Motion Detection (if clip provided).
        """
        import numpy as np
        
        frame = None
        motion_center = None
        
        # Determine if input is a Clip or a Frame
        if hasattr(clip_or_frame, 'get_frame') and hasattr(clip_or_frame, 'duration'):
            # It's a MoviePy clip
            clip = clip_or_frame
            mid_t = clip.duration / 2
            try:
                frame = clip.get_frame(mid_t)
                
                # Try Motion Detection
                if clip.duration > 0.5:
                    frame_next = clip.get_frame(min(mid_t + 0.2, clip.duration))
                    
                    # Convert to Gray
                    g1 = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                    g2 = cv2.cvtColor(frame_next, cv2.COLOR_RGB2GRAY)
                    
                    # Diff
                    diff = cv2.absdiff(g1, g2)
                    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                    
                    # Centroid of motion
                    M = cv2.moments(thresh)
                    if M["m00"] > 100: # Threshold for significant motion
                        motion_center = int(M["m10"] / M["m00"])
                        # print(f"   🏃 Motion detected at x={motion_center}")
            except Exception as e:
                # print(f"   ⚠️ Motion detection failed: {e}")
                pass
        else:
            # It's a Frame (numpy array or PIL)
            if hasattr(clip_or_frame, 'convert'):
                frame = np.array(clip_or_frame.convert('RGB'))
            else:
                frame = clip_or_frame
        
        if frame is None:
            return 0 # Should not happen
            
        h, w = frame.shape[:2]
        
        # 1. Face Detection (Priority)
        try:
            # MoviePy is RGB, OpenCV needs Gray
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            else:
                gray = frame
                
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = cv2.CascadeClassifier(cascade_path)
            
            # Scale factor 1.3 for speed, minNeighbors 5 for reliability
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            
            if len(faces) > 0:
                # Weighted average of face centers
                total_weight = 0
                weighted_sum_x = 0
                
                for (x, y, fw, fh) in faces:
                    weight = fw * fh
                    center = x + fw / 2
                    weighted_sum_x += center * weight
                    total_weight += weight
                    
                final_center_x = weighted_sum_x / total_weight
                print(f"   👤 Smart Crop: Centered on Face(s) at x={final_center_x:.0f}")
                return final_center_x
        except Exception as e:
            # print(f"   ⚠️ Face detection failed: {e}")
            pass
            
        # 2. Motion Detection (Secondary)
        if motion_center is not None:
             print(f"   🏃 Smart Crop: Centered on Action at x={motion_center:.0f}")
             return motion_center
             
        # 3. Fallback to Center
        return w / 2

    def generate_crop_trajectory(self, clip, interval=0.5):
        """
        Generates a smooth function f(t) -> center_x that tracks the subject.
        """
        import numpy as np
        
        duration = clip.duration
        timestamps = np.arange(0, duration, interval)
        if len(timestamps) == 0:
            return lambda t: clip.w / 2
            
        centers = []
        w = clip.w
        
        print(f"   🎥 Tracking subject across {len(timestamps)} frames...")
        
        # 1. Sample Keypoints
        for t in timestamps:
            try:
                # Use get_best_crop_center logic for this frame
                # We extract frame manually to optimize
                frame = clip.get_frame(t)
                
                # REUSE LOGIC: But we need to refactor slightly or just copy-paste specific logic for speed
                # Calling get_best_crop_center with frame is fine
                # But we want to favor continuity. 
                # If we lose face, maybe we should stay near previous?
                
                # Let's trust get_best_crop_center's hierarchy (Face > Motion > Center)
                # But we pass the frame directly so it doesn't re-read
                # Note: Motion detection in get_best_crop_center requires a clip, not frame.
                # So we lose motion detection if we pass frame.
                # FIX: We should pass a small subclip or handle motion here.
                
                # Simple Motion here:
                motion_x = None
                if t + 0.2 < duration:
                     next_frame = clip.get_frame(t + 0.2)
                     # Downscale for speed
                     h_small, w_small = 360, int(360 * w / frame.shape[0])
                     f1 = cv2.resize(frame, (w_small, h_small))
                     f2 = cv2.resize(next_frame, (w_small, h_small))
                     
                     g1 = cv2.cvtColor(f1, cv2.COLOR_RGB2GRAY)
                     g2 = cv2.cvtColor(f2, cv2.COLOR_RGB2GRAY)
                     diff = cv2.absdiff(g1, g2)
                     _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                     M = cv2.moments(thresh)
                     if M["m00"] > 100:
                         mx = int(M["m10"] / M["m00"])
                         motion_x = mx * (w / w_small)
                
                # Face Detection
                face_x = None
                # Reuse the face logic from get_best_crop_center but optimized
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                face_cascade = cv2.CascadeClassifier(cascade_path)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                if len(faces) > 0:
                    total_weight = 0
                    weighted_sum_x = 0
                    for (x, y, fw, fh) in faces:
                        weight = fw * fh
                        center = x + fw / 2
                        weighted_sum_x += center * weight
                        total_weight += weight
                    face_x = weighted_sum_x / total_weight

                # Decide
                if face_x is not None:
                    centers.append(face_x)
                elif motion_x is not None:
                    centers.append(motion_x)
                else:
                    # If lost, use previous or center
                    if centers:
                        centers.append(centers[-1])
                    else:
                        centers.append(w / 2)
                        
            except Exception as e:
                # print(f"Frame analysis failed: {e}")
                if centers:
                    centers.append(centers[-1])
                else:
                    centers.append(w / 2)

        # 2. Smooth the path (Moving Average)
        # Window size 3 (approx 1.5 sec)
        smoothed = []
        window = 3
        for i in range(len(centers)):
            start = max(0, i - window // 2)
            end = min(len(centers), i + window // 2 + 1)
            chunk = centers[start:end]
            smoothed.append(sum(chunk) / len(chunk))
            
        # 3. Create Interpolator
        def get_center(t):
            # Find indices
            if t <= timestamps[0]: return smoothed[0]
            if t >= timestamps[-1]: return smoothed[-1]
            
            # Linear interp
            return np.interp(t, timestamps, smoothed)
            
        return get_center

if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        matcher = SceneMatcher(path)
        while True:
            q = input("Enter query (or q to quit): ")
            if q == 'q': break
            res = matcher.find_best_match(q)
            print(res)
