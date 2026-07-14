"""Unit tests for RealLLMProvider credential precedence (no network)."""

import builtins

import pytest

from worker import explainer


@pytest.fixture(autouse=True)
def _reset_dotenv_flag(monkeypatch):
    monkeypatch.setattr(explainer, "_DOTENV_LOADED", True)


def test_provider_prefers_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    provider = explainer.RealLLMProvider()
    assert provider.provider_type == "anthropic"
    assert provider.model_id == "claude-3-haiku-20240307"


def test_provider_falls_back_to_openai(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    provider = explainer.RealLLMProvider()
    assert provider.provider_type == "openai"
    assert provider.model_id == "gpt-4o-mini"


def test_provider_vertex_via_project(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-gcp-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
    monkeypatch.delenv("GOOGLE_MODEL_ID", raising=False)
    provider = explainer.RealLLMProvider()
    assert provider.provider_type == "google"
    assert provider.model_id == "gemini-3.5-flash"
    assert provider.google_project == "my-gcp-project"
    assert provider.google_location == "europe-west1"


def test_provider_vertex_model_override(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-gcp-project")
    monkeypatch.setenv("GOOGLE_MODEL_ID", "gemini-2.5-flash")
    provider = explainer.RealLLMProvider()
    assert provider.model_id == "gemini-2.5-flash"


def test_provider_none_without_google(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEX", raising=False)

    real_import = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google" or name.startswith("google."):
            raise ImportError("blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)
    provider = explainer.RealLLMProvider()
    assert provider.provider_type is None
    assert provider.api_key is None
