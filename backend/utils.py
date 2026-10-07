"""
Shared utility functions for backend routes.
"""

from functools import wraps
from flask import request, jsonify

# Preferred display order for cartomancy types
TYPE_ORDER = ['Tarot', 'Petit Lenormand', 'Oracle', 'Playing Cards',
              'Playing Cards (Latin-suited)', 'Playing Cards (German-suited)',
              'Kipper', 'I Ching']

# Maximum allowed length for text fields (prevents abuse on a local app)
MAX_NAME_LENGTH = 200
MAX_TEXT_LENGTH = 50000


def row_to_dict(row):
    """Convert a sqlite3.Row to a dictionary, or return None if row is None."""
    return dict(row) if row else None


def sort_types(types):
    """Sort types by preferred display order, with unknown types at the end."""
    def sort_key(t):
        name = t.get('name', '') if isinstance(t, dict) else t['name']
        try:
            return TYPE_ORDER.index(name)
        except ValueError:
            return len(TYPE_ORDER)
    return sorted(types, key=sort_key)


def require_json(f):
    """Decorator that parses JSON body and returns 400 if missing/invalid.

    Injects the parsed dict as the last positional argument to the handler,
    so the route function signature should accept a `data` parameter after
    any URL parameters.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400
        kwargs['data'] = data
        return f(*args, **kwargs)
    return wrapper


def validate_length(value, max_len=MAX_NAME_LENGTH, field_name='value'):
    """Check that a string value doesn't exceed max_len. Returns error string or None."""
    if value and len(value) > max_len:
        return f'{field_name} must be {max_len} characters or less'
    return None
