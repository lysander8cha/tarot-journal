"""
Journal entry PDF export. Phase 1: header, spread image (HTML/CSS
positioned), position key, journal notes, follow-up notes.

The pipeline:
  1. Hydrate the entry the same way GET /api/entries/<id> does.
  2. Build a render-context dict for Jinja2 — flattens DB rows and
     pre-resolves card image absolute paths so WeasyPrint can pull
     them off disk.
  3. Render the print template + CSS.
  4. WeasyPrint converts the HTML to a PDF and we stream it back.

WeasyPrint's HTML/CSS support handles the rich-text content
(TipTap stores HTML already) and the absolute-positioned spread
layout without us reconstructing anything in low-level drawing
primitives.
"""

# PEP 604 union syntax (str | None) for type annotations on this
# Python 3.9 venv.
from __future__ import annotations

import json
import logging
import re
from io import BytesIO
from pathlib import Path

from flask import Blueprint, current_app, request, send_file, jsonify

from backend.utils import row_to_dict
from backend.routes.entries import _enrich_cards_with_ids, _parse_cards_used
from backend.services.richtext import convert_content_to_html
from database.correspondences import CORRESPONDENCE_FIELDS
from database.entries import parse_querent_ids


# Custom fields stored before the card_custom_fields table existed
# include I Ching language fields which the CardViewModal hides from
# the Custom Fields section because they're rendered elsewhere. Mirror
# that exclusion here so the PDF doesn't duplicate them.
_HIDDEN_CUSTOM_FIELD_KEYS = {'traditional_chinese', 'simplified_chinese'}


# Display labels — mirrors frontend/src/types/index.ts:CORRESPONDENCE_FIELD_LABELS
# so the PDF rows read the same as the in-app Reading Breakdown.
_CORRESPONDENCE_LABELS = {
    'element': 'Element',
    'planet': 'Planet',
    'zodiac_sign': 'Zodiac Sign',
    'decan': 'Decan',
    'hebrew_letter': 'Kabbalah',
    'numerology': 'Numerology',
    'rune': 'Rune',
    'i_ching_hexagram': 'I Ching Hexagram',
    'chakra': 'Chakra',
    'modality': 'Modality',
    'astrological_house': 'Astrological House',
}

_TAROT_MINOR_OF_RE = re.compile(r'^(.+?) of (.+)$')


def _has_content(value) -> bool:
    """The CardViewModal / Anki export use this same rule — a field
    counts as non-empty when its stripped text content (after HTML
    tags are removed) has at least one character. Skips empty TipTap
    docs like '<p></p>'."""
    if value is None:
        return False
    text = re.sub(r'<[^>]*>', '', str(value)).strip()
    return len(text) > 0


def _merge_custom_fields(db, card_id: int, card_row: dict | None) -> list:
    """Return a list of {field_name, field_value} for a card, merged
    from the legacy `cards.custom_fields` JSON blob + the newer
    `card_custom_fields` table. Table values win on case-insensitive
    name collision (matching the dedupe rule already used by the
    CardViewModal / Anki export). Excludes empty values and the
    I Ching language keys that surface elsewhere in the UI."""
    legacy: dict[str, str] = {}
    raw = card_row.get('custom_fields') if card_row else None
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                legacy = {
                    str(k): ('' if v is None else str(v))
                    for k, v in parsed.items()
                }
        except (TypeError, ValueError):
            pass

    cursor = db.conn.cursor()
    cursor.execute(
        'SELECT field_name, field_value FROM card_custom_fields '
        'WHERE card_id = ? ORDER BY COALESCE(field_order, 0), id',
        (card_id,),
    )
    table_fields = [
        {'field_name': r['field_name'], 'field_value': r['field_value'] or ''}
        for r in cursor.fetchall()
    ]
    table_names_lower = {f['field_name'].lower() for f in table_fields}

    # Legacy entries that aren't shadowed by a table row come first,
    # in the order Python's dict preserved (i.e. insertion order from
    # the JSON load).
    merged = []
    for name, value in legacy.items():
        if name.lower() in _HIDDEN_CUSTOM_FIELD_KEYS:
            continue
        if name.lower() in table_names_lower:
            continue
        if _has_content(value):
            merged.append({'field_name': name, 'field_value': value})
    for f in table_fields:
        if f['field_name'].lower() in _HIDDEN_CUSTOM_FIELD_KEYS:
            continue
        if _has_content(f['field_value']):
            merged.append(f)
    return merged


