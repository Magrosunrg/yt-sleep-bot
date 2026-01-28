import os
import requests
import zipfile
import io

ARIA2_URL = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"
TOOLS_DIR = os.path.join(os.getcwd(), "tools")
ARIA2_EXE = os.path.join(TOOLS_DIR, "aria2c.exe")

def setup_aria2():
    if os.path.exists(ARIA2_EXE):
        print(f"✅ Aria2 already installed at: {ARIA2_EXE}")
        return True

    if not os.path.exists(TOOLS_DIR):
        os.makedirs(TOOLS_DIR)

    print(f"⬇️ Downloading Aria2 from {ARIA2_URL}...")
    try:
        r = requests.get(ARIA2_URL)
        r.raise_for_status()
        
        print("📦 Extracting...")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            # Find the exe in the zip
            for name in z.namelist():
                if name.endswith("aria2c.exe"):
                    # Extract specifically this file to TOOLS_DIR
                    with z.open(name) as source, open(ARIA2_EXE, "wb") as target:
                        target.write(source.read())
                    print(f"✅ Aria2 installed successfully to {ARIA2_EXE}")
                    return True
    except Exception as e:
        print(f"❌ Failed to setup Aria2: {e}")
        return False

if __name__ == "__main__":
    setup_aria2()
