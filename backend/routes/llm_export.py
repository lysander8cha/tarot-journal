"""
LLM-readable export — renders a journal entry as structured markdown
suitable for pasting into any AI chat (Claude, ChatGPT, a local
model...). The app deliberately does no interpretation itself; this
is the "Librarian": it assembles the reading's full context so the
user can take the conversation wherever they choose.
"""

from __future__ import annotations

import html as html_mod
import re
from datetime import datetime

from collections import Counter

from flask import Blueprint, current_app, jsonify, request

from backend.routes.pdf_export import _hydrate_entry_for_pdf
from backend.routes.anki_export import FIELD_LABELS

llm_export_bp = Blueprint('llm_export', __name__)


def _html_to_text(raw: str) -> str:
    """Flatten stored rich text (HTML) to readable plain text."""
    if not raw:
        return ''
    s = raw
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</p>\s*<p[^>]*>', '\n\n', s, flags=re.I)
    s = re.sub(r'<li[^>]*>', '\n- ', s, flags=re.I)
    s = re.sub(r'</(p|div|ul|ol|h[1-6]|blockquote)>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = html_mod.unescape(s)
    # Collapse runs of blank lines
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def _pretty_datetime(raw: str) -> str:
    if not raw:
        return ''
    try:
        d = datetime.fromisoformat(raw.replace(' ', 'T'))
        return d.strftime('%B %-d, %Y, %-I:%M %p')
    except ValueError:
        return raw


def _card_display(card: dict) -> str:
    name = card.get('name') or 'Unknown card'
    out = f"**{name}**"
    if card.get('reversed'):
        out += " (reversed)"
    arch = card.get('archetype')
    if arch and arch != name:
        out += f" _[{arch}]_"
    return out


def _correspondence_line(db, card: dict) -> str | None:
    """Compact one-line correspondence summary for a card, or None."""
    card_id = card.get('card_id')
    if not card_id:
        return None
    parts = []
    for c in db.get_card_correspondences(card_id):
        if c.get('value'):
            label = FIELD_LABELS.get(c['field_name'],
                                     c['field_name'].replace('_', ' ').title())
            parts.append(f"{label}: {c['value']}")
    return ' · '.join(parts) if parts else None


def _reference_sections(entry: dict) -> list[str]:
    """Reference material for the drawn cards — deck custom fields and
    archetype source entries (already hydrated onto the cards). Cards
    are deduped across readings; empty when nothing is authored."""
    lines: list[str] = []
    seen_ids: set[int] = set()
    for rd in entry.get('readings') or []:
        for c in rd.get('cards_used') or []:
            cid = c.get('card_id')
            if not cid or cid in seen_ids:
                continue
            seen_ids.add(cid)
            card_lines: list[str] = []
            for f in c.get('custom_fields') or []:
                text = _html_to_text(f.get('field_value') or '')
                if text:
                    card_lines.append(f"- Deck field \"{f.get('field_name')}\": {text}")
            for grp in c.get('archetype_entries') or []:
                src = grp.get('source_name') or 'Unnamed source'
                for f in grp.get('fields') or []:
                    text = _html_to_text(f.get('content') or '')
                    if text:
                        card_lines.append(f"- {src} — \"{f.get('field_name')}\": {text}")
            if card_lines:
                lines.append(f"### {c.get('name') or 'Card'}")
                lines.extend(card_lines)
                lines.append('')
    if not lines:
        return []
    return [
        '## Reference material for the drawn cards',
        '',
        ('_From the user\'s own library (deck card fields and authored '
         'source notes). Factual lookups only — not interpretations of '
         'this reading._'),
        '',
        *lines,
    ]


def build_entry_markdown(db, entry: dict, include_reference: bool = False) -> str:
    lines: list[str] = []
    title = entry.get('title') or 'Untitled Entry'
    lines.append(f"# Journal Entry — {title}")
    lines.append('')

    when = entry.get('reading_datetime') or entry.get('created_at')
    if when:
        lines.append(f"**Date of reading:** {_pretty_datetime(when)}")
    if entry.get('location_name'):
        lines.append(f"**Location:** {entry['location_name']}")
    querents = [q.get('name') for q in (entry.get('querents') or []) if q.get('name')]
    if not querents and entry.get('querent_name'):
        querents = [entry['querent_name']]
    if querents:
        lines.append(f"**Querent:** {', '.join(querents)}")
    if entry.get('reader_name'):
        lines.append(f"**Reader:** {entry['reader_name']}")
    tags = [t.get('name') for t in (entry.get('tags') or []) if t.get('name')]
    if tags:
        lines.append(f"**Tags:** {', '.join(tags)}")
    lines.append('')

    for i, rd in enumerate(entry.get('readings') or []):
        spread = rd.get('spread')
        spread_name = rd.get('spread_name') or (spread or {}).get('name')
        heading = f"## Reading {i + 1}"
        if spread_name:
            heading += f": {spread_name}"
        if rd.get('deck_name'):
            heading += f" — {rd['deck_name']} deck"
        if rd.get('querent_name'):
            heading += f" (for {rd['querent_name']})"
        lines.append(heading)
        lines.append('')

        desc = _html_to_text((spread or {}).get('description') or '')
        if desc:
            lines.append(f"_{desc}_")
            lines.append('')

        cards = rd.get('cards_used') or []
        positions = (spread or {}).get('positions') or []
        if positions:
            lines.append('| # | Position | Card |')
            lines.append('|---|----------|------|')
            for idx, pos in enumerate(positions):
                card = next(
                    (c for c in cards if c.get('position_index') == idx),
                    None,
                )
                key = pos.get('key') or str(idx + 1)
                label = pos.get('label') or f"Position {idx + 1}"
                lines.append(
                    f"| {key} | {label} | "
                    f"{_card_display(card) if card else '—'} |"
                )
            extras = rd.get('extra_cards') or []
            if extras:
                lines.append('')
                lines.append('**Extra cards:**')
                for c in extras:
                    line = f"- {_card_display(c)}"
                    if c.get('clarifies_label'):
                        line += f" — clarifies position {c['clarifies_label']}"
                    lines.append(line)
        elif cards:
            for c in cards:
                lines.append(f"- {_card_display(c)}")
        lines.append('')

        # Compact correspondences for the cards that have them
        corr_lines = []
        seen_ids = set()
        for c in cards:
            cid = c.get('card_id')
            if not cid or cid in seen_ids:
                continue
            seen_ids.add(cid)
            summary = _correspondence_line(db, c)
            if summary:
                corr_lines.append(f"- **{c.get('name')}**: {summary}")
        if corr_lines:
            lines.append('**Card correspondences:**')
            lines.extend(corr_lines)
            lines.append('')

        reading_notes = _html_to_text(rd.get('notes') or '')
        if reading_notes:
            lines.append('**Notes for this reading:**')
            lines.append('')
            lines.append(reading_notes)
            lines.append('')

    if include_reference:
        lines.extend(_reference_sections(entry))

    notes = _html_to_text(entry.get('content_html') or '')
    if notes:
        lines.append('## My Notes')
        lines.append('')
        lines.append(notes)
        lines.append('')

    follow_ups = entry.get('follow_up_notes') or []
    if follow_ups:
        lines.append('## Follow-up Notes')
        lines.append('')
        for n in follow_ups:
            date = _pretty_datetime(n.get('created_at') or '')
            text = _html_to_text(n.get('content') or '')
            lines.append(f"- ({date}) {text}" if date else f"- {text}")
        lines.append('')

    return '\n'.join(lines).strip() + '\n'


@llm_export_bp.route('/api/entries/<int:entry_id>/llm-export')
def llm_export(entry_id):
    """Return the entry as LLM-ready markdown: {"markdown": "..."}"""
    db = current_app.config['DB']
    entry = _hydrate_entry_for_pdf(db, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    include_reference = request.args.get('include_reference') == '1'
    return jsonify({'markdown': build_entry_markdown(
        db, entry, include_reference=include_reference)})


# ── Bulk export (the Analyst) ────────────────────────────────────────

MAX_BULK_ENTRIES = 300


def _aggregate_stats(entries: list) -> str:
    """Deterministic counts the model should trust over its own tally.
    Cards are counted by archetype where known, so the same card across
    different decks aggregates together."""
    card_counts = Counter()
    spread_counts = Counter()
    tag_counts = Counter()
    querent_counts = Counter()
    reversed_count = 0
    total_cards = 0
    dates = []
    for e in entries:
        when = e.get('reading_datetime') or e.get('created_at')
        if when:
            dates.append(str(when)[:10])
        for t in (e.get('tags') or []):
            if t.get('name'):
                tag_counts[t['name']] += 1
        for q in (e.get('querents') or []):
            if q.get('name'):
                querent_counts[q['name']] += 1
        for rd in (e.get('readings') or []):
            spread_name = rd.get('spread_name') or (rd.get('spread') or {}).get('name')
            if spread_name:
                spread_counts[spread_name] += 1
            for c in (rd.get('cards_used') or []):
                name = c.get('archetype') or c.get('name')
                if not name:
                    continue
                card_counts[name] += 1
                total_cards += 1
                if c.get('reversed'):
                    reversed_count += 1

    def fmt(counter: Counter, n: int) -> str:
        return ', '.join(f"{name} ×{count}" for name, count in counter.most_common(n))

    lines = [
        '## Statistics (computed by the app — trust these over manual counting)',
        '',
        f"- Entries: {len(entries)}",
    ]
    if dates:
        lines.append(f"- Date range: {min(dates)} to {max(dates)}")
    lines.append(f"- Cards drawn: {total_cards} ({reversed_count} reversed)")
    if card_counts:
        lines.append(f"- Most frequent cards (by archetype where known): {fmt(card_counts, 20)}")
    if spread_counts:
        lines.append(f"- Spreads used: {fmt(spread_counts, 10)}")
    if querent_counts:
        lines.append(f"- Querents: {fmt(querent_counts, 10)}")
    if tag_counts:
        lines.append(f"- Tags: {fmt(tag_counts, 15)}")
    return '\n'.join(lines)


@llm_export_bp.route('/api/entries/llm-export', methods=['POST'])
def llm_export_bulk():
    """Bundle several entries into one LLM-ready document.

    Body: {"ids": [1, 2, ...]}. Entries are ordered chronologically
    (oldest first) so trends read forward in time, prefixed with
    app-computed statistics.
    """
    db = current_app.config['DB']
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids or not isinstance(ids, list):
        return jsonify({'error': 'ids is required'}), 400
    entries = []
    for entry_id in ids[:MAX_BULK_ENTRIES]:
        entry = _hydrate_entry_for_pdf(db, int(entry_id))
        if entry:
            entries.append(entry)
    if not entries:
        return jsonify({'error': 'No matching entries found'}), 404
    entries.sort(key=lambda e: str(e.get('reading_datetime') or e.get('created_at') or ''))

    parts = [
        f"# Journal excerpt — {len(entries)} entries",
        '',
        _aggregate_stats(entries),
        '',
        '---',
        '',
    ]
    for e in entries:
        parts.append(build_entry_markdown(db, e))
        parts.append('---')
        parts.append('')
    markdown = '\n'.join(parts)
    return jsonify({
        'markdown': markdown,
        'entry_count': len(entries),
        'char_count': len(markdown),
    })
