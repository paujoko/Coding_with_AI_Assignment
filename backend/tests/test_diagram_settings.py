"""Diagram rendering is set up from the UI: the public PlantUML server, or a downloaded plantuml.jar."""

import httpx

from wings.bootstrap import DiagramSettings, build_container
from wings.config import Settings, read_env_file


def test_public_server_can_be_switched_on_and_off(tmp_path):
    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    service = DiagramSettings(container, env_file=tmp_path / ".env", tools_dir=tmp_path / "tools")
    assert service.view()["mode"] in (None, "jar")  # depends on the machine; no server yet

    view = service.use_public_server(True)
    assert view["server_url"] == "https://www.plantuml.com/plantuml" and container.orchestrator.renderer.mode in ("server", "jar")
    assert read_env_file(tmp_path / ".env")["PLANTUML_SERVER_URL"] == "https://www.plantuml.com/plantuml"

    service.use_public_server(False)
    assert "PLANTUML_SERVER_URL" not in read_env_file(tmp_path / ".env")


def test_download_saves_the_jar_and_switches_to_it(tmp_path):
    jar_bytes = b"PK" + b"x" * 2_000_000  # looks like a jar of plausible size

    def handler(req: httpx.Request) -> httpx.Response:
        assert "plantuml" in str(req.url)
        return httpx.Response(200, content=jar_bytes)

    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = DiagramSettings(container, env_file=tmp_path / ".env", tools_dir=tmp_path / "tools", client=client)
    view = service.download_jar()
    jar = tmp_path / "tools" / "plantuml.jar"
    assert jar.read_bytes() == jar_bytes
    assert read_env_file(tmp_path / ".env")["PLANTUML_JAR"] == str(jar)
    assert view["jar_path"] == str(jar)


def test_a_failed_download_explains_itself_and_leaves_nothing(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404, text="not found")))
    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    service = DiagramSettings(container, env_file=tmp_path / ".env", tools_dir=tmp_path / "tools", client=client)
    import pytest

    from wings.domain.errors import InvalidInputError

    with pytest.raises(InvalidInputError, match="404"):
        service.download_jar()
    assert not (tmp_path / "tools" / "plantuml.jar").exists()