def _archetype_entries(db, archetype_id: int | None, cartomancy_type: str | None) -> list:
    """Source entries for the card's archetype, grouped by source for
    display. Returns a list of dicts:
        {source_id, source_name, fields: [{field_id, field_name, content}]}
    Empty list when the card has no archetype, or no entries authored."""
    if not archetype_id:
        return []
    rows = db.get_source_entries_for_archetype(archetype_id, cartomancy_type)
    grouped: dict[int, dict] = {}
    for r in rows:
        if not _has_content(r.get('content')):
            continue
        bucket = grouped.get(r['source_id'])
        if bucket is None:
            bucket = {
                'source_id': r['source_id'],
                'source_name': r['source_name'],
                'fields': [],
            }
            grouped[r['source_id']] = bucket
        bucket['fields'].append({
            'field_id': r['field_id'],
            'field_name': r['field_name'],
            'content': r['content'],
        })
    return list(grouped.values())


logger = logging.getLogger(__name__)

pdf_export_bp = Blueprint('pdf_export', __name__)

# Resolved at import time so the Jinja2 + CSS files travel with the
# backend package.
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'pdf_templates'


def _file_uri(path: str, cache=None) -> str | None:
    """Convert a card's stored image_path (possibly relative to the
    project root) into a file:// URI WeasyPrint can embed.

    When a thumbnail cache is provided, prefer the cached PREVIEW
    rendition (~500x750) over the original. Card scans are often
    several MB each; for an A4 print the preview is plenty crisp
    and keeps the resulting PDF small enough to share.
    """
    if not path:
        return None
    if cache is not None:
        try:
            preview_path = cache.get_thumbnail_path(path, size=cache.PREVIEW_SIZE)
        except Exception:
            preview_path = None
        if preview_path:
            p = Path(preview_path)
            if p.exists():
                return p.as_uri()
    # Fallback: stream the original.
    p = Path(path)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parent.parent.parent / p).resolve()
    if not p.exists():
        return None
    return p.as_uri()


def _safe_filename(stem: str) -> str:
    """Sanitize an entry title for use in the download filename.
    Drops anything other than alphanumerics, dash, and underscore."""
    cleaned = re.sub(r'[^A-Za-z0-9_-]+', '_', stem).strip('_')
    return cleaned or 'journal_entry'


