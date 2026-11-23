from wings.domain.uml import basic_problems, check_consistency, parse_classes, sequence_messages

CLASSES = """@startuml
class Task {
  +title: str
}
class TaskService {
  +complete(number: int): Task
}
interface TaskRepository {
  +load(): Task[*]
}
class JsonTaskRepository {
  +path: str
}
JsonTaskRepository ..|> TaskRepository
@enduml"""

SEQUENCE = """@startuml
actor User
participant Cli
participant TaskService
participant JsonTaskRepository
User -> Cli : todo done 1
Cli -> TaskService : complete(1)
TaskService -> JsonTaskRepository : load()
JsonTaskRepository --> TaskService : tasks
TaskService -> JsonTaskRepository : archive(tasks)
@enduml"""


def test_classes_with_operations_and_inherited_ones():
    classes = parse_classes(CLASSES)
    assert set(classes) == {"Task", "TaskService", "TaskRepository", "JsonTaskRepository"}
    assert classes["TaskService"] == {"complete"}
    assert "load" in classes["JsonTaskRepository"]  # realised from the interface


def test_sequence_messages_skip_actors_and_replies():
    msgs = sequence_messages(SEQUENCE)
    assert ("Cli", "TaskService", "complete") in msgs
    assert all(m[0] != "User" for m in msgs)
    assert ("JsonTaskRepository", "TaskService", None) not in msgs  # dashed replies are not calls


def test_consistency_names_missing_classes_and_operations():
    problems = check_consistency(CLASSES, {"Complete a task": SEQUENCE})
    assert any("Cli" in p and "not a class" in p for p in problems)
    assert any("archive" in p and "JsonTaskRepository" in p for p in problems)
    assert not any("load" in p for p in problems)
    assert not any("complete" in p for p in problems)


def test_basic_problems():
    assert basic_problems("class A") == ["The diagram must start with @startuml.", "The diagram must end with @enduml."]
    assert basic_problems("@startuml\n@enduml") == ["The diagram is empty."]
    assert basic_problems("@startuml\nclass A\n@enduml") == []


# The class model: all class diagrams read together, with parents and attributes.


def test_class_model_reads_parents_from_arrows_and_keywords():
    from wings.domain.uml import class_model

    model = class_model(
        [
            "@startuml\nclass Animal {\n  +name: str\n  +speak(): str\n}\nclass Dog extends Animal\nAnimal <|-- Cat\n@enduml",
            "@startuml\ninterface Pet\nclass Puppy\nPuppy --|> Dog\nclass Kitten implements Pet, Animal\nPet <|.. Dog\n@enduml",
        ]
    )
    assert model.parents["Dog"] == {"Animal", "Pet"}
    assert model.parents["Cat"] == {"Animal"}
    assert model.parents["Kitten"] == {"Pet", "Animal"}
    assert model.ancestors("Puppy") == {"Dog", "Animal", "Pet"}  # across diagrams
    assert model.operations["Puppy"] == set()  # the maps hold what a class declares itself
    assert "speak" in model.all_operations("Puppy") and "name" in model.all_public_attributes("Puppy")


def test_class_model_attributes_only_in_the_unambiguous_form():
    from wings.domain.uml import class_model

    model = class_model(
        ["@startuml\nclass Task {\n  +title: str\n  -secret: str\n  due : date [0..1]\n  {static} +count: int\n  String legacy\n  --\n  +done(): bool\n}\n@enduml"]
    )
    assert model.attributes["Task"] == {"title", "secret", "due", "count"}  # `String legacy` is not read as an attribute
    assert model.public_attributes["Task"] == {"title", "count"}  # only the ones marked +
    assert model.operations["Task"] == {"done"}


def test_a_class_body_left_open_does_not_swallow_the_next_diagram():
    from wings.domain.uml import class_model

    model = class_model(["@startuml\nclass A {\n  +a(): int\n@enduml", "@startuml\nclass B {\n  +b(): int\n}\n@enduml"])
    assert model.operations == {"A": {"a"}, "B": {"b"}}


def test_parse_classes_inherits_through_the_extends_keyword():
    classes = parse_classes("@startuml\nclass Base {\n  +save(): None\n}\nclass Child extends Base {\n  +load(): None\n}\n@enduml")
    assert classes["Child"] == {"save", "load"}
