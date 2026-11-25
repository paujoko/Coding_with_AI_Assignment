"""ASGI entry point: `uvicorn wings.main:app --port 8810`."""

import logging
import logging.handlers
from pathlib import Path

from wings.api.app import create_app
from wings.bootstrap import DiagramSettings, LLMSettings, build_container

_log_file = Path(__file__).parents[3] / "wings_llm.log"
_handler = logging.handlers.RotatingFileHandler(_log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
logging.getLogger("wings.llm").setLevel(logging.DEBUG)
logging.getLogger("wings.llm").addHandler(_handler)

container = build_container()
app = create_app(container.orchestrator, container.info, settings=LLMSettings(container), diagrams=DiagramSettings(container), picker=container.picker)
