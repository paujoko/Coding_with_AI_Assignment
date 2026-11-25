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


def test_an_operation_marked_private_in_the_diagram_is_not_drift():
    """Seen building Snake (2026-11-25): `-send_json()` in the diagram, `_send_json()` in the code,
    was reported as "send_json() is in the class diagram but not in the code"."""
    diagram = "@startuml\nclass Handler {\n  +do_GET() : None\n  -send_json(payload : dict) : None\n  # check(x : int) : bool\n  {static} -build() : Handler\n}\n@enduml"
    code = {"app/handler.py": "class Handler:\n    def do_GET(self):\n        pass\n    def _send_json(self, payload):\n        pass\n"}
    assert compare_design_and_code(diagram, code).lines() == []


# Inheritance and realisation, both directions.

SHAPES = """@startuml
interface Shape {
  +area(): float
}
class Circle
class Square
class Label
Shape <|.. Circle
Square --|> Shape
@enduml"""


def test_inheritance_in_the_diagram_but_not_in_the_code():
    code = {"shapes.py": "class Shape:\n    def area(self): ...\n\nclass Circle(Shape):\n    pass\n\nclass Square:\n    def area(self): ...\n\nclass Label:\n    pass\n"}
    report = compare_design_and_code(SHAPES, code)
    assert report.inheritance_missing_in_code == ["Square(Shape)"]
    assert report.lines() == ["Square inherits from Shape in the class diagram but not in the code."]
    assert not report.in_sync


def test_inheritance_in_the_code_but_not_in_the_diagram():
    code = {"shapes.py": "class Shape:\n    def area(self): ...\n\nclass Circle(Shape):\n    pass\n\nclass Square(Shape):\n    pass\n\nclass Label(Shape):\n    pass\n"}
    report = compare_design_and_code(SHAPES, code)
    assert report.inheritance_missing_in_diagram == ["Label(Shape)"]
    # Label inherits area() in the code; that follows from the one real difference and is not listed again.
    assert report.lines() == ["Label inherits from Shape in the code but not in the class diagram."]


def test_inheritance_is_followed_through_intermediate_and_private_classes():
    """A direct arrow in the diagram is met by an indirect base in the code and the other way round;
    bases the diagram does not know (ABC, a private mixin) are details."""
    diagram = "@startuml\nclass A\nclass B\nclass C\nclass E\nB --|> A\nC --|> B\nE --|> A\n@enduml"
    code = {
        "m.py": (
            "from abc import ABC\n"
            "class A(ABC):\n    pass\n"
            "class B(A):\n    pass\n"
            "class C(B, A):\n    pass\n"  # C(A) is in the diagram through B
            "class _Mixin(A):\n    pass\n"
            "class E(_Mixin):\n    pass\n"  # E reaches A through a private class
        )
    }
    report = compare_design_and_code(diagram, code)
    assert report.lines() == []


def test_a_protocol_is_realised_without_naming_it_as_a_base():
    """Python's structural typing: a class with all methods of a Protocol realises it."""
    diagram = "@startuml\ninterface Store {\n  +load(): list\n  +save(items: list): None\n}\nclass FileStore\nclass HalfStore\nFileStore ..|> Store\nHalfStore ..|> Store\n@enduml"
    code = {
        "s.py": (
            "from typing import Protocol\n"
            "class Store(Protocol):\n    def load(self) -> list: ...\n    def save(self, items: list) -> None: ...\n"
            "class FileStore:\n    def load(self): return []\n    def save(self, items): pass\n"
            "class HalfStore:\n    def load(self): return []\n"
        )
    }
    report = compare_design_and_code(diagram, code)
    assert report.inheritance_missing_in_code == ["HalfStore(Store)"]
    assert "FileStore" not in " ".join(report.lines())


def test_inheritance_of_a_class_that_is_missing_anyway_is_not_reported_twice():
    report = compare_design_and_code(SHAPES, {"shapes.py": "class Shape:\n    def area(self): ...\n\nclass Circle(Shape):\n    pass\n\nclass Label:\n    pass\n"})
    assert report.lines() == ["Square is in the class diagram but not in the code."]


# All class diagrams of the design together.


def test_several_class_diagrams_are_read_together():
    domain = "@startuml\nclass Task {\n  +title: str\n}\ninterface Repo {\n  +load(): list\n}\n@enduml"
    storage = "@startuml\nclass JsonRepo {\n  +path: str\n}\nJsonRepo ..|> Repo\n@enduml"
    code = {
        "a.py": "from dataclasses import dataclass\n@dataclass\nclass Task:\n    title: str\n",
        "b.py": "class Repo:\n    def load(self): ...\n\nclass JsonRepo(Repo):\n    def __init__(self, path):\n        self.path = path\n    def load(self): return []\n",
    }
    assert compare_design_and_code([domain, storage], code).lines() == []
    # With the first diagram alone, the class of the second one looked like drift.
    assert compare_design_and_code(domain, code).lines() == ["JsonRepo is in the code but not in the class diagram."]


# Attributes: only where both sides are unambiguous.

TASK = "@startuml\nclass Task {\n  +number: int\n  +title: str\n  -secret: str\n  note: str\n}\n@enduml"


