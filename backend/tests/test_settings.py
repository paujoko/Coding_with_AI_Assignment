"""Settings: .env is read at start, and the model provider can be switched from the UI without a restart."""

from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.llm_openai import OpenAILLM
from wings.bootstrap import LLMSettings, NotConfiguredLLM, build_container
from wings.config import Settings, read_env_file, write_env_file


def test_env_file_is_read_and_real_environment_wins(tmp_path):
    env = tmp_path / ".env"
    env.write_text('# comment\nWINGS_LLM_PROVIDER=openai\nOPENAI_API_KEY="sk-file"\nWINGS_MODEL_MID=gpt-x\n', encoding="utf-8")
    s = Settings.from_env({"WINGS_MODEL_MID": "from-env"}, env_file=env)
    assert (s.llm_provider, s.openai_api_key, s.models["mid"]) == ("openai", "sk-file", "from-env")
    assert s.models["small"] == Settings.default_models("openai")["small"]


def test_writing_the_env_file_keeps_comments_and_other_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# keep me\nPLANTUML_JAR=C:/tools/plantuml.jar\nOPENAI_API_KEY=old\n", encoding="utf-8")
    write_env_file(env, {"OPENAI_API_KEY": "sk-new", "WINGS_LLM_PROVIDER": "openai"})
    text = env.read_text(encoding="utf-8")
    assert text.startswith("# keep me\nPLANTUML_JAR=C:/tools/plantuml.jar\n")
    assert read_env_file(env) == {"PLANTUML_JAR": "C:/tools/plantuml.jar", "OPENAI_API_KEY": "sk-new", "WINGS_LLM_PROVIDER": "openai"}


def test_switching_provider_writes_env_and_swaps_the_llm_without_restart(tmp_path):
    env = tmp_path / ".env"
    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    service = LLMSettings(container, env_file=env)
    assert isinstance(container.orchestrator.llm, ScriptedLLM)

    view = service.update("openai", api_key="sk-abcdefgh1234", models=None)
    assert isinstance(container.orchestrator.llm, OpenAILLM)
    assert view["provider"] == "openai" and view["key_set"] and view["key_hint"] == "sk-…1234"
    assert "sk-abcdefgh1234" not in str(view)  # the key never goes back to the browser
    assert read_env_file(env)["OPENAI_API_KEY"] == "sk-abcdefgh1234"
    assert view["models"]["mid"] == Settings.default_models("openai")["mid"]

    # Saving again without a key keeps the saved one.
    service.update("openai", api_key=None, models={"small": "a", "mid": "b", "frontier": "c"})
    assert read_env_file(env)["OPENAI_API_KEY"] == "sk-abcdefgh1234" and read_env_file(env)["WINGS_MODEL_MID"] == "b"

    service.update("mock", api_key=None, models=None)
    assert isinstance(container.orchestrator.llm, ScriptedLLM)


def test_a_provider_without_key_explains_what_to_do(tmp_path):
    container = build_container(Settings(workspace_dir=tmp_path / "ws", llm_provider="openai"))
    assert isinstance(container.orchestrator.llm, NotConfiguredLLM)
    assert container.info()["llm_ready"] is False
    result = LLMSettings(container, env_file=tmp_path / ".env").test()
    assert result["ok"] is False and "Settings" in result["error"]


def test_connection_test_on_the_mock_needs_no_network(tmp_path):
    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    result = LLMSettings(container, env_file=tmp_path / ".env").test()
    assert result["ok"] is True and "mock" in result["message"].lower()


def test_anthropic_is_a_provider_with_its_own_key_models_and_effort(tmp_path):
    from wings.adapters.llm_anthropic import AnthropicLLM

    env = tmp_path / ".env"
    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    service = LLMSettings(container, env_file=env)
    assert service.view()["defaults"]["anthropic"] == {"small": "claude-haiku-5-5", "mid": "claude-sonnet-5-5", "frontier": "claude-sonnet-5-5"}

    view = service.update("anthropic", api_key="sk-ant-api03-abcd5678", models=None, efforts={"frontier": "low", "mid": ""})
    assert isinstance(container.orchestrator.llm, AnthropicLLM)
    assert view["provider"] == "anthropic" and view["keys"]["anthropic"] == {"set": True, "hint": "sk-…5678"}
    assert "abcd5678" not in str({k: v for k, v in view.items() if k != "keys"})
    saved = read_env_file(env)
    assert saved["ANTHROPIC_API_KEY"] == "sk-ant-api03-abcd5678"
    assert saved["WINGS_MODEL_FRONTIER"] == "claude-sonnet-5-5" and saved["WINGS_EFFORT_FRONTIER"] == "low"
    assert "WINGS_EFFORT_MID" not in saved
    assert view["efforts"] == {"frontier": "low"}

    again = Settings.from_env({}, env_file=env)
    assert (again.llm_provider, again.anthropic_api_key, again.efforts) == ("anthropic", "sk-ant-api03-abcd5678", {"frontier": "low"})


def test_an_unknown_effort_is_refused(tmp_path):
    import pytest

    from wings.domain.errors import InvalidInputError

    service = LLMSettings(build_container(Settings(workspace_dir=tmp_path / "ws")), env_file=tmp_path / ".env")
    with pytest.raises(InvalidInputError, match="effort"):
        service.update("anthropic", api_key="sk-ant-x-12345678", models=None, efforts={"mid": "turbo"})


def test_anthropic_without_key_explains_what_to_do(tmp_path):
    container = build_container(Settings(workspace_dir=tmp_path / "ws", llm_provider="anthropic"))
    assert isinstance(container.orchestrator.llm, NotConfiguredLLM)
    assert "ANTHROPIC_API_KEY" in LLMSettings(container, env_file=tmp_path / ".env").test()["error"]


def test_anthropic_base_url_comes_from_the_environment(tmp_path):
    s = Settings.from_env({"WINGS_LLM_PROVIDER": "anthropic", "ANTHROPIC_BASE_URL": "https://proxy.example"}, env_file=None)
    assert s.anthropic_base_url == "https://proxy.example"
    assert s.models == Settings.default_models("anthropic")
