import whisper
import os

# Load Whisper model once (important for performance)
_model = None


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes a WAV audio file to text using Whisper.
    """

    if not os.path.exists(audio_path):
        raise FileNotFoundError("Audio file not found")

    model = get_model()
    result = model.transcribe(audio_path)

    text = result.get("text", "").strip()
    return text
