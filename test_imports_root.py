print("Starting test")
try:
    from moviepy.video.fx.resize import resize
    print("Import moviepy.video.fx.resize.resize successful")
except ImportError as e:
    print(f"Error importing moviepy.video.fx.resize.resize: {e}")
except Exception as e:
    print(f"Exception importing moviepy.video.fx.resize.resize: {e}")

try:
    from moviepy.video.fx.mask_color import mask_color
    print("Import moviepy.video.fx.mask_color.mask_color successful")
except ImportError as e:
    print(f"Error importing moviepy.video.fx.mask_color.mask_color: {e}")
except Exception as e:
    print(f"Exception importing moviepy.video.fx.mask_color.mask_color: {e}")
