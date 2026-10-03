from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.models import Budget, PendingAction, PendingStatus, Transaction
from app.nlu import stt
from app.routers import commands as commands_router
from tests.helpers import account_id, category_id


def _say(client, text, previous=None):
    body = {"text": text} | ({"previous": previous} if previous else {})
    response = client.post("/api/commands", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_status_without_keys(client, seeded):
    assert client.get("/api/voice/status").json() == {"server_stt": False, "llm": []}


def test_typed_expense_is_proposed_then_confirmed(client, seeded):
    out = _say(client, "chai 20 cash")
    assert out["status"] == "proposal"
    assert out["parser"] == "rules"
    assert out["message"].startswith("₹20 for Tea & snacks, paid by Cash, today")
    data = out["action"]["data"]
    assert data["amount_paise"] == 2000
    assert data["category_id"] == category_id(seeded, "Tea & snacks")
    assert data["account_id"] == account_id(seeded, "Cash")
    assert seeded.scalars(select(Transaction)).all() == []  # nothing written yet

    confirmed = client.post(f"/api/pending-actions/{out['action']['id']}/confirm")
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["message"] == "Saved ₹20."
    assert body["transaction"]["source"] == "text"
    txn = seeded.scalar(select(Transaction))
    assert txn.raw_text == "chai 20 cash"

    again = client.post(f"/api/pending-actions/{out['action']['id']}/confirm")
    assert again.status_code == 409


def test_card_corrections_are_applied(client, seeded):
    out = _say(client, "paid 300")
    groceries = category_id(seeded, "Groceries")
    confirmed = client.post(
        f"/api/pending-actions/{out['action']['id']}/confirm",
        json={"category_id": groceries, "amount_paise": 32000, "merchant": "DMart"},
    )
    assert confirmed.status_code == 200
    txn = confirmed.json()["transaction"]
    assert (txn["category_id"], txn["amount_paise"], txn["merchant"]) == (groceries, 32000, "DMart")


def test_invalid_correction_is_rejected(client, seeded):
    out = _say(client, "chai 20")
    salary = category_id(seeded, "Salary")  # income category on an expense
    response = client.post(
        f"/api/pending-actions/{out['action']['id']}/confirm", json={"category_id": salary}
    )
    assert response.status_code == 422
    assert seeded.scalars(select(Transaction)).all() == []


def test_budget_command(client, seeded):
    out = _say(client, "set food budget to 6000")
    assert out["message"] == "Set the Food budget to ₹6,000 a month?"
    confirmed = client.post(f"/api/pending-actions/{out['action']['id']}/confirm").json()
    assert confirmed["message"] == "Budget set to ₹6,000 a month."
    budget = seeded.scalar(select(Budget))
    assert (budget.category_id, budget.amount_paise) == (category_id(seeded, "Food"), 600000)


def test_follow_up_answers_the_question(client, seeded):
    first = _say(client, "paid for auto")
    assert first["status"] == "clarify"
    assert first["message"] == "How much was it?"
    second = _say(client, "120", previous="paid for auto")
    assert second["status"] == "proposal"
    assert second["action"]["data"]["amount_paise"] == 12000
    assert second["transcript"] == "120"


def test_unsupported(client, seeded):
    out = _say(client, "what's my balance?")
    assert out["status"] == "unsupported"
    assert out["action"] is None


def test_cancel(client, seeded):
    out = _say(client, "chai 20")
    action_id = out["action"]["id"]
    assert client.post(f"/api/pending-actions/{action_id}/cancel").status_code == 204
    assert client.post(f"/api/pending-actions/{action_id}/confirm").status_code == 409
    assert seeded.get(PendingAction, action_id).status == PendingStatus.CANCELLED


def test_expired_actions_cannot_be_confirmed(client, seeded):
    out = _say(client, "chai 20")
    action_id = out["action"]["id"]
    seeded.execute(
        update(PendingAction).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    response = client.post(f"/api/pending-actions/{action_id}/confirm")
    assert response.status_code == 409
    assert "expired" in response.json()["detail"]


def test_voice_needs_server_stt(client, seeded):
    response = client.post("/api/voice", files={"audio": ("a.webm", b"x", "audio/webm")})
    assert response.status_code == 503


class FakeTranscriber:
    def __init__(self, text="swiggy 450 on gpay", fail=False):
        self.text, self.fail = text, fail

    def transcribe(self, audio, filename, content_type, vocab):
        if self.fail:
            raise stt.TranscriptionError("boom")
        assert audio == b"fake-audio"
        assert "swiggy" in stt._prompt(vocab)  # aliases bias the transcription
        return self.text


@pytest.fixture
def fake_stt(monkeypatch):
    def install(**kwargs):
        monkeypatch.setattr(
            commands_router, "transcriber_from_settings", lambda s: FakeTranscriber(**kwargs)
        )

    return install


def test_voice_command(client, seeded, fake_stt):
    fake_stt()
    response = client.post("/api/voice", files={"audio": ("a.webm", b"fake-audio", "audio/webm")})
    assert response.status_code == 200
    out = response.json()
    assert out["transcript"] == "swiggy 450 on gpay"
    assert out["action"]["data"]["category_id"] == category_id(seeded, "Eating out")
    confirmed = client.post(f"/api/pending-actions/{out['action']['id']}/confirm").json()
    assert confirmed["transaction"]["source"] == "voice"


def test_voice_transcription_failure(client, seeded, fake_stt):
    fake_stt(fail=True)
    response = client.post("/api/voice", files={"audio": ("a.webm", b"fake-audio", "audio/webm")})
    assert response.status_code == 502


def test_voice_too_long(client, seeded, fake_stt):
    fake_stt()
    big = b"x" * (stt.MAX_AUDIO_BYTES + 1)
    response = client.post("/api/voice", files={"audio": ("a.webm", big, "audio/webm")})
    assert response.status_code == 413


def test_groq_transcriber_request(monkeypatch):
    import httpx

    from app.nlu.vocab import Vocabulary

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = request.content
        return httpx.Response(200, json={"text": " chai 20 "})

    t = stt.GroqTranscriber(
        "key", "https://groq.test/v1", "whisper-large-v3-turbo", 5, httpx.MockTransport(handler)
    )
    assert t.transcribe(b"audio", "a.webm", "audio/webm", Vocabulary.from_seed()) == "chai 20"
    assert seen["url"] == "https://groq.test/v1/audio/transcriptions"
    assert b"whisper-large-v3-turbo" in seen["body"]
    assert b'name="language"' in seen["body"]


def test_browser_transcribed_commands_are_marked_voice(client, seeded):
    out = client.post("/api/commands", json={"text": "chai 20", "via": "voice"}).json()
    confirmed = client.post(f"/api/pending-actions/{out['action']['id']}/confirm").json()
    assert confirmed["transaction"]["source"] == "voice"
