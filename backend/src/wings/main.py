"""ASGI entry point: `uvicorn wings.main:app --port 8810`."""

from wings.adapters.llm_log import attach_llm_log
from wings.api.app import create_app
from wings.bootstrap import DiagramSettings, LLMSettings, build_container

container = build_container()
# Every prompt and reply of a run, next to the projects in the (git-ignored) workspace.
attach_llm_log(container.settings.workspace_dir)
app = create_app(container.orchestrator, container.info, settings=LLMSettings(container), diagrams=DiagramSettings(container), picker=container.picker)
