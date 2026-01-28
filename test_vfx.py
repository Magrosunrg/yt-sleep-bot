try:
    from moviepy import vfx
    print("from moviepy import vfx successful")
except ImportError as e:
    print(f"Error from moviepy import vfx: {e}")
except Exception as e:
    print(f"Exception from moviepy import vfx: {e}")
