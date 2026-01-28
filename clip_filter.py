import requests
from PIL import Image
from io import BytesIO
import torch

class ClipFilter:
    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔧 Initializing CLIP Filter on {self.device.upper()}...")

    def load_model(self):
        if self.model is None:
            try:
                from transformers import CLIPProcessor, CLIPModel
                print(f"📥 Loading CLIP model: {self.model_name}...")
                self.model = CLIPModel.from_pretrained(self.model_name).to(self.device)
                self.processor = CLIPProcessor.from_pretrained(self.model_name)
                print("✅ CLIP model loaded successfully.")
                return True
            except ImportError:
                print("❌ 'transformers' or 'torch' library missing. Please run: pip install transformers torch pillow")
                return False
            except Exception as e:
                print(f"❌ Error loading CLIP model: {e}")
                return False
        return True

    def score_candidates(self, candidates, text_query):
        """
        Scores a list of candidates against a text query.
        candidates: List of dicts with 'thumbnail' (URL) and other metadata.
        text_query: The text to match against.
        Returns: The best candidate dict, or None if failed.
        """
        if not self.load_model():
            return None

        if not candidates:
            return None

        print(f"🔍 CLIP Scoring {len(candidates)} images against: '{text_query}'")
        
        images = []
        valid_candidates = []
        
        # Download thumbnails
        for cand in candidates:
            thumb_url = cand.get('thumbnail')
            if not thumb_url:
                continue
                
            try:
                resp = requests.get(thumb_url, timeout=5)
                if resp.status_code == 200:
                    img = Image.open(BytesIO(resp.content)).convert("RGB")
                    images.append(img)
                    valid_candidates.append(cand)
            except Exception as e:
                # print(f"Failed to load thumbnail: {e}")
                pass

        if not images:
            print("⚠️ No valid thumbnails downloaded for scoring.")
            return None

        # Process and Score
        try:
            inputs = self.processor(text=[text_query], images=images, return_tensors="pt", padding=True).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                
            # specific logic for CLIP score (logits_per_image)
            logits_per_image = outputs.logits_per_image  # shape: [num_images, num_texts]
            probs = logits_per_image.softmax(dim=0)  # Softmax across images
            
            # Get best index
            best_idx = logits_per_image.argmax(dim=0).item()
            best_score = logits_per_image[best_idx].item()
            
            winner = valid_candidates[best_idx]
            print(f"🏆 CLIP Winner: {winner.get('source', 'Unknown')} (Score: {best_score:.2f})")
            return winner
            
        except Exception as e:
            print(f"❌ CLIP Scoring Error: {e}")
            return None
