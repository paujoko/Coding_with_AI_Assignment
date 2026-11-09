"""Architecture rules, enforced. See docs/code/architecture.md.

Each layer may only import from the layers listed as allowed. A failure lists
`file:line imports module` so the offending import is easy to find.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "wings"

# Internal packages each layer must NOT import.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": ("wings.application", "wings.phases", "wings.adapters", "wings.api", "wings.bootstrap", "wings.cli", "wings.config"),
    "application": ("wings.phases", "wings.adapters", "wings.api", "wings.bootstrap", "wings.cli", "wings.config"),
    "phases": ("wings.adapters", "wings.api", "wings.bootstrap", "wings.cli", "wings.config"),
    "adapters": ("wings.phases", "wings.api", "wings.bootstrap", "wings.cli"),
    "api": ("wings.adapters", "wings.phases", "wings.bootstrap", "wings.cli"),
}

# Third-party packages that must stay out of the pure layers.
FORBIDDEN_THIRD_PARTY: dict[str, tuple[str, ...]] = {
    "domain": ("fastapi", "httpx", "uvicorn", "starlette"),
    "application": ("fastapi", "httpx", "uvicorn", "starlette"),
    "phases": ("fastapi", "httpx", "uvicorn", "starlette"),
}


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
    return found


def _files(layer: str) -> list[Path]:
    return sorted((SRC / layer).rglob("*.py"))


def _violations(layer: str, prefixes: tuple[str, ...]) -> list[str]:
    bad = []
    for file in _files(layer):
        for line, module in _imports(file):
            if any(module == p or module.startswith(p + ".") for p in prefixes):
                bad.append(f"{file.relative_to(SRC)}:{line} imports {module}")
    return bad


def test_layers_respect_dependency_rules():
    bad = [v for layer, prefixes in FORBIDDEN.items() for v in _violations(layer, prefixes)]
    assert not bad, "Layer rule violations:\n" + "\n".join(bad)


def test_pure_layers_stay_framework_free():
    bad = [v for layer, prefixes in FORBIDDEN_THIRD_PARTY.items() for v in _violations(layer, prefixes)]
    assert not bad, "Framework imports in pure layers:\n" + "\n".join(bad)


def test_phases_do_not_import_each_other():
    bad = []
    for phase_dir in sorted(p for p in (SRC / "phases").iterdir() if p.is_dir() and not p.name.startswith("_")):
        own = f"wings.phases.{phase_dir.name}"
        for file in phase_dir.rglob("*.py"):
            for line, module in _imports(file):
                if module.startswith("wings.phases.") and not (module == own or module.startswith(own + ".")):
                    bad.append(f"{file.relative_to(SRC)}:{line} imports {module}")
    assert not bad, "Wings must only talk through artifacts:\n" + "\n".join(bad)


def test_relative_imports_do_not_escape_their_phase():
    # `from ..design import x` inside a phase would bypass the rule above.
    bad = []
    for file in _files("phases"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        depth = len(file.relative_to(SRC / "phases").parts) - 1
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > depth:
                bad.append(f"{file.relative_to(SRC)}:{node.lineno} relative import level {node.level}")
    assert not bad, "\n".join(bad)
