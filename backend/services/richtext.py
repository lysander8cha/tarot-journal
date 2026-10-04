"""
Normalize stored entry content to HTML for the frontend.

Entries from the React frontend are stored as HTML (Tiptap output).
Very old entries may be plain text, or XML from the retired wxPython
editor; those are shown as plain paragraphs.
"""

from __future__ import annotations

import re
from html import escape


def convert_content_to_html(content: str | None) -> str:
    """Convert stored content to HTML for the frontend.

    - Legacy wxPython XML (starts with <?xml or <richtext>) → tags
      stripped, text wrapped in <p> tags (formatting is dropped)
    - HTML (starts with <) → passed through unchanged
    - Plain text → wrapped in <p> tags
    """
    if not content or not content.strip():
        return ''

    stripped = content.strip()

    if stripped.startswith('<?xml') or stripped.startswith('<richtext'):
        return _plain_text_to_html(re.sub(r'<[^>]+>', '', stripped))

    if stripped.startswith('<'):
        return content

    return _plain_text_to_html(stripped)


def _plain_text_to_html(text: str) -> str:
    """Wrap plain text in <p> tags, preserving line breaks."""
    paragraphs = []
    for line in text.split('\n'):
        escaped = escape(line)
        paragraphs.append(f'<p>{escaped}</p>' if escaped else '<p><br></p>')
    return ''.join(paragraphs)
