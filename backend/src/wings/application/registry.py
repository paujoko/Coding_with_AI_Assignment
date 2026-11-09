"""Phase registry: the pipeline is just the ordered list of registered wings."""

from importlib.resources import files

from wings.application.phase import PhaseModule
from wings.domain.errors import NotFoundError
from wings.domain.phases import PhaseId


class RegistryError(Exception):
    pass


class PhaseRegistry:
    def __init__(self, modules: list[PhaseModule]):
        self._modules = {m.id: m for m in modules}
        if len(self._modules) != len(modules):
            raise RegistryError("Two modules registered for the same phase.")
        for m in modules:
            unknown = [r for r in m.requires if r not in self._modules]
            if unknown:
                raise RegistryError(f"{m.id.value} requires unregistered phases: {unknown}")
        self._check_acyclic()

    def get(self, phase: PhaseId | str) -> PhaseModule:
        try:
            return self._modules[PhaseId(phase)]
        except (ValueError, KeyError):
            raise NotFoundError(f"Unknown phase '{phase}'.") from None

    def ordered(self) -> list[PhaseModule]:
        return list(self._modules.values())

    def dependencies(self) -> dict[PhaseId, list[PhaseId]]:
        return {pid: list(m.requires) for pid, m in self._modules.items()}

    def _check_acyclic(self) -> None:
        state: dict[PhaseId, str] = {}

        def visit(pid: PhaseId) -> None:
            if state.get(pid) == "done":
                return
            if state.get(pid) == "visiting":
                raise RegistryError(f"Dependency cycle through '{pid.value}'.")
            state[pid] = "visiting"
            for req in self._modules[pid].requires:
                visit(req)
            state[pid] = "done"

        for pid in self._modules:
            visit(pid)


def load_prompt(package: str, name: str) -> str:
    """Prompts live next to their wing in `prompts/*.md`, versioned with the code."""
    return files(package).joinpath("prompts", name).read_text(encoding="utf-8").strip()
