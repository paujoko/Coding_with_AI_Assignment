"""The LLM log (every prompt and reply of a run) is written into the workspace, never into the repository."""

import logging
from pathlib import Path

import pytest

from wings.adapters.llm_log import LOGGER, attach_llm_log


@pytest.fixture
def clean_logger():
    log = logging.getLogger(LOGGER)
    before = list(log.handlers)
    yield log
    for handler in log.handlers[:]:
        if handler not in before:
            log.removeHandler(handler)
            handler.close()


def test_the_log_goes_into_the_given_workspace(tmp_path: Path, clean_logger: logging.Logger):
    path = attach_llm_log(tmp_path / "workspace")
    clean_logger.debug("REQUEST agent=analyst")
    for handler in clean_logger.handlers:
        handler.flush()
    assert path == (tmp_path / "workspace" / "wings_llm.log").resolve()
    assert "REQUEST agent=analyst" in path.read_text(encoding="utf-8")


def test_attaching_twice_writes_each_line_once(tmp_path: Path, clean_logger: logging.Logger):
    attach_llm_log(tmp_path)
    path = attach_llm_log(tmp_path)
    clean_logger.debug("one line")
    for handler in clean_logger.handlers:
        handler.flush()
    assert path.read_text(encoding="utf-8").count("one line") == 1
