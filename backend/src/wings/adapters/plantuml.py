"""PlantUML rendering to SVG.

Two ways, in this order: a local plantuml.jar (Java is needed) or a PlantUML
server (GET <url>/svg/<encoded source>, e.g. https://www.plantuml.com/plantuml or
the Docker image plantuml/plantuml-server). Without either, render_svg returns
None and the UI shows the source text instead.

Two details make diagrams usable out of the box:
- Without Graphviz (`dot`), PlantUML draws an error picture instead of class and
  use case diagrams. The jar is then called with its built-in Java layout
  engine (Smetana), and an error picture is never passed on as a diagram.
- Every diagram is drawn in the house style of the interface (strict UML
  notation, the app's ink and neutrals). The style is added only when
  rendering; the stored source stays exactly what the agent or developer wrote,
  and skinparams inside a diagram still win because they come later.
"""

import hashlib
import shutil
import subprocess
import zlib
from pathlib import Path

import httpx

HOUSE_STYLE = """\
skinparam style strictuml
skinparam backgroundColor transparent
skinparam shadowing false
skinparam roundCorner 4
skinparam defaultFontName Helvetica
skinparam defaultFontSize 13
skinparam defaultFontColor #1b1d21
skinparam ArrowColor #50555e
skinparam ArrowFontColor #50555e
skinparam ArrowFontSize 12
skinparam ActorBorderColor #1b1d21
skinparam ActorBackgroundColor #ffffff
skinparam UsecaseBorderColor #1b1d21
skinparam UsecaseBackgroundColor #ffffff
skinparam ClassBorderColor #1b1d21
skinparam ClassBackgroundColor #ffffff
skinparam ClassHeaderBackgroundColor #f1f2ef
skinparam ClassAttributeIconSize 0
skinparam PackageBorderColor #8a8f98
skinparam RectangleBorderColor #8a8f98
skinparam ComponentBorderColor #1b1d21
skinparam ComponentBackgroundColor #ffffff
skinparam NodeBorderColor #1b1d21
skinparam NodeBackgroundColor #ffffff
skinparam ParticipantBorderColor #1b1d21
skinparam ParticipantBackgroundColor #ffffff
skinparam SequenceLifeLineBorderColor #8a8f98
skinparam SequenceGroupBorderColor #8a8f98
skinparam SequenceGroupHeaderFontColor #50555e
skinparam ActivityBorderColor #1b1d21
skinparam ActivityBackgroundColor #ffffff
skinparam StateBorderColor #1b1d21
skinparam StateBackgroundColor #ffffff
skinparam NoteBorderColor #c9b26b
skinparam NoteBackgroundColor #fbf6e4
"""

# Text PlantUML puts into the picture when it cannot lay the diagram out.
_ERROR_MARKERS = ("Dot Executable", "Cannot find Graphviz", "dot executable does not exist")


_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def encode(source: str) -> str:
    """PlantUML's text encoding for server URLs: raw deflate, then its own 64-character alphabet."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = compressor.compress(source.encode("utf-8")) + compressor.flush()
    out = []
    for i in range(0, len(data), 3):
        chunk = data[i : i + 3] + b"\0" * (3 - len(data[i : i + 3]))
        b1, b2, b3 = chunk
        for c in (b1 >> 2, ((b1 & 0x3) << 4) | (b2 >> 4), ((b2 & 0xF) << 2) | (b3 >> 6), b3 & 0x3F):
            out.append(_ALPHABET[c])
    return "".join(out)


def with_house_style(source: str) -> str:
    """Insert the house style right after the first @startuml line."""
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("@startuml"):
            return "\n".join([*lines[: i + 1], HOUSE_STYLE.rstrip("\n"), *lines[i + 1 :]]) + "\n"
    return source


def is_error_svg(svg: str) -> bool:
    return any(marker.lower() in svg.lower() for marker in _ERROR_MARKERS)


class PlantUMLRenderer:
    def __init__(
        self,
        jar: Path | None = None,
        server_url: str | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ):
        self._jar = Path(jar) if jar else None
        self._server = server_url.rstrip("/") if server_url else None
        self._timeout = timeout
        self._client = client
        self._cache: dict[str, str] = {}

    @property
    def java(self) -> bool:
        return shutil.which("java") is not None

    @property
    def _jar_ok(self) -> bool:
        return bool(self._jar and self._jar.exists() and self.java)

    @property
    def mode(self) -> str | None:
        """How diagrams are drawn: 'jar', 'server', or None."""
        return "jar" if self._jar_ok else "server" if self._server else None

    @property
    def available(self) -> bool:
        return self.mode is not None

    def render_svg(self, source: str) -> str | None:
        styled = with_house_style(source)
        key = hashlib.sha256(styled.encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        svg = self._via_jar(styled) if self._jar_ok else None
        if svg is None and self._server:
            svg = self._via_server(styled)
        if svg is not None:
            self._cache[key] = svg
        return svg

    def _via_jar(self, source: str) -> str | None:
        cmd = ["java", "-jar", str(self._jar), "-tsvg", "-pipe", "-charset", "UTF-8"]
        if shutil.which("dot") is None:
            cmd.append("-Playout=smetana")  # built-in layout engine, no Graphviz needed
        try:
            done = subprocess.run(cmd, input=source.encode("utf-8"), capture_output=True, timeout=self._timeout)
        except (OSError, subprocess.TimeoutExpired):
            return None
        out = done.stdout.decode("utf-8", errors="replace")
        return out if done.returncode == 0 and "<svg" in out and not is_error_svg(out) else None

    def check(self, source: str) -> str | None:
        """PlantUML's own syntax check (`-syntax`), on the source exactly as written so line numbers match.
        Only with a local jar; a server offers no syntax endpoint."""
        if not self._jar_ok:
            return None
        try:
            done = subprocess.run(
                ["java", "-jar", str(self._jar), "-syntax", "-charset", "UTF-8"],
                input=source.encode("utf-8"),
                capture_output=True,
                timeout=self._timeout,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        lines = [line.strip() for line in done.stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
        if not lines or lines[0] != "ERROR":
            return None
        # PlantUML counts lines from 0; people and models count from 1.
        where = f"Line {int(lines[1]) + 1}: " if len(lines) > 1 and lines[1].isdigit() else ""
        return where + (" ".join(lines[2:]) or "syntax error")

    def _via_server(self, source: str) -> str | None:
        url = f"{self._server}/svg/{encode(source)}"
        try:
            resp = self._client.get(url, timeout=self._timeout) if self._client else httpx.get(url, timeout=self._timeout)
        except httpx.HTTPError:
            return None
        ok = resp.status_code == 200 and "<svg" in resp.text and not is_error_svg(resp.text)
        return resp.text if ok else None
