from app.voice.tts import speak


def test_tts_basic():
    """
    Simple TTS sanity test.
    """
    result = {
        "category": "food",
        "amount": 600
    }

    text = f"Your {result['category']} budget is set to {result['amount']} rupees"
    

    audio_path = speak(text)

    print("TTS generated at:", audio_path)


if __name__ == "__main__":
    test_tts_basic()
