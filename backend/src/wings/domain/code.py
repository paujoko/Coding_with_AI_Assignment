"""Design versus code, computed by code: what the class diagrams of the design say and what the
Python sources do, in both directions (drift).

Compared: classes, public operations, inheritance and realisation, and attributes where both sides
are unambiguous. Uses the standard `ast` module only. Private names (leading underscore) and dunder
methods are implementation details on both sides.

Rules that keep the report free of noise (lessons.md, "Noise hides signal"):
- One difference gives one line. A class that is missing is not also listed with its operations; a
  missing inheritance line is not also listed as the operations and attributes that came with it.
- Inheritance is met by an indirect base too (through a class in between, also a private one), and a
  `typing.Protocol` is realised by any class that has all its methods.
- Attributes of the diagram count only when written `+name: type`. They are met by a declared field,
  an assignment `self.name = ...` anywhere in the class, a property, or the same in a base class. A
  class with a base Wings cannot read (anything outside the files except ABC, Protocol, Generic,
  object) is not judged.
- Fields of the code count as missing in the diagram only when they are declared in the class body
  (`name: type`, as in a dataclass), the diagram shows attributes for that class at all, and the type
  does not name a class of the diagram (such a field is the association line, not an attribute).
"""

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from wings.domain.uml import ancestors, class_model

_READABLE_BASES = frozenset({"object", "ABC", "Protocol", "Generic"})  # bases that add no attributes
_OPAQUE = frozenset({"__getattr__", "__getattribute__", "__slots__"})  # attributes cannot be read from the source
_WORD = re.compile(r"[A-Za-z_]\w*")


class DriftReport(BaseModel):
    missing_in_code: list[str] = Field(default_factory=list)  # classes in the diagram, not in the code
    missing_in_diagram: list[str] = Field(default_factory=list)  # classes in the code, not in the diagram
    operations_missing_in_code: list[str] = Field(default_factory=list)  # "Class.op"
    operations_missing_in_diagram: list[str] = Field(default_factory=list)
    inheritance_missing_in_code: list[str] = Field(default_factory=list)  # "Child(Parent)"
    inheritance_missing_in_diagram: list[str] = Field(default_factory=list)
    attributes_missing_in_code: list[str] = Field(default_factory=list)  # "Class.attribute"
    attributes_missing_in_diagram: list[str] = Field(default_factory=list)
    unparsable: list[str] = Field(default_factory=list)  # files that are not valid Python

    @property
    def in_sync(self) -> bool:
        return not (
            self.missing_in_code
            or self.missing_in_diagram
            or self.operations_missing_in_code
            or self.operations_missing_in_diagram
            or self.inheritance_missing_in_code
            or self.inheritance_missing_in_diagram
            or self.attributes_missing_in_code
            or self.attributes_missing_in_diagram
        )

    def lines(self) -> list[str]:
        out = [f"{c} is in the class diagram but not in the code." for c in self.missing_in_code]
        out += [f"{c} is in the code but not in the class diagram." for c in self.missing_in_diagram]
        out += [f"{_inherits(i)} in the class diagram but not in the code." for i in self.inheritance_missing_in_code]
        out += [f"{_inherits(i)} in the code but not in the class diagram." for i in self.inheritance_missing_in_diagram]
        out += [f"{o}() is in the class diagram but not in the code." for o in self.operations_missing_in_code]
        out += [f"{o}() is in the code but not in the class diagram." for o in self.operations_missing_in_diagram]
        out += [f"{a} is in the class diagram but not in the code." for a in self.attributes_missing_in_code]
        out += [f"{a} is in the code but not in the class diagram." for a in self.attributes_missing_in_diagram]
        out += [f"{f} is not valid Python." for f in self.unparsable]
        return out


def _inherits(pair: str) -> str:
    child, _, parent = pair.rstrip(")").partition("(")
    return f"{child} inherits from {parent}"


@dataclass
class _CodeClass:
    """What the source says about one class, its own body only."""

    methods: set[str] = field(default_factory=set)  # public methods, properties included
    properties: set[str] = field(default_factory=set)
    fields: dict[str, set[str]] = field(default_factory=dict)  # declared in the class body: name -> names in its type
    known: set[str] = field(default_factory=set)  # every public attribute name the class is seen to have
    bases: list[str] = field(default_factory=list)
    opaque: bool = False


