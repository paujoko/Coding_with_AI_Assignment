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


# Review round 7 findings: stdin, grandchildren, odd paths.


def test_the_program_gets_no_standard_input():
    # Under wings-mcp the server talks JSON-RPC over stdio; a child must not read it.
    files = {"ask.py": "try:\n    input()\n    print('read')\nexcept EOFError:\n    print('no input')\n"}
    result = LocalSandbox().run(files, ["{python}", "ask.py"], timeout=10)
    assert "no input" in result.output


def test_the_time_limit_also_stops_programs_it_started(tmp_path):
    marker = tmp_path / "late.txt"
    child = f"import time, pathlib\ntime.sleep(3)\npathlib.Path({str(marker)!r}).write_text('still running')\n"
    parent = "import subprocess, sys\nsubprocess.Popen([sys.executable, 'child.py'])\nwhile True: pass\n"
    result = LocalSandbox().run({"parent.py": parent, "child.py": child}, ["{python}", "parent.py"], timeout=1)
    assert result.timed_out
    import time

    time.sleep(3.5)
    assert not marker.exists()


def test_odd_paths_are_refused_not_raised():
    assert LocalSandbox().run({".": "x"}, ["{python}", "-c", "print(1)"], timeout=5).exit_code == 2
    clash = LocalSandbox().run({"a": "x", "a/b.py": "print(1)"}, ["{python}", "-c", "print(1)"], timeout=5)
    assert clash.exit_code == 2 and "Could not write" in clash.output


def test_standard_input_can_be_given_for_interactive_programs():
    """Real run (s03): an interactive tic-tac-toe could not be smoke-tested without input."""
    files = {"ask.py": "print('got', input())\nprint('then', input())\n"}
    result = LocalSandbox().run(files, ["{python}", "ask.py"], timeout=10, stdin="0 0\nq\n")
    assert result.exit_code == 0 and "got 0 0" in result.output and "then q" in result.output
