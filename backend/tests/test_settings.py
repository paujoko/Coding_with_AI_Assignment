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
