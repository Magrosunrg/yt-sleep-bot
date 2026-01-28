import torchaudio
print(f"Torchaudio version: {torchaudio.__version__}")
print(f"Available backends: {torchaudio.list_audio_backends()}")
try:
    import soundfile
    print("Soundfile is importable")
except ImportError:
    print("Soundfile not found")
