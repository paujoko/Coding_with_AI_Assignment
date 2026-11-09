"""The local sandbox runs generated code in a temporary folder with a time limit and a clean environment."""

import os

from wings.adapters.sandbox import LocalSandbox


def test_runs_python_in_a_temp_folder_and_collects_files():
    files = {"app/__init__.py": "", "app/main.py": "import os\nopen('out.txt', 'w').write('hi')\nprint('ran')\n"}
    result = LocalSandbox().run(files, ["{python}", "-m", "app.main"], timeout=30, collect=["out.txt"])
    assert result.exit_code == 0 and "ran" in result.output
    assert result.collected == {"out.txt": "hi"}


def test_secrets_are_not_passed_on(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    files = {"show.py": "import os\nprint(os.environ.get('OPENAI_API_KEY', 'none'))\n"}
    result = LocalSandbox().run(files, ["{python}", "show.py"], timeout=30)
    assert "sk-secret" not in result.output and "none" in result.output


def test_time_limit_stops_a_hanging_program():
    result = LocalSandbox().run({"loop.py": "while True: pass\n"}, ["{python}", "loop.py"], timeout=1)
    assert result.timed_out and result.exit_code != 0


def test_paths_outside_the_folder_are_refused(tmp_path):
    result = LocalSandbox().run({"../escape.py": "print(1)"}, ["{python}", "-c", "print(1)"], timeout=5)
    assert result.exit_code != 0 and "path" in result.output.lower()
    assert not os.path.exists(tmp_path.parent / "escape.py")


def test_pytest_runs_and_writes_junit():
    files = {"test_x.py": "def test_req_001_ok():\n    assert True\n"}
    result = LocalSandbox().run(files, ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=report.xml"], timeout=60, collect=["report.xml"])
    assert result.exit_code == 0 and "test_req_001_ok" in result.collected["report.xml"]
