from gtts import gTTS
import os
import uuid


def speak(text: str):
    """
    Converts text to speech using Google TTS.
    Saves an mp3 file.
    """

    if not text:
        return

    filename = f"tts_{uuid.uuid4().hex}.mp3"
    tts = gTTS(text=text, lang="en")
    tts.save(filename)

    os.system(f"start {filename}")  # Windows
