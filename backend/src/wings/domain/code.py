"""Design versus code, computed by code: which classes and operations of the class diagram the
Python sources implement, and what the code has that the diagram does not show (drift).

Uses the standard `ast` module only. Public methods count as operations; private helpers
(leading underscore) and dunder methods are implementation details.
"""

import ast

from pydantic import BaseModel, Field

from wings.domain.uml import parse_classes


class DriftReport(BaseModel):
    missing_in_code: list[str] = Field(default_factory=list)  # classes in the diagram, not in the code
    missing_in_diagram: list[str] = Field(default_factory=list)  # classes in the code, not in the diagram
    operations_missing_in_code: list[str] = Field(default_factory=list)  # "Class.op"
    operations_missing_in_diagram: list[str] = Field(default_factory=list)
    unparsable: list[str] = Field(default_factory=list)  # files that are not valid Python

    @property
    def in_sync(self) -> bool:
        return not (self.missing_in_code or self.missing_in_diagram or self.operations_missing_in_code or self.operations_missing_in_diagram)

    def lines(self) -> list[str]:
        out = [f"{c} is in the class diagram but not in the code." for c in self.missing_in_code]
        out += [f"{c} is in the code but not in the class diagram." for c in self.missing_in_diagram]
        out += [f"{o}() is in the class diagram but not in the code." for o in self.operations_missing_in_code]
        out += [f"{o}() is in the code but not in the class diagram." for o in self.operations_missing_in_diagram]
        out += [f"{f} is not valid Python." for f in self.unparsable]
        return out


def python_classes(files: dict[str, str], unparsable: list[str] | None = None) -> dict[str, set[str]]:
    """Class name -> public methods, inherited methods included (bases found in the same files)."""
    classes: dict[str, set[str]] = {}
    bases: dict[str, list[str]] = {}
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
                methods = {
                    f.name for f in node.body if isinstance(f, ast.FunctionDef | ast.AsyncFunctionDef) and not f.name.startswith("_")
                }
                classes[node.name] = classes.get(node.name, set()) | methods
                bases[node.name] = [b.id for b in node.bases if isinstance(b, ast.Name)] + [
                    b.attr for b in node.bases if isinstance(b, ast.Attribute)
                ]
    for _ in range(len(classes)):
        for name, parents in bases.items():
            for parent in parents:
                classes[name] |= classes.get(parent, set())
    return classes


def compare_design_and_code(class_diagram: str, files: dict[str, str]) -> DriftReport:
    designed = parse_classes(class_diagram)
    unparsable: list[str] = []
    coded = python_classes(files, unparsable)
    report = DriftReport(unparsable=unparsable)
    report.missing_in_code = sorted(c for c in designed if c not in coded)
    report.missing_in_diagram = sorted(c for c in coded if c not in designed)
    for name in sorted(set(designed) & set(coded)):
        report.operations_missing_in_code += [f"{name}.{op}" for op in sorted(designed[name] - coded[name])]
        report.operations_missing_in_diagram += [f"{name}.{op}" for op in sorted(coded[name] - designed[name])]
    return report
