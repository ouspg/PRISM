"""Custom exceptions for the prism-analyze pipeline."""


class InsufficientDataError(Exception):
    """Raised when the input data does not meet minimum requirements."""


class ValidationError(Exception):
    """Raised when input data fails validation checks."""


class CatalogError(Exception):
    """Raised when a catalog file is malformed or contains invalid entries."""
