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


class SchedulerError(CADError):
    """Raised for batch scheduler / job management errors."""


class VersionError(CADError):
    """Raised for version snapshot / restore errors."""


class ViewError(CADError):
    """Raised for 3D view definition errors."""


class RateLimitError(CADError):
    """Raised when an HTTP client exceeds its request rate limit."""


class VariableError(CADError):
    """Raised for parametric variable / expression errors."""


class ConstraintError(CADError):
    """Raised for geometric constraint / solver errors."""


class AssemblyError(CADError):
    """Raised for assembly modeling errors."""


class DrawingError(CADError):
    """Raised for engineering drawing errors."""


class SimulationError(CADError):
    """Raised for simulation lifecycle / execution errors."""


class CollabError(CADError):
    """Raised for collaboration session / sync errors."""


class PluginError(CADError):
    """Raised for plugin lifecycle / permission errors."""
