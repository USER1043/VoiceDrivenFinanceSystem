import subprocess
import os

def preprocess_audio(input_path: str) -> str:
    """
    Converts audio to:
    - mono
    - 16kHz
    - normalized loudness
    """
    output_path = input_path.replace(".wav", "_clean.wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ac", "1",          # mono
        "-ar", "16000",      # 16kHz (Whisper expects this)
        "-af", "loudnorm",   # normalize volume
        output_path
    ]

    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return output_path
