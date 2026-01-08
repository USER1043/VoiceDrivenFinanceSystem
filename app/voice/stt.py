import whisper
import os
from app.voice.audio_preprocess import preprocess_audio

model = whisper.load_model("small")  # small > base for accents


def speech_to_text(audio_path: str) -> str:
    if not audio_path or not os.path.exists(audio_path):
        raise ValueError("Audio file does not exist")

    clean_audio = preprocess_audio(audio_path)

    result = model.transcribe(
        clean_audio,
        language="en",
        fp16=False,                 # REQUIRED on Windows
        temperature=0.0,            # no randomness
        condition_on_previous_text=False,
        initial_prompt=(
            "The user gives short finance commands like "
            "'set food budget to 6000', "
            "'add expense 250 food', "
            "'check balance'."
        ),
        no_speech_threshold=0.25,
        logprob_threshold=-1.0,
        compression_ratio_threshold=2.2
    )

    text = result.get("text", "").strip().lower()
    return text
