"""Deterministic checks on PlantUML sources: the code that verifies what an agent proposes.

Deliberately small parsers for the subset the agents write (classes with operations,
realisation and inheritance arrows, sequence participants and messages). They do not
validate PlantUML syntax in general; the renderer port does that.
"""

import re
from collections.abc import Iterable, Mapping

from pydantic import BaseModel, Field

_DECL = re.compile(
    r'^\s*(?:abstract\s+class|abstract|class|interface|enum|entity|annotation)\s+"?([A-Za-z_]\w*)"?(?:\s+as\s+(\w+))?[^{]*?(\{)?\s*$'
)
_OPERATION = re.compile(r"([A-Za-z_]\w*)\s*\(")
_MODIFIER = r"(?:\{(?:static|classifier|abstract|field)\}\s*)*"
_ATTRIBUTE = re.compile(rf"^\s*{_MODIFIER}([+\-#~])?\s*{_MODIFIER}([A-Za-z_]\w*)\s*:\s*\S")  # +name: type
_HIDDEN = re.compile(rf"^\s*{_MODIFIER}[\-#]")  # -private or #protected: the `_name` of Python
_EXTENDS = re.compile(r"\b(?:extends|implements)\s+([A-Za-z_][\w\s,]*)")  # class B extends A implements I, J
_CHILD_FIRST = re.compile(r"^\s*([A-Za-z_]\w*)\s*[.\-]+\|>\s*([A-Za-z_]\w*)")  # Child ..|> Parent, Child --|> Parent
_PARENT_FIRST = re.compile(r"^\s*([A-Za-z_]\w*)\s*<\|[.\-]+\s*([A-Za-z_]\w*)")  # Parent <|-- Child
# `participant Game`, `participant Game as G`, `participant "Game" as G`, `actor "Browser page" as PAGE`.
_PARTICIPANT = re.compile(
    r'^\s*(actor|participant|boundary|control|entity|database|collections|queue)\s+(?:"([^"]+)"|([A-Za-z_]\w*))(?:\s+as\s+(\w+))?'
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


class ClassModel(BaseModel):
    """What one or more class diagrams say, read together. The maps hold what each class declares
    itself; the `all_` methods add what it inherits."""

    operations: dict[str, set[str]] = Field(default_factory=dict)  # class -> operation names
    attributes: dict[str, set[str]] = Field(default_factory=dict)  # class -> attributes written as `name: type`, any visibility
    public_attributes: dict[str, set[str]] = Field(default_factory=dict)  # the ones marked `+`
    parents: dict[str, set[str]] = Field(default_factory=dict)  # class -> direct parents (inheritance and realisation)
    hidden_operations: dict[str, set[str]] = Field(default_factory=dict)  # class -> operations marked - or #

    def ancestors(self, name: str) -> set[str]:
        return ancestors(name, self.parents)

    def all_operations(self, name: str) -> set[str]:
        return self._with_inherited(self.operations, name)

    def all_attributes(self, name: str) -> set[str]:
        return self._with_inherited(self.attributes, name)

    def all_public_attributes(self, name: str) -> set[str]:
        return self._with_inherited(self.public_attributes, name)

    def _with_inherited(self, members: dict[str, set[str]], name: str) -> set[str]:
        return set(members.get(name, set())).union(*(members.get(p, set()) for p in self.ancestors(name)))


def ancestors(name: str, parents: Mapping[str, Iterable[str]]) -> set[str]:
    """Every direct and indirect parent of a class, whatever the depth; cycles end."""
    found: set[str] = set()
    todo = list(parents.get(name, ()))
    while todo:
        parent = todo.pop()
        if parent not in found and parent != name:
            found.add(parent)
            todo += parents.get(parent, ())
    return found


def class_model(sources: Iterable[str]) -> ClassModel:
    """Classes (and interfaces, enums) of all given class diagrams together: a class may be declared in
    one diagram and extended in another. Parents come from the arrows (`A <|-- B`, `B --|> A`,
    `B ..|> A`) and from `class B extends A` / `implements A`."""
    model = ClassModel()
    for source in sources:
        current: str | None = None  # a class body never runs on into the next diagram
        for line in _lines(source):
            if current is not None:
                if line.strip().startswith("}"):
                    current = None
                elif "(" in line:
                    names = set(_OPERATION.findall(line))
                    model.operations[current] |= names
                    if _HIDDEN.match(line):
                        model.hidden_operations.setdefault(current, set()).update(names)
                else:
                    attribute = _ATTRIBUTE.match(line)
                    if attribute:
                        model.attributes[current].add(attribute.group(2))
                        if attribute.group(1) == "+":
                            model.public_attributes[current].add(attribute.group(2))
                continue
            decl = _DECL.match(line)
            if decl:
                name = decl.group(2) or decl.group(1)
                for members in (model.operations, model.attributes, model.public_attributes):
                    members.setdefault(name, set())
                for group in _EXTENDS.findall(line.split("{")[0]):
                    for word in group.replace(",", " ").split():
                        if word not in ("extends", "implements"):
                            model.parents.setdefault(name, set()).add(word)
                if decl.group(3):
                    current = name
                continue
            for pattern, child_first in ((_CHILD_FIRST, True), (_PARENT_FIRST, False)):
                m = pattern.match(line)
                if m:
                    child, parent = (m.group(1), m.group(2)) if child_first else (m.group(2), m.group(1))
                    model.parents.setdefault(child, set()).add(parent)
    return model


def parse_classes(source: str) -> dict[str, set[str]]:
    """Class (and interface, enum) names with their operations, including inherited ones."""
    model = class_model([source])
    return {name: model.all_operations(name) for name in model.operations}


def _participants(source: str) -> dict[str, tuple[str, str]]:
    """How messages refer to a participant (its alias, else its name) -> (name, declared kind).
    Names only used in messages count as 'participant'."""
    found: dict[str, tuple[str, str]] = {}
    for line in _lines(source):
        decl = _PARTICIPANT.match(line)
        if decl:
            name = decl.group(2) or decl.group(3)
            found[decl.group(4) or name] = (name, decl.group(1))
            continue
        msg = _MESSAGE.match(line)
        if msg:
            for ref in (msg.group(1), msg.group(4)):
                found.setdefault(ref, (ref, "participant"))
    return found


def sequence_participants(source: str) -> dict[str, str]:
    """Participant name -> declared kind. Aliases (`participant Game as G`) are resolved to the name."""
    return {name: kind for name, kind in _participants(source).values()}


def sequence_messages(source: str) -> list[tuple[str, str, str | None]]:
    """Calls in a sequence diagram as (caller, callee, operation or None), with aliases resolved to
    participant names. Dashed replies and actors' messages are left out."""
    known = _participants(source)
    calls = []
    for line in _lines(source):
        msg = _MESSAGE.match(line)
        if not msg or msg.group(2) == "--":
            continue
        (caller, kind), (callee, _) = known[msg.group(1)], known[msg.group(4)]
        if kind == "actor":
            continue
        op = _OPERATION.match((msg.group(5) or "").strip())
        calls.append((caller, callee, op.group(1) if op else None))
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