def _hydrate_entry_for_pdf(db, entry_id: int, cache=None) -> dict | None:
    """Return the entry as a dict ready for the Jinja2 template, or
    None if it doesn't exist. Card images are resolved to absolute
    file:// URIs so WeasyPrint can load them directly (preferring
    the cached preview rendition). Spreads are fetched once each,
    keyed by id, and attached to their reading."""
    row = db.get_entry(entry_id)
    if not row:
        return None
    entry = row_to_dict(row)
    entry['content_html'] = entry.get('content') or ''

    readings_rows = db.get_entry_readings(entry_id)
    spread_cache: dict[int, dict] = {}
    readings: list[dict] = []
    for r in readings_rows:
        rd = row_to_dict(r)
        # Same enrichment the GET /api/entries/<id> route uses —
        # resolves card_id for legacy entries that only stored
        # (deck_id, name) and surfaces archetype/rank/suit/cartomancy_type
        # so the breakdown can categorise cards without a per-card fetch.
        cards = _enrich_cards_with_ids(db, _parse_cards_used(rd.get('cards_used')))
        hydrated_cards = []
        for c in cards:
            card_id = c.get('card_id')
            card_row = db.get_card(card_id) if card_id else None
            card_db = dict(card_row) if card_row else {}
            cartomancy_type = c.get('cartomancy_type') or rd.get('cartomancy_type')
            archetype_name = c.get('archetype') or (card_db.get('archetype') if card_db else None)
            archetype_id = None
            if archetype_name and cartomancy_type:
                arch_row = db.get_archetype_by_name(archetype_name, cartomancy_type)
                if arch_row:
                    archetype_id = arch_row['id']
            hydrated_cards.append({
                'name': c.get('current_name') or c.get('name') or (card_db.get('name') if card_db else ''),
                'reversed': bool(c.get('reversed')),
                'position_index': c.get('position_index'),
                'card_id': card_id,
                'image_uri': _file_uri(card_db.get('image_path'), cache) if card_db else None,
                # Prefer enrichment's metadata (it already pulled
                # archetype/rank/suit/cartomancy_type); fall back to
                # the cards row when enrichment didn't have a hit.
                'archetype': archetype_name,
                'archetype_id': archetype_id,
                'rank': c.get('rank') or (card_db.get('rank') if card_db else None),
                'suit': c.get('suit') or (card_db.get('suit') if card_db else None),
                'cartomancy_type': cartomancy_type,
                'deck_name': rd.get('deck_name'),
                # Authored custom-field values + archetype reference
                # entries, pre-filtered by _has_content. Filtering
                # by the user's chosen field names happens later
                # when the card-detail section is assembled.
                'custom_fields': _merge_custom_fields(db, card_id, card_db) if card_id else [],
                'archetype_entries': _archetype_entries(db, archetype_id, cartomancy_type),
                'clarifies': c.get('clarifies'),
            })
        rd['cards_used'] = hydrated_cards

        # Spread definition for the visual layout.
        spread = None
        if rd.get('spread_id'):
            sid = rd['spread_id']
            if sid not in spread_cache:
                sp_row = db.get_spread(sid)
                if sp_row:
                    sp = row_to_dict(sp_row)
                    positions = sp.get('positions')
                    if isinstance(positions, str):
                        try:
                            positions = json.loads(positions)
                        except (TypeError, ValueError):
                            positions = []
                    sp['positions'] = positions or []
                    # The spread's description/instructions as HTML
                    # (older spreads stored plain text or TipTap XML).
                    sp['description_html'] = (
                        convert_content_to_html(sp.get('description'))
                        if (sp.get('description') or '').strip() else ''
                    )
                    spread_cache[sid] = sp
            spread = spread_cache.get(sid)
        rd['spread'] = spread
        rd['notes_html'] = (
            convert_content_to_html(rd.get('notes'))
            if (rd.get('notes') or '').strip() else ''
        )

        # Extra cards (clarifiers / additional pulls beyond the
        # spread's positions), grouped one row per clarified card —
        # matching the journal's on-screen display. Identified by
        # stored position_index since saved arrays are compacted.
        extra_groups = []
        if spread and spread.get('positions'):
            positions = spread['positions']
            poscount = len(positions)
            by_target = {}
            unattached = []
            for c in hydrated_cards:
                pi = c.get('position_index')
                if pi is None or pi < poscount:
                    continue
                ci = c.get('clarifies')
                if ci is not None and 0 <= ci < poscount:
                    by_target.setdefault(ci, []).append(c)
                else:
                    unattached.append(c)
            for ci in sorted(by_target):
                pos = positions[ci]
                pos_label = (pos.get('label') or pos.get('key')
                             or f'position {ci + 1}')
                clarified = next(
                    (c for c in hydrated_cards
                     if c.get('position_index') == ci), None)
                if clarified and clarified.get('name'):
                    title = f"↳ Clarifying {clarified['name']} ({pos_label})"
                else:
                    title = f'↳ Clarifying {pos_label}'
                extra_groups.append({'title': title, 'cards': by_target[ci]})
            if unattached:
                extra_groups.append(
                    {'title': 'Extra cards', 'cards': unattached})
        rd['extra_groups'] = extra_groups
        readings.append(rd)
    entry['readings'] = readings

    tags = db.get_entry_tags(entry_id)
    entry['tags'] = [row_to_dict(t) for t in tags]

    follow_ups = db.get_follow_up_notes(entry_id)
    entry['follow_up_notes'] = [row_to_dict(n) for n in follow_ups]

    querents = db.get_entry_querents(entry_id)
    entry['querents'] = [row_to_dict(q) for q in querents]
    names = {q['id']: q['name'] for q in entry['querents']}
    for rd in entry['readings']:
        rd['querent_names'] = [names[i] for i in parse_querent_ids(rd.get('querent_ids'))
                               if i in names]
    if entry.get('querent_id'):
        q = db.get_profile(entry['querent_id'])
        entry['querent_name'] = q['name'] if q else None
    if entry.get('reader_id'):
        rp = db.get_profile(entry['reader_id'])
        entry['reader_name'] = rp['name'] if rp else None

    return entry


# === Astrological event chart (mirrors the /chart entry route) ===

_SUMMARY_BODIES = (
    'sun', 'moon', 'mercury', 'venus', 'mars',
    'jupiter', 'saturn', 'uranus', 'neptune', 'pluto',
    'chiron', 'mean_node', 'mean_south_node',
)

_BODY_LABELS = {
    'sun': 'Sun', 'moon': 'Moon', 'mercury': 'Mercury', 'venus': 'Venus',
    'mars': 'Mars', 'jupiter': 'Jupiter', 'saturn': 'Saturn',
    'uranus': 'Uranus', 'neptune': 'Neptune', 'pluto': 'Pluto',
    'chiron': 'Chiron',
    'mean_node': 'North Node', 'mean_south_node': 'South Node',
}

