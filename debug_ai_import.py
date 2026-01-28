
import sys
import traceback

print("1. Importing diffusers...")
try:
    from diffusers import StableDiffusionPipeline
    print("   Success importing StableDiffusionPipeline")
except Exception:
    traceback.print_exc()

print("\n2. Importing ai_visual_generator...")
try:
    import ai_visual_generator
    print("   Success importing ai_visual_generator")
except Exception:
    traceback.print_exc()
