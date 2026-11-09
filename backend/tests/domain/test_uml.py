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
