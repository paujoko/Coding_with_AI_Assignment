"""Architecture rules, enforced. See docs/code/architecture.md.

Each layer may only import from the layers listed as allowed. A failure lists
`file:line imports module` so the offending import is easy to find. Relative
imports are resolved to absolute module names first, so `from ..adapters import x`
is caught like `from wings.adapters import x`.
"""

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "wings"

# Internal packages each layer must NOT import.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": ("wings.application", "wings.phases", "wings.adapters", "wings.api", "wings.bootstrap", "wings.cli", "wings.config", "wings.main"),
    "application": ("wings.phases", "wings.adapters", "wings.api", "wings.bootstrap", "wings.cli", "wings.config", "wings.main"),
    "phases": ("wings.adapters", "wings.api", "wings.bootstrap", "wings.cli", "wings.config", "wings.main"),
    "adapters": ("wings.phases", "wings.api", "wings.bootstrap", "wings.cli", "wings.main"),
    "api": ("wings.adapters", "wings.phases", "wings.bootstrap", "wings.cli", "wings.main"),
}

# The pure layers may use the standard library, Pydantic and wings itself, nothing else.
# A wing that needs the outside world (HTTP, an LLM SDK, subprocesses) gets a port instead.
ALLOWED_THIRD_PARTY = {"pydantic", "pydantic_core", "wings"}
PURE_LAYERS = ("domain", "application", "phases")
# Standard-library modules that reach the outside world and belong behind a port.
FORBIDDEN_STDLIB = {"subprocess", "socket", "urllib", "http"}


def _module_name(path: Path) -> str:
    parts = ["wings", *path.relative_to(SRC).with_suffix("").parts]
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path) -> list[tuple[int, str]]:
    """Absolute module names imported by a file, relative imports resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _module_name(path).split(".")
    if path.name != "__init__.py":
        package = package[:-1]
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                anchor = package[: len(package) - (node.level - 1)] if node.level > 1 else package
                base = ".".join([*anchor, *([node.module] if node.module else [])])
            found.append((node.lineno, base))
            if node.level and not node.module:  # `from .. import adapters`
                found += [(node.lineno, f"{base}.{alias.name}") for alias in node.names]
    return found


def _files(layer: str) -> list[Path]:
    return sorted((SRC / layer).rglob("*.py"))


def _matches(module: str, prefixes) -> bool:
    return any(module == p or module.startswith(p + ".") for p in prefixes)


def test_layers_respect_dependency_rules():
    bad = [
        f"{file.relative_to(SRC)}:{line} imports {module}"
        for layer, prefixes in FORBIDDEN.items()
        for file in _files(layer)
        for line, module in _imports(file)
        if _matches(module, prefixes)
    ]
    assert not bad, "Layer rule violations:\n" + "\n".join(bad)


def test_pure_layers_only_use_stdlib_and_pydantic():
    bad = []
    for layer in PURE_LAYERS:
        for file in _files(layer):
            for line, module in _imports(file):
                top = module.split(".")[0]
                if top in FORBIDDEN_STDLIB or (top not in sys.stdlib_module_names and top not in ALLOWED_THIRD_PARTY):
                    bad.append(f"{file.relative_to(SRC)}:{line} imports {module}")
    assert not bad, "Pure layers must reach the outside world through ports:\n" + "\n".join(bad)


def test_phases_do_not_import_each_other():
    bad = []
    for phase_dir in sorted(p for p in (SRC / "phases").iterdir() if p.is_dir() and not p.name.startswith("_")):
        own = f"wings.phases.{phase_dir.name}"
        for file in phase_dir.rglob("*.py"):
            for line, module in _imports(file):
                if module.startswith("wings.phases") and not _matches(module, (own,)):
                    bad.append(f"{file.relative_to(SRC)}:{line} imports {module}")
    assert not bad, "Wings must only talk through artifacts:\n" + "\n".join(bad)


def test_the_resolver_catches_relative_escapes(tmp_path):
    # Guard for the test itself: a relative import out of application must resolve to wings.adapters.
    fake = SRC / "application" / "_probe_for_test.py"
    fake.write_text("from ..adapters.fs_store import FileSystemStore\nfrom .. import phases\n", encoding="utf-8")
    try:
        modules = [m for _, m in _imports(fake)]
    finally:
        fake.unlink()
    assert "wings.adapters.fs_store" in modules and "wings.phases" in modules
