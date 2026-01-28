import os
import torch
import soundfile as sf
import numpy as np

# Singleton to hold the model
_MODEL = None
_LOAD_FAILED = False

def load_model():
    global _MODEL, _LOAD_FAILED
    if _MODEL is None and not _LOAD_FAILED:
        try:
            from chatterbox.tts import ChatterboxTTS
            print("🚀 Loading Chatterbox TTS Model...")
            # Automatically uses CUDA if available internally or we pass device
            # Check env var for override, else use cuda if available, else cpu
            if os.environ.get("USE_CUDA_TTS", "0") == "1" or torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
                
            print(f"   Using device: {device}")
            _MODEL = ChatterboxTTS.from_pretrained(device=device)
        except ImportError:
            print("⚠️ Chatterbox library not found. Install with: pip install chatterbox-tts")
            _LOAD_FAILED = True
        except Exception as e:
            print(f"❌ Failed to load Chatterbox: {e}")
            _LOAD_FAILED = True
    return _MODEL

def generate_cloned_audio(text, output_path, reference_audio_path):
    """
    Generates audio using Chatterbox TTS with voice cloning.
    Returns True if successful, False otherwise.
    """
    model = load_model()
    if not model:
        return False
        
    try:
        print(f"🎙️ Generating cloned audio for: '{text[:30]}...' using {os.path.basename(reference_audio_path)}")
        
        # Verify reference exists
        if not os.path.exists(reference_audio_path):
            print("❌ Reference audio not found.")
            return False
            
        # Run Inference
        # Based on inspection: generate(text, audio_prompt_path=...)
        audio = model.generate(text, audio_prompt_path=reference_audio_path)
        
        # Save to file
        # Check return type
        sr = 24000 # Chatterbox default usually
        data = audio
        
        if isinstance(audio, tuple):
            sr, data = audio
        
        # If data is tensor, move to cpu and numpy
        if hasattr(data, 'cpu'):
            data = data.cpu().numpy()
            
        # Ensure correct shape (N,) for mono audio
        if len(data.shape) > 1:
            # If shape is (1, N) -> squeeze to (N,)
            # If shape is (N, 1) -> squeeze to (N,)
            data = data.squeeze()
            
        sf.write(output_path, data, sr)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True, None
        else:
            print(f"❌ Generated audio too small or missing: {output_path}")
            return False, None
        
    except Exception as e:
        print(f"❌ Chatterbox Generation Error: {e}")
        return False, None
