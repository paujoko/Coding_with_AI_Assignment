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
