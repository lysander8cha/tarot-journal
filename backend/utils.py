"""
Shared utility functions for backend routes.
"""

# Preferred display order for cartomancy types
TYPE_ORDER = ['Tarot', 'Lenormand', 'Oracle', 'Playing Cards', 'Kipper', 'I Ching']


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
