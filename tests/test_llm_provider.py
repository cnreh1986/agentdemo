from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.config.settings import Settings
from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.providers.llm_base import ProviderError
from src.providers.litellm_provider import LiteLLMProvider


def test_litellm_status_missing_credentials():
    settings = Settings(openai_api_key=None, llm_model="openai/gpt-4o-mini")
    provider = LiteLLMProvider(settings)
    status = provider.status()
    assert status.ready is False


def test_litellm_status_ready():
    settings = Settings(openai_api_key="sk-test", llm_model="openai/gpt-4o-mini")
    provider = LiteLLMProvider(settings)
    assert provider.status().ready is True


def test_litellm_maps_timeout():
    settings = Settings(openai_api_key="sk-test", llm_model="openai/gpt-4o-mini", llm_max_retries=0)
    provider = LiteLLMProvider(settings)
    with patch("src.providers.litellm_provider.litellm") as mock_litellm:
        mock_litellm.completion.side_effect = Exception("timeout talking to host")
        with pytest.raises(ProviderError) as exc:
            provider.complete_json(
                system_prompt="s", user_prompt="{}", schema_name="research"
            )
        assert exc.value.code == "timeout"


def test_structured_output_retry_then_success():
    settings = Settings(
        openai_api_key="sk-test",
        llm_model="openai/gpt-4o-mini",
        llm_max_retries=0,
        structured_output_retries=1,
    )
    provider = LiteLLMProvider(settings)
    bad = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))])
    good = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
    )
    with patch("src.providers.litellm_provider.litellm") as mock_litellm:
        mock_litellm.completion.side_effect = [bad, good]
        data = provider.complete_json(system_prompt="s", user_prompt="{}", schema_name="x")
        assert data == {"ok": True}
        assert mock_litellm.completion.call_count == 2


def test_live_graph_with_demo_provider_as_mock():
    # Full live path shape using DemoProvider stand-in (no network)
    runner = WorkforceRunner(DemoProvider(), max_revisions=1)
    state = runner.run(task="Plan my next productive week.", mode="live")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["model_configuration"]["provider"] == "demo"