def test_public_attribute_of_the_diagram_missing_in_the_code():
    code = {"t.py": "class Task:\n    def __init__(self, number):\n        self.number = number\n        self._title = ''\n"}
    report = compare_design_and_code(TASK, code)
    # -secret is private; `note` has no visibility mark, so it is not claimed to be public.
    assert report.attributes_missing_in_code == ["Task.title"]
    assert report.lines() == ["Task.title is in the class diagram but not in the code."]
    assert not report.in_sync


def test_an_attribute_is_met_by_a_field_an_assignment_a_property_or_an_inherited_one():
    diagram = "@startuml\nclass Base {\n  +id: int\n}\nclass Task {\n  +number: int\n  +title: str\n  +done: bool\n  +label: str\n}\nTask --|> Base\n@enduml"
    code = {
        "t.py": (
            "class Base:\n    id: int = 0\n"
            "class Task(Base):\n"
            "    number: int\n"
            "    def __init__(self):\n        self.title = ''\n"
            "    def finish(self):\n        self.done = True\n"  # set outside __init__: still there
            "    @property\n    def label(self):\n        return self.title\n"
        )
    }
    report = compare_design_and_code(diagram, code)
    assert report.attributes_missing_in_code == []
    # The property is the attribute `label`, not an operation the diagram lacks.
    assert report.operations_missing_in_diagram == ["Task.finish"]


def test_attributes_are_not_judged_when_the_code_class_has_a_base_wings_cannot_read():
    diagram = "@startuml\nclass Failure {\n  +message: str\n}\nclass Row {\n  +name: str\n}\n@enduml"
    code = {"e.py": "class Failure(Exception):\n    pass\n\nclass Row(SomeBase):\n    pass\n"}
    assert compare_design_and_code(diagram, code).lines() == []


def test_declared_field_in_the_code_missing_in_the_diagram():
    code = {
        "t.py": (
            "from dataclasses import dataclass\nfrom typing import ClassVar\n"
            "@dataclass\nclass Task:\n"
            "    number: int\n    title: str\n    secret: str\n    note: str\n"
            "    priority: int = 0\n"
            "    _cache: int = 0\n"
            "    LIMIT: ClassVar[int] = 10\n"
        )
    }
    report = compare_design_and_code(TASK, code)
    assert report.attributes_missing_in_diagram == ["Task.priority"]
    assert report.lines() == ["Task.priority is in the code but not in the class diagram."]


def test_fields_that_implement_an_association_or_are_plain_assignments_are_not_extra_attributes():
    """No false alarm: a field typed with a class of the diagram is the association line, and `self.x = ...`
    without a declaration is often an injected collaborator. A diagram class without attributes shows none on purpose."""
    diagram = "@startuml\nclass Task {\n  +title: str\n}\nclass Board {\n  +name: str\n}\nclass Service {\n  +run(): None\n}\nBoard \"1\" o-- \"*\" Task : tasks\n@enduml"
    code = {
        "b.py": (
            "from dataclasses import dataclass, field\n"
            "@dataclass\nclass Task:\n    title: str\n"
            "@dataclass\nclass Board:\n    name: str\n    tasks: list[Task] = field(default_factory=list)\n    first: 'Task | None' = None\n"
            "class Service:\n    retries: int = 3\n    def __init__(self, board):\n        self.board = board\n    def run(self): ...\n"
        )
    }
    assert compare_design_and_code(diagram, code).lines() == []


# No false alarms on the demo project the mock script produces.


def _demo(demo_script: dict) -> tuple[list[str], list[str], dict[str, str]]:
    first = [d["plantuml"] for d in demo_script["architect"][0]["diagrams"] if d["kind"] == "class"]
    refined = [d["plantuml"] for d in demo_script["refiner"][0]["diagrams"] if d["kind"] == "class"]
    code = {f["path"]: f["content"] for f in demo_script["coder"][0]["files"]}
    return first, refined, code


def test_the_demo_code_matches_the_refined_demo_design_with_all_rules(demo_script):
    _first, refined, code = _demo(demo_script)
    report = compare_design_and_code(refined, code)
    assert report.lines() == [] and report.in_sync


def test_the_demo_code_differs_from_the_first_design_in_one_operation_only(demo_script):
    first, _refined, code = _demo(demo_script)
    assert compare_design_and_code(first, code).lines() == ["TaskRepository.next_number() is in the code but not in the class diagram."]


def test_every_scripted_scenario_of_the_demo_is_in_sync_with_its_refined_design(demo_script):
    """Also the change scenario (a priority attribute on Task): no false alarm from the attribute rules."""
    checked = 0
    for key, replies in demo_script.items():
        if key.split("?")[0] != "coder":
            continue
        # a scenario that changes only the code (the web view, ADR 0020) is checked against the main refined design
        refined = demo_script.get("refiner" + key[len("coder") :], demo_script["refiner"])[0]
        diagrams = [d["plantuml"] for d in refined["diagrams"] if d["kind"] == "class"]
        code = {f["path"]: f["content"] for f in replies[0]["files"]}
        assert compare_design_and_code(diagrams, code).lines() == [], key
        checked += 1
    assert checked >= 1


def test_the_demo_test_file_adds_one_class_and_no_inheritance_or_attribute_noise(demo_script):
    """The demo tests define MemoryRepository(TaskRepository) with a declared-looking `self.tasks`."""
    _first, refined, code = _demo(demo_script)
    tests = {f["path"]: f["content"] for f in demo_script["tester"][0]["files"]}
    assert compare_design_and_code(refined, code | tests).lines() == ["MemoryRepository is in the code but not in the class diagram."]
