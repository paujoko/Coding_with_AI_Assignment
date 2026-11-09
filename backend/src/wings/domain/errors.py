class DomainError(Exception):
    """Base for rule violations the developer can understand and fix."""


class PhaseLockedError(DomainError):
    pass


class InvalidTransitionError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class InvalidInputError(DomainError, ValueError):
    """Input from the developer (or a hand edit) that cannot be accepted. Maps to HTTP 422."""


class ConflictError(DomainError):
    """The project changed underneath the request (e.g. another process saved it). Maps to HTTP 409."""
