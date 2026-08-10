from typing import Any


class JmixCliError(Exception):
    """Base exception for all jmix_cli errors."""
    pass


class ConfigurationError(JmixCliError):
    """Raised when configuration files or project structure are invalid."""
    pass


class GenerationError(JmixCliError):
    """Raised when code generation fails (entity, view, liquibase, etc.)."""
    pass


class UserInputError(JmixCliError):
    """Raised when command-line arguments or user input are invalid."""
    pass


class InvalidCsvError(ConfigurationError):
    """Raised when a CSV file is missing or has invalid schema."""
    def __init__(self, file_path: str, missing_columns: list[str] | None = None, message: str | None = None) -> None:
        self.file_path = file_path
        self.missing_columns = missing_columns
        if message:
            super().__init__(message)
        else:
            msg = f"Invalid CSV: {file_path}"
            if missing_columns:
                msg += f" (missing columns: {', '.join(missing_columns)})"
            super().__init__(msg)


class MissingProjectError(ConfigurationError):
    """Raised when no valid Jmix project is detected."""
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"No valid Jmix project detected at: {path}")


class GitOperationError(GenerationError):
    """Raised when a git operation fails."""
    pass
