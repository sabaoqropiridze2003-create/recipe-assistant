from types import SimpleNamespace as NS

from app.observability import build_tracer, redact


def test_emails_tokens_and_keys_are_removed_from_traces():
    text = (
        "my email is anna.k@example.com and my token is "
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMiJ9.abcDEF123_-xyz and the key AIzaSyA1234567890abcdefghijklmnopqrstuv"
    )
    cleaned = redact(text)
    assert "anna.k@example.com" not in cleaned and "<email>" in cleaned
    assert "eyJhbGci" not in cleaned and "<jwt>" in cleaned
    assert "AIzaSy" not in cleaned and "<api-key>" in cleaned


def test_normal_cooking_text_is_not_changed():
    text = "I have chicken, rice and broccoli. 30 minutes please, 2 servings."
    assert redact(text) == text


def test_tracing_is_off_unless_it_is_switched_on_and_has_a_key():
    assert build_tracer(NS(langsmith_tracing=False, langsmith_api_key="key", langsmith_project="p")) is None
    assert build_tracer(NS(langsmith_tracing=True, langsmith_api_key="", langsmith_project="p")) is None
