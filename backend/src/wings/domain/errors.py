class DomainError(Exception):
    """Base for rule violations the developer can understand and fix."""


class PhaseLockedError(DomainError):
    pass


class InvalidTransitionError(DomainError):
    pass


class NotFoundError(DomainError):
    pass
