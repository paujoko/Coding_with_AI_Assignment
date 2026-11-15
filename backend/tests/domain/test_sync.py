from wings.domain.artifacts import Artifact, ArtifactKind
from wings.domain.folder import SyncedFile
from wings.domain.phases import PhaseId
from wings.domain.sync import fingerprint, folder_changes, folder_path, is_ignored, plan_export, program_path


def art(aid: str, path: str, text: str, kind=ArtifactKind.SOURCE_FILE, phase=PhaseId.CODEGEN, revision: int = 1, retired: bool = False) -> Artifact:
    return Artifact(id=aid, kind=kind, phase=phase, title=path, path=path, text=text, revision=revision, retired=retired)


def stamp(a: Artifact, text: str | None = None) -> SyncedFile:
    return SyncedFile(artifact_id=a.id, revision=a.revision, sha256=fingerprint(a.text if text is None else text))


SRC = art("source-todo-models-py", "app/todo/models.py", "class Task:\n    pass\n")
REQS = art("requirements", "requirements.md", "# Requirements\n", kind=ArtifactKind.REQUIREMENTS, phase=PhaseId.REQUIREMENTS)
REPORT = art("test-report", "reports/test-results.md", "all green\n", kind=ArtifactKind.TEST_REPORT, phase=PhaseId.TESTING)


def test_program_files_go_to_the_top_and_documents_under_docs_wings():
    assert folder_path("app/todo/models.py") == "todo/models.py"
    assert folder_path("app/Dockerfile") == "Dockerfile"
    assert folder_path("requirements.md") == "docs/wings/requirements.md"
    assert folder_path("design/use-cases.puml") == "docs/wings/design/use-cases.puml"
    assert program_path("todo/models.py") == "todo/models.py"
    assert program_path("docs/wings/requirements.md") is None


def test_line_endings_are_not_a_change():
    assert fingerprint("a\r\nb\r\n") == fingerprint("a\nb\n")
    assert fingerprint("a\nb") != fingerprint("a\nc")


def test_tool_folders_and_editor_files_are_ignored():
    assert is_ignored(".venv/lib/x.py")
    assert is_ignored("todo/__pycache__/models.cpython-312.pyc")
    assert is_ignored("Thumbs.db")
    assert not is_ignored("todo/models.py")


def test_first_export_writes_every_file():
    plan = plan_export([SRC, REQS], {}, {})
    assert plan.writes == {"todo/models.py": SRC.text, "docs/wings/requirements.md": REQS.text}
    assert plan.files["todo/models.py"] == stamp(SRC)
    assert not plan.kept and not plan.deletes


def test_a_newer_revision_replaces_an_untouched_file():
    newer = SRC.model_copy(update={"text": "class Task:\n    done = False\n", "revision": 2})
    plan = plan_export([newer], {"todo/models.py": stamp(SRC)}, {"todo/models.py": SRC.text})
    assert plan.writes == {"todo/models.py": newer.text}
    assert plan.files["todo/models.py"].revision == 2


def test_a_hand_edit_is_never_overwritten():
    newer = SRC.model_copy(update={"text": "class Task:\n    done = False\n", "revision": 2})
    edited = "class Task:\n    def archive(self): ...\n"
    plan = plan_export([newer], {"todo/models.py": stamp(SRC)}, {"todo/models.py": edited})
    assert plan.writes == {}
    assert plan.kept == ["todo/models.py"]
    assert plan.files["todo/models.py"] == stamp(SRC)  # the base stays, so the edit is still seen as one


def test_a_file_deleted_by_hand_is_not_restored():
    plan = plan_export([SRC], {"todo/models.py": stamp(SRC)}, {})
    assert plan.writes == {} and plan.kept == ["todo/models.py"]


def test_a_file_that_was_there_before_wings_is_left_alone():
    plan = plan_export([SRC], {}, {"todo/models.py": "mine"})
    assert plan.writes == {} and plan.kept == ["todo/models.py"]
    assert "todo/models.py" not in plan.files


def test_a_retired_artifact_removes_its_untouched_file_but_not_an_edited_one():
    gone = SRC.model_copy(update={"retired": True, "revision": 2})
    assert plan_export([gone], {"todo/models.py": stamp(SRC)}, {"todo/models.py": SRC.text}).deletes == ["todo/models.py"]
    kept = plan_export([gone], {"todo/models.py": stamp(SRC)}, {"todo/models.py": "edited"})
    assert kept.deletes == [] and kept.kept == ["todo/models.py"] and kept.files == {}


def test_an_unchanged_folder_has_no_changes():
    manifest = {"todo/models.py": stamp(SRC), "docs/wings/requirements.md": stamp(REQS)}
    disk = {"todo/models.py": SRC.text.replace("\n", "\r\n"), "docs/wings/requirements.md": REQS.text, "tasks.json": "[]", ".venv/x.py": ""}
    assert folder_changes([SRC, REQS], manifest, disk) == []


def test_a_hand_edit_of_code_is_importable():
    [change] = folder_changes([SRC], {"todo/models.py": stamp(SRC)}, {"todo/models.py": "class Task:\n    def archive(self): ...\n"})
    assert (change.change, change.artifact_id, change.phase, change.importable, change.newer_in_wings) == ("modified", SRC.id, PhaseId.CODEGEN, True, False)


def test_an_edit_made_while_wings_wrote_a_newer_revision_is_flagged():
    newer = SRC.model_copy(update={"text": "class Task:\n    done = False\n", "revision": 2})
    [change] = folder_changes([newer], {"todo/models.py": stamp(SRC)}, {"todo/models.py": "edited"})
    assert change.newer_in_wings


def test_a_file_waiting_for_the_next_export_is_not_a_change():
    newer = SRC.model_copy(update={"text": "class Task:\n    done = False\n", "revision": 2})
    assert folder_changes([newer], {"todo/models.py": stamp(SRC)}, {"todo/models.py": SRC.text}) == []


def test_computed_files_and_requirements_are_not_importable():
    manifest = {"docs/wings/requirements.md": stamp(REQS), "docs/wings/reports/test-results.md": stamp(REPORT)}
    disk = {"docs/wings/requirements.md": "# changed", "docs/wings/reports/test-results.md": "changed"}
    changes = {c.path: c for c in folder_changes([REQS, REPORT], manifest, disk)}
    assert not changes["docs/wings/requirements.md"].importable
    assert "Requirements" in changes["docs/wings/requirements.md"].note
    assert not changes["docs/wings/reports/test-results.md"].importable


def test_deleting_code_is_importable_but_deleting_a_diagram_is_not():
    diagram = art("diagram-classes", "design/classes.puml", "@startuml\n@enduml\n", kind=ArtifactKind.DIAGRAM, phase=PhaseId.DESIGN)
    manifest = {"todo/models.py": stamp(SRC), "docs/wings/design/classes.puml": stamp(diagram)}
    changes = {c.path: c for c in folder_changes([SRC, diagram], manifest, {})}
    assert changes["todo/models.py"].change == "deleted" and changes["todo/models.py"].importable
    assert changes["docs/wings/design/classes.puml"].change == "deleted" and not changes["docs/wings/design/classes.puml"].importable


def test_new_code_files_are_offered_but_data_files_are_not():
    disk = {"todo/models.py": SRC.text, "todo/export.py": "x = 1\n", "static/app.js": "", "tasks.json": "[]", "todo.db": "", "docs/wings/notes.py": ""}
    added = [c.path for c in folder_changes([SRC], {"todo/models.py": stamp(SRC)}, disk) if c.change == "added"]
    assert added == ["static/app.js", "todo/export.py"]
