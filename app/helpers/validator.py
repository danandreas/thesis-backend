import re
from flask import request


def get_json_body():
    """Safely get JSON body from request."""
    return request.get_json(silent=True) or {}


def validate_required(data: dict, fields: list) -> dict:
    """
    Validate required fields in a dict.
    Returns dict of errors (empty if all valid).
    """
    errors = {}
    for field in fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field] = [f"Field '{field}' wajib diisi."]
    return errors


def validate_email(email: str) -> bool:
    """Simple email format validation."""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email))


def validate_min_length(value: str, min_len: int) -> bool:
    return len(str(value)) >= min_len


def validate_max_length(value: str, max_len: int) -> bool:
    return len(str(value)) <= max_len
