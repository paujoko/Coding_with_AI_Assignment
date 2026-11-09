"""ASGI entry point: `uvicorn wings.main:app --port 8810`."""

from wings.api.app import create_app
from wings.bootstrap import build_container

container = build_container()
app = create_app(container.orchestrator, container.info())