_SIGN_FULL_NAMES = {
    'Ari': 'Aries', 'Tau': 'Taurus', 'Gem': 'Gemini', 'Can': 'Cancer',
    'Leo': 'Leo', 'Vir': 'Virgo', 'Lib': 'Libra', 'Sco': 'Scorpio',
    'Sag': 'Sagittarius', 'Cap': 'Capricorn', 'Aqu': 'Aquarius', 'Pis': 'Pisces',
}


def _split_reading_datetime(dt: str) -> tuple[str, str]:
    """Same parse the entries route does — date/time can be ISO
    with T, space-separated, or just a bare date (assume noon)."""
    if 'T' in dt:
        return tuple(dt.split('T', 1))  # type: ignore[return-value]
    if ' ' in dt:
        return tuple(dt.split(' ', 1))  # type: ignore[return-value]
    return dt, '12:00:00'


def _entry_chart_ready(entry: dict) -> bool:
    """Whether the entry has enough data to generate an event chart.
    Matches the gating the entries/<id>/chart route applies."""
    return bool(
        entry.get('reading_datetime')
        and entry.get('location_lat') is not None
        and entry.get('location_lon') is not None
    )


def _resolve_event_chart(db, entry: dict) -> dict | None:
    """Return {svg, chart_data, timezone, house_system, cached,
    generated_at?} for the entry's event chart, hitting the chart_cache when it can and
    generating fresh otherwise. None if the entry doesn't have
    enough data, or if kerykeion errored out — the export should
    keep rendering the rest of the PDF rather than 500'ing. Also
    backs GET /api/entries/<id>/chart."""
    if not _entry_chart_ready(entry):
        return None

    import astrology

    date_iso, time_iso = _split_reading_datetime(entry['reading_datetime'])
    house_system = db.get_house_system()
    place_label = entry.get('location_name') or ''
    chart_label = 'Reading Chart'

    input_hash = astrology.compute_input_hash(
        date_iso, time_iso,
        entry['location_lat'], entry['location_lon'],
        house_system,
        place_label=place_label,
        chart_label=chart_label,
    )

    cached = db.get_cached_chart('entry', entry['id'])
    if cached and cached.get('input_hash') == input_hash:
        return {
            'svg': cached['chart_svg'],
            'chart_data': cached['chart_data'],
            'timezone': (cached['chart_data'] or {}).get('timezone'),
            'house_system': cached['house_system'],
            'generated_at': cached['updated_at'],
            'cached': True,
        }

    try:
        result = astrology.generate_chart(
            name=entry.get('title') or 'Reading',
            date_iso=date_iso, time_iso=time_iso,
            lat=entry['location_lat'], lon=entry['location_lon'],
            house_system=house_system,
            place_label=place_label,
            chart_label=chart_label,
        )
    except Exception as e:
        logger.warning(
            'PDF export: chart generation failed for entry %s: %s',
            entry.get('id'), e,
        )
        return None

    data_to_store = dict(result['data'])
    data_to_store['timezone'] = result['timezone']
    try:
        db.save_cached_chart(
            'entry', entry['id'], house_system, input_hash,
            result['svg'], data_to_store,
        )
    except Exception as e:
        logger.debug('PDF export: chart cache write failed: %s', e)

    return {
        'svg': result['svg'],
        'chart_data': data_to_store,
        'timezone': result['timezone'],
        'house_system': house_system,
        'cached': False,
    }


def _house_label(raw) -> str:
    """Kerykeion publishes house names like 'Ninth_House' — clean
    for display so the table reads 'Ninth' instead of 'Ninth_House'."""
    if not isinstance(raw, str):
        return ''
    return raw.replace('_', ' ').replace('House', '').strip()


def _planetary_positions(chart_data: dict | None) -> list:
    """Pull the standard ten planets + Chiron + the lunar nodes out
    of the kerykeion dump so the template can render a small table.
    Bodies that aren't present in chart_data are silently skipped."""
    if not chart_data:
        return []
    rows = []
    for key in _SUMMARY_BODIES:
        raw = chart_data.get(key)
        if not isinstance(raw, dict):
            continue
        sign = _SIGN_FULL_NAMES.get(raw.get('sign') or '', raw.get('sign') or '')
        try:
            position = float(raw.get('position') or 0)
        except (TypeError, ValueError):
            position = 0.0
        rows.append({
            'label': _BODY_LABELS.get(key, key),
            'sign': sign,
            'position': position,
            'house': _house_label(raw.get('house')),
            'retrograde': bool(raw.get('retrograde')),
        })
    return rows


