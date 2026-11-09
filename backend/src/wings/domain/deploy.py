"""Static checks on deployment files, by code: does the Dockerfile copy what exists and start what is there?"""

import re
import shlex

_COPY = re.compile(r"^\s*(?:COPY|ADD)\s+(?:--\S+\s+)*(.+?)\s*$", re.IGNORECASE)
_MODULE = re.compile(r"python[0-9.]*\"?\s*,?\s*\"?-m\"?\s*,?\s*\"?([A-Za-z_][\w.]*)")


def _exists(src: str, paths: set[str]) -> bool:
    src = src.strip().strip('"').rstrip("/")
    if src in ("", "."):
        return True
    return src in paths or any(p.startswith(src + "/") for p in paths)


def modules_started(text: str) -> list[str]:
    """Modules started with `python -m X` in a Dockerfile or a script."""
    return list(dict.fromkeys(_MODULE.findall(text)))


def check_deployment(deploy_files: dict[str, str], code_paths: set[str]) -> list[str]:
    """Problems a reader could find by looking: missing Dockerfile parts, copies of files that do not exist,
    modules started that the code does not contain."""
    problems: list[str] = []
    paths = set(code_paths) | set(deploy_files)
    packages = {p.split("/")[0] for p in code_paths if p.endswith("__main__.py")}
    dockerfile = next((t for p, t in deploy_files.items() if p.split("/")[-1] == "Dockerfile"), None)
    if dockerfile is not None:
        lines = [line for line in dockerfile.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not any(line.strip().upper().startswith("FROM ") for line in lines):
            problems.append("Dockerfile: no FROM line.")
        if not any(line.strip().upper().startswith(("CMD", "ENTRYPOINT")) for line in lines):
            problems.append("Dockerfile: no CMD or ENTRYPOINT, the container would not start the program.")
        for line in lines:
            m = _COPY.match(line)
            if m:
                parts = shlex.split(m.group(1).replace("[", " ").replace("]", " ").replace(",", " "))
                for src in parts[:-1]:
                    if not _exists(src, paths):
                        problems.append(f"Dockerfile copies '{src}', which is not in the project.")
    for path, text in deploy_files.items():
        for module in modules_started(text):
            if module.split(".")[0] not in packages and f"{module.replace('.', '/')}.py" not in paths:
                problems.append(f"{path} starts 'python -m {module}', but the code has no such module.")
    return list(dict.fromkeys(problems))
