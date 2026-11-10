from wings.domain.code import compare_design_and_code, python_classes

DIAGRAM = """@startuml
class Task {
  +title: str
}
class TaskService {
  +add(title: str): Task
  +complete(number: int): Task
}
interface TaskRepository {
  +load(): Task[*]
}
class JsonTaskRepository
JsonTaskRepository ..|> TaskRepository
@enduml"""

FILES = {
    "todo/models.py": "class Task:\n    def __init__(self, title):\n        self.title = title\n",
    "todo/service.py": "class TaskService:\n    def add(self, title):\n        pass\n\n    def archive(self):\n        pass\n\n    def _helper(self):\n        pass\n",
    "todo/repo.py": "class TaskRepository:\n    def load(self):\n        return []\n\nclass JsonTaskRepository(TaskRepository):\n    pass\n\nclass Cache:\n    pass\n",
}


def test_python_classes_with_public_methods_and_inheritance():
    classes = python_classes(FILES)
    assert classes["TaskService"] == {"add", "archive"}  # private helpers and __init__ are not part of the design
    assert "load" in classes["JsonTaskRepository"]


def test_drift_in_both_directions():
    drift = compare_design_and_code(DIAGRAM, FILES)
    assert drift.missing_in_code == []
    assert drift.missing_in_diagram == ["Cache"]
    assert drift.operations_missing_in_code == ["TaskService.complete"]
    assert drift.operations_missing_in_diagram == ["TaskService.archive"]
    assert not drift.in_sync


def test_files_that_do_not_parse_are_reported_not_fatal():
    drift = compare_design_and_code(DIAGRAM, {"bad.py": "class (:"})
    assert drift.unparsable == ["bad.py"]


def test_private_names_are_implementation_details_on_both_sides():
    """Real run (s03): 10 of 11 drift lines were private helpers (`-_serve_static()` in the diagram,
    a `_BoundHandler` class in the code). They hid the one real difference."""
    diagram = """@startuml
class Handler {
  +do_GET() : None
  -_serve_static(path : str) : None
}
@enduml"""
    code = {
        "app/handler.py": (
            "class Handler:\n"
            "    def do_GET(self):\n        pass\n"
            "    def _serve(self, path):\n        pass\n"
            "    def log_message(self, *args):\n        pass\n"
            "class _BoundHandler(Handler):\n    pass\n"
        )
    }
    report = compare_design_and_code(diagram, code)
    assert report.lines() == ["Handler.log_message() is in the code but not in the class diagram."]
