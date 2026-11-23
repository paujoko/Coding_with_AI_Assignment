"""Paths in the settings: a stale PLANTUML_JAR falls back to tools/plantuml.jar; where default project folders go."""

from pathlib import Path

from wings import config
from wings.config import Settings


def test_a_configured_jar_that_exists_is_used(tmp_path, monkeypatch):
    jar = tmp_path / "my" / "plantuml.jar"
    jar.parent.mkdir()
    jar.write_bytes(b"jar")
    monkeypatch.setattr(config, "TOOLS_DIR", tmp_path / "tools")
    assert Settings.from_env({"PLANTUML_JAR": str(jar)}, env_file=None).plantuml_jar == jar


def test_a_stale_jar_path_falls_back_to_the_downloaded_jar(tmp_path, monkeypatch):
    """Real case: the project folder was moved, .env still named the old path, and no diagram was drawn."""
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "plantuml.jar").write_bytes(b"jar")
    monkeypatch.setattr(config, "TOOLS_DIR", tools)
    settings = Settings.from_env({"PLANTUML_JAR": str(tmp_path / "moved-away" / "plantuml.jar")}, env_file=None)
    assert settings.plantuml_jar == tools / "plantuml.jar"


def test_a_stale_jar_path_without_any_jar_means_no_jar(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOOLS_DIR", tmp_path / "tools")
    assert Settings.from_env({"PLANTUML_JAR": str(tmp_path / "gone.jar")}, env_file=None).plantuml_jar is None
    assert Settings.from_env({"PLANTUML_JAR": str(tmp_path)}, env_file=None).plantuml_jar is None  # a folder is not a jar


def test_projects_dir_comes_from_the_environment_or_the_home_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert Settings.from_env({}, env_file=None).projects_dir == tmp_path / "home" / "WingsProjects"
    assert Settings.from_env({"WINGS_PROJECTS_DIR": str(tmp_path / "mine")}, env_file=None).projects_dir == tmp_path / "mine"
    assert Settings.from_env({"WINGS_PROJECTS_DIR": "  "}, env_file=None).projects_dir == tmp_path / "home" / "WingsProjects"


def test_settings_built_by_hand_have_no_projects_dir():
    """Tests build Settings(workspace_dir=...) and must never write into the real home folder."""
    assert Settings().projects_dir is None