_CSS_VAR_DECL_RE = re.compile(
    r'(--[A-Za-z0-9_-]+)\s*:\s*([^;}]+?)\s*[;}]'
)
_CSS_VAR_USE_RE = re.compile(
    r'var\(\s*(--[A-Za-z0-9_-]+)(?:\s*,\s*([^)]+))?\s*\)'
)


def _resolve_css_variables(svg: str) -> str:
    """Inline `var(--…)` references in the SVG using the values
    declared in its embedded `:root { --var: value; }` block.
    Necessary because CairoSVG (and consequently WeasyPrint) doesn't
    resolve CSS custom properties, so kerykeion's chart wheel
    otherwise renders as a solid black blob — every fill/stroke that
    references a var ends up at the initial value.

    Unknown variables fall through to the var() fallback if one was
    given, then to a transparent fill so the chart doesn't collapse
    to black again. Handles nested references via a few passes."""
    declarations: dict[str, str] = {}
    for m in _CSS_VAR_DECL_RE.finditer(svg):
        name = m.group(1).strip()
        value = m.group(2).strip()
        if name not in declarations:  # first declaration wins
            declarations[name] = value

    def replace(match: re.Match) -> str:
        name = match.group(1).strip()
        fallback = (match.group(2) or '').strip()
        return declarations.get(name) or fallback or 'transparent'

    out = svg
    for _ in range(5):  # bounded fixed-point loop
        new = _CSS_VAR_USE_RE.sub(replace, out)
        if new == out:
            break
        out = new
    return out


def _render_chart_png_data_uri(svg: str) -> str | None:
    """Rasterize kerykeion's chart SVG to a PNG data URI so the PDF
    embed renders correctly. WeasyPrint's inline-SVG path mis-renders
    the chart wheel (solid black) — kerykeion's SVG uses CSS custom
    properties (`var(--…)`) which neither WeasyPrint nor CairoSVG
    resolves. We first inline those variables, then rasterize at
    print-resolution and embed the PNG as a data URI.

    Returns None if rasterization fails — the chart section then
    falls back to omitting the wheel but still showing the
    planetary table.
    """
    try:
        import cairosvg
    except ImportError:
        logger.debug('cairosvg not installed — skipping chart wheel render')
        return None
    resolved_svg = _resolve_css_variables(svg)
    try:
        # output_width is in CSS pixels; 1500 gives a crisp print
        # at the ~170mm of A4 printable area we have available.
        png_bytes = cairosvg.svg2png(
            bytestring=resolved_svg.encode('utf-8'),
            output_width=1500,
        )
    except Exception as e:
        logger.warning('chart SVG → PNG conversion failed: %s', e)
        return None
    import base64
    encoded = base64.b64encode(png_bytes).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def _select_readings(entry: dict, ids: list[int] | None) -> dict:
    """If the request specified a readings subset, filter the entry's
    readings list to just those ids. Mutates and returns the entry."""
    if not ids:
        return entry
    keep = set(int(i) for i in ids)
    entry['readings'] = [r for r in entry['readings'] if int(r['id']) in keep]
    return entry


# === Correspondence breakdown (mirror of useEntryBreakdown) ===

def _card_categories(card: dict) -> tuple[str | None, str | None]:
    """Mirror of frontend's getCardCategories — derives (rank, suit)
    used to populate the Suit/Rank tally rows. Tarot minors parse out
    of the archetype name ("Knight of Wands" → Knight/Wands); majors
    map to suit "Major Arcana". Other types use rank/suit directly."""
    ctype = card.get('cartomancy_type')
    if ctype == 'Tarot':
        archetype = card.get('archetype')
        if archetype:
            m = _TAROT_MINOR_OF_RE.match(archetype)
            if m:
                return m.group(1), m.group(2)
            return None, 'Major Arcana'
    return card.get('rank') or None, card.get('suit') or None


# Latin/French suit equivalents — mirror of frontend utils/suitPairing.ts.
_SUIT_PAIRS = {
    'Cups / Hearts': ['cups', 'hearts', 'copas', 'coupes', 'chalices', 'cœurs', 'coeurs'],
    'Swords / Spades': ['swords', 'spades', 'espadas', 'épées', 'epees', 'piques'],
    'Pentacles / Diamonds': ['pentacles', 'diamonds', 'oros', 'coins', 'disks', 'discs', 'deniers', 'carreaux'],
    'Wands / Clubs': ['wands', 'clubs', 'bastos', 'batons', 'bâtons', 'staves', 'trèfles', 'trefles'],
}
_SUIT_PAIR_LOOKUP = {
    name: label for label, names in _SUIT_PAIRS.items() for name in names
}


