"""Exception hierarchy for the CAD system."""


class CADError(Exception):
    """Base class for all CAD errors."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        """Initialize the error with a message and optional error code."""
        super().__init__(message)
        self.message = message
        self.code = code


class DocumentError(CADError):
    """Raised for document / file management errors."""


class EntityError(CADError):
    """Raised for geometry entity errors."""


class LayerError(CADError):
    """Raised for layer management errors."""


class StyleError(CADError):
    """Raised for style management errors."""


class SessionError(CADError):
    """Raised for session lifecycle errors."""


class KernelError(CADError):
    """Raised for CAD kernel / geometry kernel errors."""


class CADImportError(CADError):
    """Raised when importing a file fails."""


class CADExportError(CADError):
    """Raised when exporting a file fails."""


class CADValidationError(CADError):
    """Raised when data fails schema validation."""


class CADNotImplementedError(CADError):
    """Raised when a backend does not support an operation."""