def _is_property(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in func.decorator_list:
        name = decorator.id if isinstance(decorator, ast.Name) else decorator.attr if isinstance(decorator, ast.Attribute) else ""
        if name in ("property", "cached_property"):
            return True
    return False


def _type_names(annotation: ast.expr) -> set[str]:
    """Every name a type annotation mentions, also inside a quoted annotation."""
    names: set[str] = set()
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(_WORD.findall(node.value))
    return names


def _read_class(node: ast.ClassDef, into: _CodeClass) -> None:
    into.bases += [b.id for b in node.bases if isinstance(b, ast.Name)] + [b.attr for b in node.bases if isinstance(b, ast.Attribute)]
    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            if item.name in _OPAQUE:
                into.opaque = True
            if not item.name.startswith("_"):
                into.methods.add(item.name)
                if _is_property(item):
                    into.properties.add(item.name)
            receiver = item.args.args[0].arg if item.args.args else None
            for sub in ast.walk(item):  # self.name = ... anywhere in the method
                if (
                    isinstance(sub, ast.Attribute)
                    and isinstance(sub.ctx, ast.Store)
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id == receiver
                    and not sub.attr.startswith("_")
                ):
                    into.known.add(sub.attr)
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            if not item.target.id.startswith("_"):
                into.known.add(item.target.id)
                into.fields[item.target.id] = _type_names(item.annotation)
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    if target.id in _OPAQUE:
                        into.opaque = True
                    if not target.id.startswith("_"):
                        into.known.add(target.id)


def _scan(files: dict[str, str], unparsable: list[str] | None = None) -> dict[str, _CodeClass]:
    classes: dict[str, _CodeClass] = {}
    for path, text in files.items():
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            if unparsable is not None:
                unparsable.append(path)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                _read_class(node, classes.setdefault(node.name, _CodeClass()))
    return classes


def python_classes(files: dict[str, str], unparsable: list[str] | None = None) -> dict[str, set[str]]:
    """Class name -> public methods, inherited methods included (bases found in the same files)."""
    scanned = _scan(files, unparsable)
    bases = {name: c.bases for name, c in scanned.items()}
    return {name: c.methods.union(*(scanned[a].methods for a in ancestors(name, bases) if a in scanned)) for name, c in scanned.items()}


def compare_design_and_code(class_diagrams: str | Iterable[str], files: dict[str, str]) -> DriftReport:
    """Compare the code with all class diagrams of the design, read together (one text or several).

    Private names (leading underscore) are implementation details on both sides: private classes in
    the code and private operations in the diagram are not drift (real run s03: 10 of 11 lines were such)."""
    model = class_model([class_diagrams] if isinstance(class_diagrams, str) else class_diagrams)
    unparsable: list[str] = []
    scanned = _scan(files, unparsable)
    code_bases = {name: c.bases for name, c in scanned.items()}
    designed = set(model.operations)
    coded = {name for name in scanned if not name.startswith("_")}
    both = sorted(designed & coded)

    def code_ancestors(name: str) -> set[str]:
        return {a for a in ancestors(name, code_bases) if a in scanned}

    def all_methods(name: str) -> set[str]:
        return scanned[name].methods.union(*(scanned[a].methods for a in code_ancestors(name)))

    report = DriftReport(unparsable=unparsable)
    report.missing_in_code = sorted(designed - coded)
    report.missing_in_diagram = sorted(coded - designed)

    # Inheritance and realisation, for classes both sides have.
    for child in both:
        for parent in sorted(model.parents.get(child, set()) & coded):
            if parent in code_ancestors(child):
                continue
            if "Protocol" in scanned[parent].bases and all_methods(parent) <= all_methods(child):
                continue  # structural typing: the class has every method of the protocol
            report.inheritance_missing_in_code.append(f"{child}({parent})")
        for parent in sorted(set(scanned[child].bases) & designed & coded):
            if parent not in model.ancestors(child):
                report.inheritance_missing_in_diagram.append(f"{child}({parent})")

    for name in both:
        # What a class inherits from a class both sides have is that class's line, or the inheritance line.
        design_parents = [p for p in model.ancestors(name) if p not in coded]
        code_parents = [p for p in code_ancestors(name) if p not in designed]
        wanted = model.operations[name].union(*(model.operations.get(p, set()) for p in design_parents))
        wanted = {op for op in wanted if not op.startswith("_")}
        own = scanned[name].methods.union(*(scanned[p].methods for p in code_parents))
        shown = model.all_operations(name) | model.all_attributes(name)  # a property may be drawn as an attribute
        report.operations_missing_in_code += [f"{name}.{op}" for op in sorted(wanted - all_methods(name))]
        report.operations_missing_in_diagram += [f"{name}.{op}" for op in sorted(own - shown)]

        family = [scanned[name], *(scanned[a] for a in code_ancestors(name))]
        readable = all(not c.opaque and all(b in scanned or b in _READABLE_BASES for b in c.bases) for c in family)
        if readable:
            declared = model.public_attributes[name].union(*(model.public_attributes.get(p, set()) for p in design_parents))
            has = set().union(*(c.known | c.properties for c in family))
            report.attributes_missing_in_code += [f"{name}.{a}" for a in sorted(declared - has) if not a.startswith("_")]
        if model.all_attributes(name):
            extra = [a for a, types in scanned[name].fields.items() if "ClassVar" not in types and not (types & designed)]
            report.attributes_missing_in_diagram += [f"{name}.{a}" for a in sorted(set(extra) - model.all_attributes(name))]
    return report