def _paired_suit_label(suit: str) -> str:
    """The merged Latin/French label for a suit, or the suit itself
    when unpaired (Major Arcana, oracle groupings…)."""
    return _SUIT_PAIR_LOOKUP.get(suit.strip().lower(), suit)


def _tally_to_columns(tally: dict) -> list:
    """Sort the (value → count) tally by count desc then alphabetical
    tiebreak, matching the in-app Reading Breakdown ordering."""
    return [
        {'value': v, 'count': c}
        for v, c in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _build_breakdown_tab(
    label: str,
    cards: list[dict],
    correspondences_by_id: dict,
    enabled_fields: set,
    pair_suits: bool = False,
) -> dict:
    """Build a single tab (one reading or the aggregate) given the
    cards and the resolved correspondences keyed by card_id.

    enabled_fields is a set of row keys ('suit', 'rank', or any
    correspondence field name) the user opted into; rows not in
    the set are skipped entirely.
    """
    suit_tally: dict[str, int] = {}
    rank_tally: dict[str, int] = {}
    # field_name → {value: count}
    corr_tallies: dict[str, dict[str, int]] = {}

    for c in cards:
        rank, suit = _card_categories(c)
        if suit and 'suit' in enabled_fields:
            key = _paired_suit_label(suit) if pair_suits else suit
            suit_tally[key] = suit_tally.get(key, 0) + 1
        if rank and 'rank' in enabled_fields:
            rank_tally[rank] = rank_tally.get(rank, 0) + 1

        for corr in correspondences_by_id.get(c.get('card_id'), []):
            field = corr.get('field_name')
            if field not in enabled_fields:
                continue
            values = corr.get('values') or []
            if not values:
                continue
            bucket = corr_tallies.setdefault(field, {})
            for v in values:
                bucket[v] = bucket.get(v, 0) + 1

    rows = []
    if suit_tally:
        rows.append({'key': 'suit', 'label': 'Suit',
                     'columns': _tally_to_columns(suit_tally)})
    if rank_tally:
        rows.append({'key': 'rank', 'label': 'Rank',
                     'columns': _tally_to_columns(rank_tally)})
    # Correspondence rows follow CORRESPONDENCE_FIELDS' canonical order
    # so the table doesn't reshuffle with different cards.
    for field in CORRESPONDENCE_FIELDS:
        bucket = corr_tallies.get(field)
        if not bucket:
            continue
        rows.append({
            'key': field,
            'label': _CORRESPONDENCE_LABELS.get(field, field),
            'columns': _tally_to_columns(bucket),
        })

    return {'label': label, 'card_count': len(cards), 'rows': rows}


def _build_correspondence_breakdown(db, entry: dict, enabled_fields: set,
                                    pair_suits: bool = False) -> list:
    """Returns a list of tab dicts: one per reading + an aggregate
    when there are multiple readings. Each tab has a label,
    card_count, and rows (each row = {key, label, columns}).

    Empty list if no fields are enabled or no cards have card_ids
    (the breakdown is meaningless without resolved cards)."""
    if not enabled_fields or not entry.get('readings'):
        return []

    # Fetch each unique card's correspondences once.
    unique_ids = {
        c['card_id']
        for r in entry['readings']
        for c in (r.get('cards_used') or [])
        if c.get('card_id')
    }
    corr_by_id: dict[int, list] = {}
    for cid in unique_ids:
        try:
            corr_by_id[cid] = db.get_card_correspondences(cid) or []
        except Exception as e:
            logger.debug('correspondence lookup failed for card %s: %s', cid, e)
            corr_by_id[cid] = []

    tabs = []
    for r in entry['readings']:
        cards = [c for c in (r.get('cards_used') or []) if c.get('card_id')]
        if not cards:
            continue
        tabs.append(_build_breakdown_tab(
            r.get('spread_name') or 'Reading',
            cards,
            corr_by_id,
            enabled_fields,
            pair_suits=pair_suits,
        ))

    if len(tabs) > 1:
        all_cards = [
            c for r in entry['readings']
            for c in (r.get('cards_used') or [])
            if c.get('card_id')
        ]
        tabs.append(_build_breakdown_tab(
            'All Readings', all_cards, corr_by_id, enabled_fields,
            pair_suits=pair_suits,
        ))
    # Strip tabs that ended up with no rows (all fields the user
    # selected happened to have zero data for that reading).
    return [t for t in tabs if t['rows']]


# === Card detail section (custom fields + archetype reference info) ===

def _available_field_options(entry: dict) -> dict:
    """Compute the union of custom field names + archetype source
    fields across every card in the entry's currently-selected
    readings. Returns the shape consumed by the modal:

        {
          "custom_fields": ["Keywords", "Description", ...],
          "archetype_fields": [
            {"field_id": int, "source_name": str, "field_name": str},
            ...
          ],
        }
    """
    custom_names: list[str] = []
    seen_custom = set()
    archetype_fields: list[dict] = []
    seen_archetype_field_ids = set()

    for reading in entry.get('readings', []):
        for card in (reading.get('cards_used') or []):
            for f in card.get('custom_fields') or []:
                name = f.get('field_name')
                if not name:
                    continue
                key = name.lower()
                if key in seen_custom:
                    continue
                seen_custom.add(key)
                custom_names.append(name)
            for grp in card.get('archetype_entries') or []:
                for f in grp.get('fields') or []:
                    fid = f.get('field_id')
                    if not fid or fid in seen_archetype_field_ids:
                        continue
                    seen_archetype_field_ids.add(fid)
                    archetype_fields.append({
                        'field_id': fid,
                        'source_id': grp.get('source_id'),
                        'source_name': grp.get('source_name'),
                        'field_name': f.get('field_name'),
                    })

    archetype_fields.sort(key=lambda f: (
        (f.get('source_name') or '').lower(),
        (f.get('field_name') or '').lower(),
    ))
    return {
        'custom_fields': custom_names,
        'archetype_fields': archetype_fields,
    }


def _build_card_details(
    entry: dict,
    include_custom: bool,
    custom_names: set | None,
    include_archetype: bool,
    archetype_field_ids: set | None,
) -> list:
    """Assemble the Card Detail Section for the template.

    Returns a list of {reading_label, cards: [...]} groups. Each
    card entry has the name/deck/image plus filtered custom_fields
    and filtered archetype_entries. Cards whose card_id never
    resolved are skipped (no archetype lookup, no custom-fields
    table row — nothing to show).

    Empty list when nothing was opted into."""
    if not include_custom and not include_archetype:
        return []

    out: list[dict] = []
    for reading in entry.get('readings', []):
        cards_block = []
        for card in (reading.get('cards_used') or []):
            if not card.get('card_id'):
                continue

            custom = []
            if include_custom:
                for f in card.get('custom_fields') or []:
                    name = f.get('field_name')
                    if not name:
                        continue
                    if custom_names is not None and name.lower() not in custom_names:
                        continue
                    custom.append(f)

            archetype = []
            if include_archetype:
                for grp in card.get('archetype_entries') or []:
                    if archetype_field_ids is not None:
                        kept_fields = [
                            f for f in (grp.get('fields') or [])
                            if f.get('field_id') in archetype_field_ids
                        ]
                    else:
                        kept_fields = grp.get('fields') or []
                    if not kept_fields:
                        continue
                    archetype.append({
                        'source_id': grp.get('source_id'),
                        'source_name': grp.get('source_name'),
                        'fields': kept_fields,
                    })

            if not custom and not archetype:
                continue

            cards_block.append({
                'name': card.get('name'),
                'deck_name': card.get('deck_name'),
                'image_uri': card.get('image_uri'),
                'reversed': card.get('reversed'),
                'archetype': card.get('archetype'),
                'custom_fields': custom,
                'archetype_entries': archetype,
            })
        if cards_block:
            out.append({
                'reading_label': reading.get('spread_name') or 'Reading',
                'cards': cards_block,
            })
    return out


@pdf_export_bp.route('/api/entries/<int:entry_id>/export-pdf', methods=['POST'])
def export_pdf(entry_id):
    """Generate a PDF for a journal entry. Phase 1 honors only the
    readings selection from the request body — the other toggles
    listed in PLANNING_PDF_EXPORT.md are placeholders for later
    phases. Returns the PDF as an attachment download."""
    # Local imports so a missing weasyprint install fails on POST
    # (with a clear 500), not on app startup.
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from weasyprint import HTML, CSS

    db = current_app.config['DB']
    cache = current_app.config.get('THUMB_CACHE')
    body = request.get_json(silent=True) or {}

    entry = _hydrate_entry_for_pdf(db, entry_id, cache=cache)
    if entry is None:
        return jsonify({'error': 'Entry not found'}), 404

    _select_readings(entry, body.get('readings'))
    if not entry['readings']:
        # The doc says the modal requires at least one reading; this
        # is a backstop for the API path.
        return jsonify({'error': 'At least one reading must be selected'}), 400

    # Correspondence breakdown (phase 2). The request body honours the
    # planning doc's shape: include_correspondences master toggle +
    # correspondence_types list of row keys. Row keys are
    # CORRESPONDENCE_FIELDS plus 'suit' and 'rank' to match the
    # in-app Reading Breakdown filter checklist.
    breakdown_tabs = []
    if body.get('include_correspondences'):
        requested = body.get('correspondence_types')
        if requested is None:
            # No explicit list: default to every recognised row key.
            enabled = set(CORRESPONDENCE_FIELDS) | {'suit', 'rank'}
        else:
            enabled = {str(k) for k in requested}
        breakdown_tabs = _build_correspondence_breakdown(
            db, entry, enabled,
            pair_suits=body.get('suit_view') == 'paired',
        )

    # Card detail section (phase 3). Independent toggles for custom
    # fields and archetype reference info, each with its own
    # whitelist of names/ids. None on the request body = include
    # every field on cards we already hydrated.
    include_custom = bool(body.get('include_custom_fields'))
    requested_custom = body.get('custom_fields')
    custom_set = (
        {str(n).lower() for n in requested_custom}
        if isinstance(requested_custom, list) else None
    )

    include_archetype = bool(body.get('include_archetype_fields'))
    requested_archetype = body.get('archetype_fields')
    archetype_set = (
        {int(i) for i in requested_archetype if str(i).lstrip('-').isdigit()}
        if isinstance(requested_archetype, list) else None
    )

    card_details = _build_card_details(
        entry,
        include_custom=include_custom,
        custom_names=custom_set,
        include_archetype=include_archetype,
        archetype_field_ids=archetype_set,
    )

    # Astrological event chart (phase 4). Same chart_cache + lazy
    # generation pipeline the entries/<id>/chart route uses. If
    # generation fails for any reason we keep rendering the rest of
    # the PDF rather than 500'ing on the whole export.
    chart_block = None
    if body.get('include_chart'):
        chart = _resolve_event_chart(db, entry)
        if chart:
            chart_block = {
                'image_uri': _render_chart_png_data_uri(chart['svg']),
                'planets': _planetary_positions(chart.get('chart_data')),
                'house_system': chart.get('house_system'),
                'timezone': chart.get('timezone'),
            }

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(['html']),
    )
    template = env.get_template('entry_export.html')
    html_str = template.render(
        entry=entry,
        breakdown_tabs=breakdown_tabs,
        card_details=card_details,
        chart_block=chart_block,
        include_spread_instructions=bool(body.get('include_spread_instructions')),
    )

    css_path = _TEMPLATE_DIR / 'entry_export.css'
    try:
        pdf_bytes = HTML(string=html_str, base_url=str(_TEMPLATE_DIR)).write_pdf(
            stylesheets=[CSS(filename=str(css_path))],
        )
    except Exception as e:
        logger.exception('PDF export failed for entry %s: %s', entry_id, e)
        return jsonify({'error': f'PDF generation failed: {e}'}), 500

    title_stem = entry.get('title') or f'entry_{entry_id}'
    date_part = (entry.get('reading_datetime') or entry.get('created_at') or '')[:10]
    filename = f'{_safe_filename(title_stem)}_{date_part}.pdf' if date_part \
        else f'{_safe_filename(title_stem)}.pdf'

    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


@pdf_export_bp.route('/api/entries/<int:entry_id>/export-options')
def export_options(entry_id):
    """Enumerate which custom fields + archetype reference fields are
    available to toggle in the export modal. Honours the same
    ?readings=<id>&readings=<id>... query the export endpoint
    accepts on its body, so the modal can re-fetch as the user
    changes the reading selection."""
    db = current_app.config['DB']
    cache = current_app.config.get('THUMB_CACHE')
    entry = _hydrate_entry_for_pdf(db, entry_id, cache=cache)
    if entry is None:
        return jsonify({'error': 'Entry not found'}), 404
    readings = request.args.getlist('readings', type=int)
    _select_readings(entry, readings or None)
    options = _available_field_options(entry)
    options['chart_available'] = _entry_chart_ready(entry)
    return jsonify(options)
