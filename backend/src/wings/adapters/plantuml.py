"""PlantUML rendering to SVG.

Two ways, in this order: a local plantuml.jar (Java is needed) or a PlantUML
server (POST <url>/svg with the source as body, e.g. the official Docker image
plantuml/plantuml-server). Without either, render_svg returns None and the UI
shows the source text instead.
"""

import hashlib
import subprocess
from pathlib import Path

import httpx


class PlantUMLRenderer:
    def __init__(self, jar: Path | None = None, server_url: str | None = None, timeout: float = 30.0):
        self._jar = Path(jar) if jar else None
        self._server = server_url.rstrip("/") if server_url else None
        self._timeout = timeout
        self._cache: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return bool((self._jar and self._jar.exists()) or self._server)

    def render_svg(self, source: str) -> str | None:
        key = hashlib.sha256(source.encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        svg = self._via_jar(source) if self._jar and self._jar.exists() else None
        if svg is None and self._server:
            svg = self._via_server(source)
        if svg is not None:
            self._cache[key] = svg
        return svg

    def _via_jar(self, source: str) -> str | None:
        try:
            done = subprocess.run(
                ["java", "-jar", str(self._jar), "-tsvg", "-pipe", "-charset", "UTF-8"],
                input=source.encode("utf-8"),
                capture_output=True,
                timeout=self._timeout,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        out = done.stdout.decode("utf-8", errors="replace")
        return out if done.returncode == 0 and "<svg" in out else None

    def _via_server(self, source: str) -> str | None:
        try:
            resp = httpx.post(f"{self._server}/svg", content=source.encode("utf-8"), timeout=self._timeout)
        except httpx.HTTPError:
            return None
        return resp.text if resp.status_code == 200 and "<svg" in resp.text else None
