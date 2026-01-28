
print("Importing os...")
import os
print("Importing long_video_mgr...")
try:
    import long_video_mgr
    print("Success")
except Exception as e:
    print(f"Fail: {e}")
    import traceback
    traceback.print_exc()
