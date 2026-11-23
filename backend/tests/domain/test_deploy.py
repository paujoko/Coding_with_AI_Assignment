"""The run guide and its checks: how the developer starts the program, verified by code."""

from wings.domain.deploy import RunGuide, RunTarget, check_deployment, command_problems, derive_start_command, guide_checked, run_target

CODE = {"todo/__init__.py", "todo/__main__.py", "todo/cli.py", "tools/report.py", "serve.py"}


def test_run_target_reads_modules_and_scripts():
    assert run_target("python -m todo list") == RunTarget(kind="module", name="todo")
    assert run_target("python3 -u -m todo.cli --port 8000") == RunTarget(kind="module", name="todo.cli")
    assert run_target("py serve.py --port 8000") == RunTarget(kind="script", name="serve.py")
    assert run_target('python -m todo add "Buy milk"') == RunTarget(kind="module", name="todo")


def test_run_target_is_none_for_what_wings_cannot_read():
    for command in ("./run.sh", "docker run todo", 'python -c "print(1)"', "python -m", "python", 'python -m todo "unclosed', "pythonista -m todo", ""):
        assert run_target(command) is None, command


def test_a_start_command_for_a_module_or_script_that_does_not_exist_is_a_problem():
    assert command_problems("python -m todo", CODE) == []
    assert command_problems("python -m tools.report", CODE) == []
    assert command_problems("python serve.py", CODE) == []
    assert "no such module" in command_problems("python -m shop", CODE)[0]
    assert "not in the project" in command_problems("python app.py", CODE)[0]
    assert "cannot check" in command_problems("./run.sh", CODE)[0]


def test_the_deployment_check_reports_a_run_guide_that_starts_nothing():
    files = {"Dockerfile": 'FROM python:3.12\nCOPY todo/ ./todo/\nCMD ["python", "-m", "todo"]\n'}
    good = RunGuide(start_command="python -m todo", example_commands=['python -m todo add "Buy milk"', "curl http://127.0.0.1:8000/"])
    assert check_deployment(files, CODE, good) == []
    bad = RunGuide(start_command="python -m shop", example_commands=["python -m shop list", "python -m todo list"])
    problems = check_deployment(files, CODE, bad)
    assert len(problems) == 2 and "The start command `python -m shop`" in problems[0] and "The example `python -m shop list`" in problems[1]
    copied = check_deployment(files, CODE, RunGuide(start_command="python -m todo --check"))
    assert len(copied) == 1 and "check option --check" in copied[0]  # the smoke command copied as the start command
    assert check_deployment(files, CODE) == []  # no guide: the old checks only
    assert check_deployment(files, CODE, RunGuide()) == []  # an empty start command is shown as unknown, not as a problem


def test_derive_start_command_drops_the_check_option_or_gives_up():
    assert derive_start_command("python -m shop --check") == "python -m shop"
    assert derive_start_command("python -m shop --port 8000 --check") == "python -m shop --port 8000"
    assert derive_start_command("python -m todo list") == "python -m todo list"  # nothing to drop: what was run is what is shown
    assert derive_start_command('python -m todo add "Buy milk" --dry-run') == 'python -m todo add "Buy milk"'
    assert derive_start_command('python -c "import todo"') == ""  # not safe: this starts no program
    assert derive_start_command("") == ""


def test_checked_means_the_passed_smoke_run_started_the_same_module():
    guide = RunGuide(start_command="python -m todo")
    assert guide_checked(guide, "python -m todo list", True, CODE)
    assert not guide_checked(guide, "python -m todo list", False, CODE)  # the smoke run failed
    assert not guide_checked(guide, "python -m tools.report", True, CODE)  # another module was run
    assert not guide_checked(guide, 'python -c "print(1)"', True, CODE)
    assert not guide_checked(RunGuide(start_command="python -m shop"), "python -m shop", True, CODE)  # no such module
    assert not guide_checked(RunGuide(), "python -m todo list", True, CODE)


def test_run_guide_reads_old_and_untidy_content():
    """Old projects and models that leave fields out or fill them oddly must still load."""
    assert RunGuide.model_validate({}) == RunGuide()
    guide = RunGuide.model_validate(
        {"start_command": "  python -m todo ", "url": "localhost:8000", "example_commands": ["a", " ", "b", "c", "d"], "stop_hint": None}
    )
    assert guide.start_command == "python -m todo" and guide.url is None and guide.example_commands == ["a", "b", "c"] and guide.stop_hint == ""
    assert RunGuide(url=" http://127.0.0.1:8000/ ").url == "http://127.0.0.1:8000/"


def test_run_guide_markdown_has_the_commands_in_code_blocks_and_says_what_was_checked():
    guide = RunGuide(start_command="python -m shop --port 8000", url="http://127.0.0.1:8000/", stop_hint="Ctrl+C", checked=True)
    text = guide.markdown()
    assert "```\npython -m shop --port 8000\n```" in text and "http://127.0.0.1:8000/" in text and "Stop: Ctrl+C" in text
    assert "Checked by Wings" in text
    cli = RunGuide(start_command="python -m todo", example_commands=['python -m todo add "Buy milk"', "python -m todo list"]).markdown()
    assert '```\npython -m todo add "Buy milk"\npython -m todo list\n```' in cli and "Not checked" in cli
    assert "No start command is known" in RunGuide().markdown()
