
print("Start import test...")
try:
    import short_uploader_gui
    print("✅ Successfully imported short_uploader_gui")
except ImportError as e:
    print(f"❌ ImportError: {e}")
except Exception as e:
    print(f"❌ Exception: {e}")
