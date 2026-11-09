"""Deterministic checks on PlantUML sources: the code that verifies what an agent proposes.

Deliberately small parsers for the subset the agents write (classes with operations,
realisation and inheritance arrows, sequence participants and messages). They do not
validate PlantUML syntax in general; the renderer port does that.
"""

import re

_DECL = re.compile(
    r'^\s*(?:abstract\s+class|abstract|class|interface|enum|entity|annotation)\s+"?([A-Za-z_]\w*)"?(?:\s+as\s+(\w+))?[^{]*?(\{)?\s*$'
)
_OPERATION = re.compile(r"([A-Za-z_]\w*)\s*\(")
_CHILD_FIRST = re.compile(r"^\s*([A-Za-z_]\w*)\s*[.\-]+\|>\s*([A-Za-z_]\w*)")  # Child ..|> Parent, Child --|> Parent
_PARENT_FIRST = re.compile(r"^\s*([A-Za-z_]\w*)\s*<\|[.\-]+\s*([A-Za-z_]\w*)")  # Parent <|-- Child
_PARTICIPANT = re.compile(
    r'^\s*(actor|participant|boundary|control|entity|database|collections|queue)\s+"?([A-Za-z_]\w*)"?(?:\s+as\s+(\w+))?'
)
_MESSAGE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(-{1,2})(>>|>|\\\\|//|x)\s*([A-Za-z_]\w*)\s*(?::\s*(.*))?$")


def _lines(source: str) -> list[str]:
    return [line for line in source.splitlines() if not line.strip().startswith("'")]


def basic_problems(source: str) -> list[str]:
    """Problems any reader can see without a PlantUML installation."""
    lines = [line.strip() for line in source.strip().splitlines()]
    problems = []
    if not lines or not lines[0].lower().startswith("@startuml"):
        problems.append("The diagram must start with @startuml.")
    if not lines or not lines[-1].lower().startswith("@enduml"):
        problems.append("The diagram must end with @enduml.")
    if not problems and not any(line and not line.startswith("'") for line in lines[1:-1]):
        problems.append("The diagram is empty.")
    return problems


def parse_classes(source: str) -> dict[str, set[str]]:
    """Class (and interface, enum) names with their operations, including inherited ones."""
    classes: dict[str, set[str]] = {}
    parents: dict[str, set[str]] = {}
    current: str | None = None
    for line in _lines(source):
        if current is not None:
            if line.strip().startswith("}"):
                current = None
            else:
                classes[current] |= {m for m in _OPERATION.findall(line)}
            continue
        decl = _DECL.match(line)
        if decl:
            name = decl.group(2) or decl.group(1)
            classes.setdefault(name, set())
            if decl.group(3):
                current = name
            continue
        for pattern, child_first in ((_CHILD_FIRST, True), (_PARENT_FIRST, False)):
            m = pattern.match(line)
            if m:
                child, parent = (m.group(1), m.group(2)) if child_first else (m.group(2), m.group(1))
                parents.setdefault(child, set()).add(parent)
    for _ in range(len(classes)):  # inherit transitively; the loop bound covers any depth
        for child, ps in parents.items():
            if child in classes:
                for parent in ps:
                    classes[child] |= classes.get(parent, set())
    return classes


def sequence_participants(source: str) -> dict[str, str]:
    """Participant name -> declared kind ('participant' for names that are only used in messages)."""
    found: dict[str, str] = {}
    for line in _lines(source):
        decl = _PARTICIPANT.match(line)
        if decl:
            found[decl.group(3) or decl.group(2)] = decl.group(1)
            continue
        msg = _MESSAGE.match(line)
        if msg:
            for name in (msg.group(1), msg.group(4)):
                found.setdefault(name, "participant")
    return found


def sequence_messages(source: str) -> list[tuple[str, str, str | None]]:
    """Calls in a sequence diagram as (caller, callee, operation or None). Dashed replies and actors' messages are left out."""
    kinds = sequence_participants(source)
    calls = []
    for line in _lines(source):
        msg = _MESSAGE.match(line)
        if not msg or msg.group(2) == "--" or kinds.get(msg.group(1)) == "actor":
            continue
        op = _OPERATION.match((msg.group(5) or "").strip())
        calls.append((msg.group(1), msg.group(4), op.group(1) if op else None))
    return calls


def check_consistency(class_diagram: str, sequence_diagrams: dict[str, str]) -> list[str]:
    """What the sequence diagrams use that the class diagram does not define."""
    classes = parse_classes(class_diagram)
    problems: list[str] = []
    for title, source in sequence_diagrams.items():
        for name, kind in sequence_participants(source).items():
            if kind != "actor" and name not in classes:
                problems.append(f"'{name}' appears in '{title}' but is not a class in the class diagram.")
        for _caller, callee, op in sequence_messages(source):
            if op and callee in classes and op not in classes[callee]:
                problems.append(f"'{title}' calls {op}() on {callee}, which the class diagram does not define.")
    return list(dict.fromkeys(problems))
