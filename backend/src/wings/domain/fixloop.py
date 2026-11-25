"""The memory of one fix loop in testing: run, explain, fix, run again.

Each explanation is an attempt: which tests failed, what the debugger said, what it changed. The next
run records which tests still fail. The next explanation and the code fix get this history, so a fix
that did not help is not tried again (real run 2026-11-25: every explanation started from zero).
A green run or newly written tests end the loop.
"""

from typing import Literal

from pydantic import BaseModel, Field

Cause = Literal["code", "test", "environment"]


class Attempt(BaseModel):
    number: int
    failing: list[str]  # test names failing before the attempt
    cause: Cause
    diagnosis: str
    fix: str
    changed: list[str] = Field(default_factory=list)  # files the attempt rewrote (test fixes)
    after: list[str] | None = None  # failing in the next run; None until the tests ran again


def _names(names: list[str]) -> str:
    return ", ".join(names) if names else "none"


class FixLog(BaseModel):
    attempts: list[Attempt] = Field(default_factory=list)

    def attempt(self, failing: list[str], cause: Cause, diagnosis: str, fix: str, changed: list[str]) -> "FixLog":
        item = Attempt(number=len(self.attempts) + 1, failing=failing, cause=cause, diagnosis=diagnosis, fix=fix, changed=changed)
        return FixLog(attempts=[*self.attempts, item])

    def after_run(self, failing: list[str]) -> "FixLog":
        """The tests ran: the latest attempt learns what still fails. Later runs do not overwrite it."""
        if not self.attempts or self.attempts[-1].after is not None:
            return self
        last = self.attempts[-1].model_copy(update={"after": failing})
        return FixLog(attempts=[*self.attempts[:-1], last])

    def stuck(self) -> list[str]:
        """Tests that still failed after every attempt that was followed by a run (at least two)."""
        judged = [a for a in self.attempts if a.after is not None]
        if len(judged) < 2:
            return []
        return sorted(set.intersection(*(set(a.after or []) for a in judged)))

    def _outcome(self, a: Attempt) -> str:
        if a.after is None:
            return "The tests were not run again yet after it."
        if not a.after:
            return "After it: all tests pass."
        fixed = [n for n in a.failing if n not in a.after]
        still = [n for n in a.failing if n in a.after]
        new = [n for n in a.after if n not in a.failing]
        parts = [f"still failing: {_names(still)}"]
        if fixed:
            parts.insert(0, f"fixed: {_names(fixed)}")
        if new:
            parts.append(f"newly failing: {_names(new)}")
        return "After it, " + "; ".join(parts) + "."

    def prompt(self) -> str:
        """The history for the debugger or the coder; empty when there is none."""
        if not self.attempts:
            return ""
        lines = ["Earlier attempts in this fix loop (oldest first):"]
        for a in self.attempts:
            changed = f" Changed: {', '.join(a.changed)}." if a.changed else ""
            lines.append(f"Attempt {a.number} (cause: {a.cause}): {a.diagnosis} Fix: {a.fix}{changed} {self._outcome(a)}")
        for name in self.stuck():
            judged = sum(a.after is not None for a in self.attempts)
            lines.append(f"{name} still fails after {judged} attempts: question whether the code or the test is wrong before trying again.")
        lines.append("Do not repeat a fix that did not help. Build on what the earlier attempts found.")
        return "\n".join(lines)

    def markdown(self) -> str:
        lines = ["# Fix attempts", ""]
        for a in self.attempts:
            lines += [f"## Attempt {a.number} (cause: {a.cause})", "", f"Failing before: {_names(a.failing)}.", "", a.diagnosis, "", f"Fix: {a.fix}"]
            if a.changed:
                lines += ["", f"Changed: {', '.join(a.changed)}."]
            lines += ["", self._outcome(a), ""]
        return "\n".join(lines).rstrip() + "\n"
