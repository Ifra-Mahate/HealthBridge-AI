import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def offline_ai(monkeypatch):
    """Tests always use the rule engine: no network calls, no API quota, same result every run."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
