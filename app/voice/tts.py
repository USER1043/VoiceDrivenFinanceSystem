from gtts import gTTS
import os
import uuid
import subprocess

TTS_DIR = "audio_outputs"
os.makedirs(TTS_DIR, exist_ok=True)


def synthesize_speech(text: str) -> str:
    """
    Converts text to speech using Google TTS.
    Saves and plays an MP3 file on Windows.
    Returns the file path.
    """

    if not text:
        raise ValueError("Text is required for TTS")

    filename = f"tts_{uuid.uuid4().hex}.mp3"
    file_path = os.path.join(TTS_DIR, filename)

    tts = gTTS(text=text, lang="en")
    tts.save(file_path)

    # Play audio on Windows (non-blocking)
    try:
        subprocess.Popen(
            ["powershell", "-c", f'Start-Process "{file_path}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass  # Audio still saved even if playback fails

    return file_path
    