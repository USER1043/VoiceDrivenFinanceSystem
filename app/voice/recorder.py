import os
from fastapi import UploadFile
from datetime import datetime

AUDIO_DIR = "audio_inputs"

os.makedirs(AUDIO_DIR, exist_ok=True)

async def save_audio_file(audio: UploadFile) -> str:
    """
    Saves uploaded audio file and returns file path
    """
    if audio.content_type not in ["audio/wav", "audio/x-wav"]:
        raise ValueError("Invalid audio format. Only WAV supported.")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"voice_{timestamp}.wav"
    file_path = os.path.join(AUDIO_DIR, filename)

    with open(file_path, "wb") as f:
        content = await audio.read()
        f.write(content)

    return file_path
