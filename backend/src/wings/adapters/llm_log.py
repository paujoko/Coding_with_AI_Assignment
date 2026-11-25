"""The LLM log: every request, reply and tool call of a run (logger `wings.llm`) in a rotating file.

It holds whole prompts and replies, so it lives in the workspace (runtime data, git-ignored) and
never in the repository. The real adapters and `LLMAgent` write to the logger; only the server
entry point (`wings.main`) attaches the file, so tests and the CLI write nothing.
"""

import logging
import logging.handlers
from pathlib import Path

LOGGER = "wings.llm"
FILE_NAME = "wings_llm.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUPS = 3


def attach_llm_log(directory: Path) -> Path:
    """Write the LLM log to `<directory>/wings_llm.log` (10 MB, three older files). Idempotent."""
    directory.mkdir(parents=True, exist_ok=True)
    path = (directory / FILE_NAME).resolve()
    log = logging.getLogger(LOGGER)
    log.setLevel(logging.DEBUG)
    if not any(isinstance(h, logging.FileHandler) and Path(h.baseFilename) == path for h in log.handlers):
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        log.addHandler(handler)
    return path
