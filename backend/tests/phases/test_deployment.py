"""P6 Deployment: files checked by code, the program started for real."""

import copy

from wings.adapters.sandbox import LocalSandbox
from wings.domain.deploy import check_deployment
from wings.domain.phases import PhaseId as P


def deployed_orch(make_orchestrator, script, walk):
    orch = make_orchestrator(script)
    orch.sandbox = LocalSandbox()
    pid = walk(orch, P.DEPLOYMENT)
    return orch, pid


def test_prepare_writes_files_checks_them_and_starts_the_program(make_orchestrator, demo_script, walk):
    orch, pid = deployed_orch(make_orchestrator, demo_script, walk)
    result = orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    check = orch.store.get_artifact(pid, "deployment-check")
    assert check.content["passed"] and check.content["exit_code"] == 0 and "No tasks." in check.content["output"]
    assert {a.id for a in result.outcome.artifacts} >= {"deploy-dockerfile", "deploy-run-sh", "deploy-run-ps1", "deploy-deploy-md"}
    assert orch.store.get_artifact(pid, "deploy-dockerfile").path == "app/Dockerfile"
    assert "Check passed" in result.outcome.reply


def test_a_dockerfile_that_copies_missing_files_fails_the_check(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    docker = next(f for f in script["deployer"][0]["files"] if f["path"] == "Dockerfile")
    docker["content"] = docker["content"].replace("COPY todo/ ./todo/", "COPY src/ ./src/")
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    check = orch.store.get_artifact(pid, "deployment-check")
    assert not check.content["passed"] and any("src" in p for p in check.content["problems"])


def test_static_checks():
    code = {"todo/__main__.py", "todo/cli.py"}
    ok = {"Dockerfile": 'FROM python:3.12\nCOPY todo/ ./todo/\nENTRYPOINT ["python", "-m", "todo"]\n', "run.sh": "python3 -m todo \"$@\""}
    assert check_deployment(ok, code) == []
    bad = {"Dockerfile": "FROM python:3.12\nCOPY app.py .\n", "run.ps1": "python -m shop list"}
    problems = check_deployment(bad, code)
    assert any("app.py" in p for p in problems) and any("CMD or ENTRYPOINT" in p for p in problems) and any("shop" in p for p in problems)


def test_deployment_is_approved_only_when_its_check_passed_on_the_current_files(make_orchestrator, demo_script, walk):
    import pytest

    from wings.domain.errors import InvalidTransitionError

    script = copy.deepcopy(demo_script)
    docker = next(f for f in script["deployer"][0]["files"] if f["path"] == "Dockerfile")
    docker["content"] = docker["content"].replace("COPY todo/ ./todo/", "COPY src/ ./src/")
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    with pytest.raises(InvalidTransitionError, match="did not pass"):
        orch.approve(pid, P.DEPLOYMENT)
    fixed = orch.store.get_artifact(pid, "deploy-dockerfile")
    orch.update_artifact(pid, fixed.id, text=fixed.text.replace("COPY src/ ./src/", "COPY todo/ ./todo/"))
    with pytest.raises(InvalidTransitionError, match="changed since the last check"):
        orch.approve(pid, P.DEPLOYMENT)
    orch.run_action(pid, P.DEPLOYMENT, "check", {})
    orch.approve(pid, P.DEPLOYMENT)


# Real run (s03): the deployer of an interactive game wanted `printf '0 0\nq\n' | python -m tictactoe`.


def test_a_shell_pipe_in_the_smoke_command_is_refused_with_the_way_out():
    import pytest
    from pydantic import ValidationError

    from wings.phases.deployment.schema import DeployerOutput

    files = [{"path": "Dockerfile", "purpose": "p", "content": "FROM python:3.12-slim\nCMD [\"python\"]\n"}]
    with pytest.raises(ValidationError, match="smoke_input"):
        DeployerOutput(notes="n", smoke_command="printf 'q\n' | python -m game", files=files)
    ok = DeployerOutput(notes="n", smoke_command="python -m game", smoke_input="0 0\nq\n", files=files)
    assert ok.smoke_input == "0 0\nq\n"


def test_an_interactive_program_gets_its_smoke_input(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    script["deployer"][0]["smoke_command"] = "python -c \"import sys; assert sys.stdin.read().strip() == 'q'; print('ok')\""
    script["deployer"][0]["smoke_input"] = "q\n"
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    check = orch.store.get_artifact(pid, "deployment-check")
    assert check.content["passed"] and check.content["input"] == "q\n"
    orch.run_action(pid, P.DEPLOYMENT, "check", {})  # "Check again" feeds the same input
    assert orch.store.get_artifact(pid, "deployment-check").content["passed"]


# The run guide: "where can I start my project now?" answered as data, checked by code.


def test_prepare_saves_the_run_guide_as_data_next_to_deploy_md(make_orchestrator, demo_script, walk):
    from wings.domain.artifacts import ArtifactKind
    from wings.domain.sync import folder_path

    orch, pid = deployed_orch(make_orchestrator, demo_script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    guide = orch.store.get_artifact(pid, "run-guide")
    assert guide.kind is ArtifactKind.RUN_GUIDE and guide.author == "system:check"
    assert guide.content == {
        "start_command": "python -m todo",
        "url": None,
        "example_commands": ['python -m todo add "Buy milk"', "python -m todo list", "python -m todo done 1"],
        "stop_hint": "",
        "checked": True,
        "derived": False,
        "port_taken": None,
    }
    assert "```\npython -m todo\n```" in guide.text and "Checked by Wings" in guide.text
    assert folder_path(guide.path) == "RUN.md"
    assert folder_path(orch.store.get_artifact(pid, "deploy-deploy-md").path) == "DEPLOY.md"  # same place
    assert orch.store.get_artifact(pid, "deployment-check").content["start_command"] == "python -m todo"


def test_a_start_command_for_a_module_the_code_does_not_have_fails_the_check(make_orchestrator, demo_script, walk):
    import pytest

    from wings.domain.errors import InvalidTransitionError

    script = copy.deepcopy(demo_script)
    script["deployer"][0]["start_command"] = "python -m tasks"
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    result = orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    check = orch.store.get_artifact(pid, "deployment-check")
    assert not check.content["passed"] and check.content["exit_code"] == 0  # the smoke run itself was fine
    assert any("python -m tasks" in p and "no such module" in p for p in check.content["problems"])
    assert "python -m tasks" in result.outcome.reply and "Check passed" not in result.outcome.reply
    assert orch.store.get_artifact(pid, "run-guide").content["checked"] is False
    with pytest.raises(InvalidTransitionError, match="did not pass"):
        orch.approve(pid, P.DEPLOYMENT)


def test_a_deployer_answer_without_the_new_fields_still_gives_a_run_guide(make_orchestrator, demo_script, walk):
    """Old scripts and models that leave the fields out: the start command is derived from the smoke command."""
    script = copy.deepcopy(demo_script)
    for key in ("start_command", "url", "example_commands", "stop_hint"):
        script["deployer"][0].pop(key, None)
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    guide = orch.store.get_artifact(pid, "run-guide").content
    assert guide["start_command"] == "python -m todo list" and guide["derived"] and guide["checked"]
    assert guide["example_commands"] == [] and guide["url"] is None
    assert orch.store.get_artifact(pid, "deployment-check").content["passed"]


def test_no_start_command_is_derived_from_a_smoke_command_that_starts_no_program(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    script["deployer"][0].pop("start_command", None)
    script["deployer"][0]["smoke_command"] = 'python -c "import todo"'
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    guide = orch.store.get_artifact(pid, "run-guide")
    assert guide.content["start_command"] == "" and not guide.content["checked"] and "No start command is known" in guide.text
    assert orch.store.get_artifact(pid, "deployment-check").content["passed"]  # an unknown start command is not a failure


def test_check_again_keeps_the_run_guide_and_makes_one_for_a_project_from_before(make_orchestrator, demo_script, walk):
    orch, pid = deployed_orch(make_orchestrator, demo_script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    first = orch.store.get_artifact(pid, "run-guide")
    orch.run_action(pid, P.DEPLOYMENT, "check", {})
    again = orch.store.get_artifact(pid, "run-guide")
    assert again.content == first.content
    # A project deployed before the run guide existed: no such artifact, only the check with its smoke command.
    orch.store.save_artifact(pid, again.model_copy(update={"retired": True}))
    orch.run_action(pid, P.DEPLOYMENT, "check", {})
    derived = orch.store.get_artifact(pid, "run-guide")
    assert not derived.retired and derived.content["start_command"] == "python -m todo list" and derived.content["derived"] and derived.content["checked"]


def test_the_run_guide_is_computed_and_cannot_be_edited_or_written_by_the_deployer(make_orchestrator, demo_script, walk):
    import pytest
    from pydantic import ValidationError

    from wings.domain.errors import InvalidInputError
    from wings.phases.deployment.schema import DeployFile

    orch, pid = deployed_orch(make_orchestrator, demo_script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    with pytest.raises(InvalidInputError, match="computed"):
        orch.update_artifact(pid, "run-guide", text="# Run it\n\nrm -rf /\n")
    with pytest.raises(ValidationError, match="written by Wings"):
        DeployFile(path="RUN.md", purpose="p", content="x")  # would land on the same file as the run guide
    assert DeployFile(path="docs/RUN.md", purpose="p", content="x").path == "docs/RUN.md"


def test_the_run_guide_is_written_to_the_folder_and_a_hand_edit_of_it_is_not_imported(make_orchestrator, demo_script, walk):
    from wings.domain.folder import SyncedFile
    from wings.domain.sync import fingerprint, folder_changes, plan_export

    orch, pid = deployed_orch(make_orchestrator, demo_script, walk)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    artifacts = orch.store.list_artifacts(pid)
    plan = plan_export(artifacts, {}, {})
    assert "RUN.md" in plan.writes and "DEPLOY.md" in plan.writes and plan.writes["RUN.md"].startswith("# Run it")
    guide = orch.store.get_artifact(pid, "run-guide")
    manifest = {"RUN.md": SyncedFile(artifact_id=guide.id, revision=guide.revision, sha256=fingerprint(guide.text))}
    changes = folder_changes(artifacts, manifest, {"RUN.md": "# Run it\n\nedited by hand\n"})
    mine = next(c for c in changes if c.path == "RUN.md")
    assert not mine.importable and "Computed by Wings" in mine.note


def test_the_start_command_must_be_a_python_command_but_long_text_is_never_refused():
    import pytest
    from pydantic import ValidationError

    from wings.phases.deployment.schema import DeployerOutput

    files = [{"path": "Dockerfile", "purpose": "p", "content": "FROM python:3.12-slim\nCMD [\"python\"]\n"}]
    for bad in ("./run.sh", "docker run todo", "python -m todo | more", 'python -m todo "open'):
        with pytest.raises(ValidationError, match="start_command"):
            DeployerOutput(notes="n", smoke_command="python -m todo list", start_command=bad, files=files)
    ok = DeployerOutput(notes="word " * 500, smoke_command="python -m todo list", start_command=" python -m todo ", example_commands=["a"] * 9, files=files)
    assert ok.start_command == "python -m todo" and len(ok.example_commands) == 9  # trimmed later by code, not refused
    assert DeployerOutput(notes="n", smoke_command="python -m todo list", files=files).start_command == ""


# Short replies: the result and the one open point; details are in the artifacts.


def test_the_reply_is_short_and_names_the_result(make_orchestrator, demo_script, walk):
    orch, pid = deployed_orch(make_orchestrator, demo_script, walk)
    reply = orch.run_action(pid, P.DEPLOYMENT, "generate", {}).outcome.reply
    assert reply.startswith("4 deployment files. Check passed") and "\n" not in reply
    assert len(reply.split()) <= 45, reply
    again = orch.run_action(pid, P.DEPLOYMENT, "check", {}).outcome.reply
    assert again.startswith("Check passed") and len(again.split()) <= 20


def test_long_notes_of_the_deployer_are_cut_in_the_reply_and_kept_in_the_data(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    notes = "The image is small. " + "This sentence repeats what DEPLOY.md already says about volumes and scripts. " * 12
    script["deployer"][0]["notes"] = notes
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    result = orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    assert len(result.outcome.reply) < 500 and result.outcome.reply.rstrip().endswith(".")
    assert result.outcome.data["notes"] == notes.strip()


def test_many_problems_are_listed_compactly(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    docker = next(f for f in script["deployer"][0]["files"] if f["path"] == "Dockerfile")
    docker["content"] = "FROM python:3.12-slim\n" + "".join(f"COPY missing{i}/ ./m{i}/\n" for i in range(9)) + 'CMD ["python", "-m", "todo"]\n'
    orch, pid = deployed_orch(make_orchestrator, script, walk)
    reply = orch.run_action(pid, P.DEPLOYMENT, "generate", {}).outcome.reply
    assert reply.count("\n- ") == 6 and "and 4 more (deployment check)" in reply
    assert len(orch.store.get_artifact(pid, "deployment-check").content["problems"]) == 9  # all of them in the artifact


class BusyPortSandbox(LocalSandbox):
    """The local sandbox, on a computer where another program already listens on port 8000."""

    def port_in_use(self, port: int) -> bool:
        return port == 8000


def test_a_web_app_whose_port_is_taken_says_so_in_the_check_and_the_run_guide(make_orchestrator, demo_script, walk):
    # Seen on Windows (2026-11-25): the generated server started on a taken port and the browser showed an old game.
    script = copy.deepcopy(demo_script)
    script["deployer"][0]["url"] = "http://127.0.0.1:8000/"
    orch = make_orchestrator(script)
    orch.sandbox = BusyPortSandbox()
    pid = walk(orch, P.DEPLOYMENT)
    result = orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    guide = orch.store.get_artifact(pid, "run-guide")
    assert guide.content["port_taken"] == 8000 and "Port 8000 was in use" in guide.text
    check = orch.store.get_artifact(pid, "deployment-check")
    assert check.content["passed"]  # the deployment itself is fine; the port is a fact about this computer
    assert check.content["port_taken"] == 8000 and "Port 8000" in check.text
    assert "Port 8000 is in use by another program, so the program will use the next free port" in result.outcome.reply


def test_a_free_port_is_not_mentioned(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    script["deployer"][0]["url"] = "http://127.0.0.1:8001/"
    orch = make_orchestrator(script)
    orch.sandbox = BusyPortSandbox()
    pid = walk(orch, P.DEPLOYMENT)
    result = orch.run_action(pid, P.DEPLOYMENT, "generate", {})
    assert orch.store.get_artifact(pid, "run-guide").content["port_taken"] is None
    assert "in use" not in result.outcome.reply
