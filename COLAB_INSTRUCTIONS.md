# Running on Google Colab

Follow these steps to run the video generator on Google Colab using GitHub.

## Prerequisite: Push to GitHub
Since you are running this locally first, you need to push this code to a GitHub repository.

1.  Create a new repository on GitHub (e.g., `yt-sleep-bot`).
2.  Run these commands in your local terminal:
    ```bash
    git remote add origin https://github.com/Magrosunrg/yt-sleep-bot.git
    git branch -M main
    git push -u origin main
    ```
3.  **IMPORTANT**: Do NOT commit `client_secret.json` or `token.pickle` if your repo is public.

## Step 1: Setup in Colab
Open a new Google Colab notebook and run this cell to clone your code and install dependencies.

```python
# 1. Clone Repository
!git clone https://github.com/Magrosunrg/yt-sleep-bot.git
%cd yt-sleep-bot

# 2. System Dependencies
!apt-get update
!apt-get install -y imagemagick ffmpeg aria2

# 3. Fix ImageMagick Policy
!sed -i '/<policy domain="path" rights="none" pattern="@\*"\/>/d' /etc/ImageMagick-6/policy.xml

# 4. Install Python Packages
!pip install -r requirements.txt
!pip install moviepy==1.0.3
!pip install diffusers transformers accelerate sentencepiece protobuf bitsandbytes
!pip install -U torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121

# 5. Install Ollama (Local LLM)
!curl -fsSL https://ollama.com/install.sh | sh

# 6. Start Ollama in Background
import subprocess
import time
import os

# Set OLLAMA_HOST to bind to localhost
os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"

print("🚀 Starting Ollama Server...")
# Use nohup and full path to ensure it runs in background and persists
process = subprocess.Popen("nohup /usr/local/bin/ollama serve > ollama.log 2>&1 &", shell=True)
time.sleep(10) # Give it more time to start

# 7. Pull Model
print("📥 Pulling llama3 model...")
!/usr/local/bin/ollama pull llama3
print("✅ Ready!")
```

## Step 2: Upload Secrets
Since we excluded secrets from GitHub, you must upload them manually to the `yt-sleep-bot` folder in Colab:
1.  Click the **Folder Icon** (Files) on the left sidebar.
2.  Navigate into `yt-sleep-bot`.
3.  Right-click -> **Upload**.
4.  Upload your `client_secret.json` (and `token.pickle` if you have it).

## Step 3: Run the Generator

### Option A: Sleep Video (Fast Render)
```bash
!python colab_runner.py sleep --topic "Ancient Forests" --num_facts 50 --duration 3600
```
*   **Optimization**: Now uses FFmpeg filters for 10x faster rendering!
*   `--use_ai`: Add this flag to force AI-generated animated backgrounds (instead of YouTube search).

### Option B: Story Short (AI Mode)
Generate a story with AI visuals (no movie clips needed):
```bash
!python colab_runner.py story --prompt "A cyberpunk detective in the rain" --use_ai
```
*   `--use_ai`: Generates 5-8s AI video clips for each scene using Stable Diffusion v1.5 (Text-to-Image) with Ken Burns effect.
*   `--output`: (Optional) Specify filename.

## Troubleshooting
*   **OOM (Out of Memory)**: Ensure you are using a GPU runtime (Runtime > Change runtime type > T4 GPU).
*   **Audio Issues**: If TTS fails, check if `edge-tts` is working or try a different voice.
