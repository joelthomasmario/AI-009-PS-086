"""
validation.py – Input validation helpers for commands and entities.

Shared module – AI-009
Team: AI-009  Section: 6BTAI
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Raised when a command or input fails validation."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"[{field}] {message}")


def require_non_empty(value: Any, field: str) -> str:
    """Ensure a string field is non-empty after stripping whitespace."""
    s = str(value).strip()
    if not s:
        raise ValidationError(field, "Value must not be empty.")
    return s


def require_positive_int(value: Any, field: str) -> int:
    """Ensure the value can be cast to a positive integer."""
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field, f"'{value}' is not a valid integer.")
    if n <= 0:
        raise ValidationError(field, f"Value must be a positive integer, got {n}.")
    return n


def require_non_negative_int(value: Any, field: str) -> int:
    """Ensure the value can be cast to a non-negative integer."""
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field, f"'{value}' is not a valid integer.")
    if n < 0:
        raise ValidationError(field, f"Value must be >= 0, got {n}.")
    return n


def require_datetime(value: Any, field: str, fmt: str = "%Y-%m-%dT%H:%M:%S") -> datetime:
    """Parse a datetime string.

    Supported formats: ISO 8601 (with or without T), date-only (YYYY-MM-DD).
    """
    s = str(value).strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for f in formats:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    raise ValidationError(
        field,
        f"'{s}' is not a recognised datetime. "
        "Use YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD.",
    )


def require_choice(value: Any, field: str, choices: List[str]) -> str:
    """Ensure the value is one of the allowed choices (case-insensitive)."""
    s = str(value).strip().upper()
    upper_choices = [c.upper() for c in choices]
    if s not in upper_choices:
        raise ValidationError(
            field,
            f"'{value}' is not a valid choice. Allowed: {choices}",
        )
    return s


def require_id(value: Any, field: str) -> str:
    """Ensure an ID is non-empty and alphanumeric with optional dashes/underscores."""
    s = require_non_empty(value, field)
    if not re.match(r"^[A-Za-z0-9_\-]+$", s):
        raise ValidationError(
            field,
            f"'{s}' contains invalid characters. IDs must be alphanumeric "
            "with optional hyphens or underscores.",
        )
    return s


def require_float(value: Any, field: str) -> float:
    """Ensure the value can be cast to a float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        raise ValidationError(field, f"'{value}' is not a valid number.")


def validate_command_fields(
    command: str,
    row: Dict[str, str],
    required_fields: List[str],
) -> None:
    """Ensure all required fields are present and non-empty in a command row.

    Args:
        command: Command name (for error reporting).
        row: Parsed key->value mapping.
        required_fields: Fields that must be present and non-empty.

    Raises:
        ValidationError: If any required field is missing or empty.
    """
    for f in required_fields:
        if f not in row or not str(row[f]).strip():
            raise ValidationError(
                f,
                f"Command '{command}' requires field '{f}' but it is missing or empty.",
            )


