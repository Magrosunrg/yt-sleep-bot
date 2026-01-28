
print("Start")
import sys
try:
    import torchvision
    print("Torchvision imported")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
print("End")
