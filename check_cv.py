
import cv2
import sys

print(f"OpenCV Version: {cv2.__version__}")
try:
    print(f"Haar Path: {cv2.data.haarcascades}")
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if cascade.empty():
        print("❌ Cascade failed to load")
    else:
        print("✅ Cascade loaded")
except Exception as e:
    print(f"❌ Haar error: {e}")

try:
    saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
    print("✅ Saliency available")
except AttributeError:
    print("❌ Saliency NOT available (requires opencv-contrib-python)")
except Exception as e:
    print(f"❌ Saliency error: {e}")
