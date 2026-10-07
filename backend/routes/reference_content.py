"""
Reference-section endpoints: astrology, Kabbalah, numerology, chakras.

Static curated content comes from the root reference_content module;
everything derivable comes live from birth_cards.py (decan calendar,
rulers, trumps, court systems). Card references are hydrated exactly
like the birth-card endpoints (archetype ids + default-Tarot-deck card
ids for images).

Every endpoint accepts an optional ?system_id= naming a correspondence
system; when present, each sign/planet/letter/number/chakra also lists
the archetypes that system assigns to it (zodiac_sign / planet / decan /
hebrew_letter / numerology / chakra fields). Cross-references are
computed, never stored here.
"""

import json
import unicodedata
from collections import defaultdict
from datetime import date

from flask import Blueprint, jsonify, request, current_app

import birth_cards as bc
import reference_content as rc
from database.correspondences import parse_decan
from database.entity_notes import ENTITY_KINDS
from backend.routes.birth_cards import make_card_hydrators, _prefs
from backend.utils import require_json

reference_content_bp = Blueprint('reference_content', __name__)

_MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Alternate romanizations seen in the wild, so a user's hebrew_letter
# field options match regardless of spelling convention.
_LETTER_ALIASES = {
    'Aleph': ['alef'], 'Beth': ['bet', 'beit'], 'Gimel': ['gimmel'],
    'Daleth': ['dalet'], 'Heh': ['he', 'hey'], 'Vav': ['vau', 'waw'],
    'Zayin': ['zain'], 'Cheth': ['chet', 'het', 'heth'],
    'Teth': ['tet'], 'Yod': ['yud'], 'Kaph': ['caph', 'kaf'],
    'Lamed': ['lamedh'], 'Mem': [], 'Nun': [], 'Samekh': ['samech'],
    'Ayin': [], 'Peh': ['pe', 'fe'], 'Tzaddi': ['tsade', 'tzadi', 'tsadi'],
    'Qoph': ['qof', 'kof'], 'Resh': [], 'Shin': [], 'Tav': ['tau', 'taw'],
}


# Court rank words across deck traditions, for splitting a sephira's
# system-assigned cards into pips and courts in the panel.
_COURT_WORDS = {'king', 'queen', 'knight', 'page', 'prince', 'princess',
                'knave', 'dame', 'cavalier', 'valet'}


def _is_court_name(name):
    return name.split(' ', 1)[0].lower() in _COURT_WORDS


# Sephira attributions live in the same hebrew_letter field (values
# like 'כֶּתֶר / Kether'); alternate romanizations for matching them.
_SEPHIRA_ALIASES = {
    'Kether': ['keter'], 'Chokmah': ['chochmah', 'hokmah', 'chokma'],
    'Binah': [], 'Chesed': ['hesed'], 'Geburah': ['gevurah'],
    'Tiphareth': ['tiphereth', 'tiferet', 'tifereth'],
    'Netzach': ['netsach'], 'Hod': [], 'Yesod': [],
    'Malkuth': ['malchut', 'malkut'],
}


def _span_text(start, end):
    """'(3, 21), (4, 20)' -> 'Mar 21 – Apr 20'."""
    return (f'{_MONTHS[start[0]]} {start[1]} – '
            f'{_MONTHS[end[0]]} {end[1]}')


def _norm(value):
    """Matching key: casefold and strip combining marks, so IAST
    Sanskrit ('Mūlādhāra') matches plain spellings ('Muladhara') and
    pointed Hebrew matches unpointed."""
    decomposed = unicodedata.normalize('NFD', value.strip().lower())
    return ''.join(ch for ch in decomposed if not unicodedata.combining(ch))


# Fields whose values are often stored as slash-joined alternatives
# ('צ / Tsadi', 'Fifth Chakra / Viśuddha / Throat Chakra') — each part
# is indexed separately so any one spelling matches.
_SLASH_JOINED_FIELDS = ('hebrew_letter', 'chakra')


def _assignments_index(db):
    """Group the chosen system's assignments by (field, normalized
    value) -> [archetype refs]. Returns None when no system was
    requested."""
    raw = request.args.get('system_id')
    if not raw:
        return None
    try:
        system_id = int(raw)
    except ValueError:
        return None
    index = defaultdict(list)
    seen = defaultdict(set)
    for row in db.get_system_assignments(system_id):
        r = row if isinstance(row, dict) else dict(row)
        value = (r.get('field_value') or '').strip()
        if not value:
            continue
        key = (r['field_name'], _norm(value))
        if r['archetype_id'] in seen[key]:
            continue
        seen[key].add(r['archetype_id'])
        ref = {
            'archetype_id': r['archetype_id'],
            'name': r['archetype_name'],
            'cartomancy_type': r['cartomancy_type'],
        }
        index[key].append(ref)
        # Slash-joined values ('צ / Tsadi', 'First Chakra / Mūlādhāra /
        # Root Chakra') index each part separately, so any one
        # spelling matches.
        if r['field_name'] in _SLASH_JOINED_FIELDS and '/' in value:
            for part in value.split('/'):
                part = _norm(part)
                if not part or part == key[1]:
                    continue
                pkey = (r['field_name'], part)
                if r['archetype_id'] not in seen[pkey]:
                    seen[pkey].add(r['archetype_id'])
                    index[pkey].append(ref)
        # Decan values ('Jupiter in Libra') also count toward their
        # sign and planet.
        if r['field_name'] == 'decan':
            parsed = parse_decan(value)
            if parsed:
                planet, sign = parsed
                for field, name in (('planet', planet), ('zodiac_sign', sign)):
                    dkey = (field, name.lower())
                    if r['archetype_id'] not in seen[dkey]:
                        seen[dkey].add(r['archetype_id'])
                        index[dkey].append(index[key][-1])
    return index


def _assigned(index, field, *values):
    """Assigned archetypes for any of the given values (deduped)."""
    if index is None:
        return []
    out, have = [], set()
    for v in values:
        for ref in index.get((field, _norm(v)), []):
            if ref['archetype_id'] not in have:
                have.add(ref['archetype_id'])
                out.append(ref)
    return out


@reference_content_bp.route('/api/reference/astrology')
def astrology():
    db = current_app.config['DB']
    _, eight_eleven, court_system = _prefs(db)
    major, minor, by_card_name = make_card_hydrators(db, eight_eleven)
    index = _assignments_index(db)

    def court_arc(ref, system):
        court = bc.decan_court(ref, system)
        return {**court, **by_card_name(court['name'])}

    signs = []
    for i, sign in enumerate(rc.SIGNS):
        decan_rows = bc.DECANS[i * 3:i * 3 + 3]
        decans = []
        for j, (start, end, rank, suit) in enumerate(decan_rows):
            ref = {'rank': rank, 'suit': suit}
            rulers = bc.zodiacal_rulers(ref)
            decans.append({
                'index': j + 1,
                'dates': _span_text(start, end),
                'planet': rulers['planet'],
                'minor': minor(ref),
                'planet_trump': major(rulers['planet_major'], canonical=True),
            })
        # The sign's span: first decan's start through third's end.
        dates = _span_text(decan_rows[0][0], decan_rows[2][1])
        # Two court arcs touch each sign: its own court (0°–20°) via
        # decan I, and the next sign's court (20°–30°) via decan III.
        first, third = decan_rows[0], decan_rows[2]
        courts = {
            system: [
                court_arc({'rank': first[2], 'suit': first[3]}, system),
                court_arc({'rank': third[2], 'suit': third[3]}, system),
            ]
            for system in bc.COURT_SYSTEMS
        }
        signs.append({
            **sign,
            'dates': dates,
            'trump': major(bc.SIGN_MAJORS[sign['name']], canonical=True),
            'decans': decans,
            'courts': courts,
            'assigned': _assigned(index, 'zodiac_sign', sign['name']),
        })

    planets = []
    for planet in rc.PLANETS:
        trump_number = bc.PLANET_MAJORS.get(planet['name'])
        modern = False
        if trump_number is None:
            trump_number = rc.MODERN_PLANET_MAJORS.get(planet['name'])
            modern = trump_number is not None
        decans_ruled = [
            {'sign': rulers['sign'],
             'minor': minor({'rank': rank, 'suit': suit})}
            for (start, end, rank, suit) in bc.DECANS
            for rulers in [bc.zodiacal_rulers({'rank': rank, 'suit': suit})]
            if rulers['planet'] == planet['name']
        ]
        planets.append({
            **planet,
            'trump': major(trump_number, canonical=True) if trump_number else None,
            'modern_attribution': modern,
            'decans_ruled': decans_ruled,
            'assigned': _assigned(index, 'planet', planet['name']),
        })

    # Today's decan, for the wheel's "you are here" marker.
    today_ref = bc.zodiacal_card(date.today())
    return jsonify({
        'eight_eleven': eight_eleven,
        'court_system': court_system,
        'signs': signs,
        'planets': planets,
        'today_decan': bc.decan_position(today_ref),
    })


@reference_content_bp.route('/api/reference/kabbalah')
def kabbalah():
    """The Tree of Life. With ?system_id= and ?deck_id= (a configured
    tree tab), each path's cards come from that correspondence system's
    hebrew_letter assignments — so a Thoth-style system's Emperor/Star
    letter swap shows up — and images come from the named deck. Without
    them, canonical GD attributions and the default Tarot deck."""
    db = current_app.config['DB']
    _, eight_eleven, court_system = _prefs(db)
    try:
        deck_id = int(request.args.get('deck_id', ''))
    except ValueError:
        deck_id = None
    major, minor, by_card_name = make_card_hydrators(db, eight_eleven, deck_id)
    index = _assignments_index(db)

    court_ranks = rc.TREE_COURT_RANKS[court_system]
    sephiroth = []
    for s in rc.SEPHIROTH:
        entry = {
            **s,
            # The four Minors of the sephira's number: Aces for Kether
            # down to Tens for Malkuth.
            'minors': [minor({'rank': s['number'], 'suit': suit})
                       for suit in bc.SUITS],
        }
        # Tetragrammaton courts on 2 / 3 / 6 / 10.
        rank = court_ranks.get(s['number'])
        if rank:
            entry['court_rank'] = rank
            entry['courts'] = [
                {'rank': rank, 'suit': suit,
                 **by_card_name(f'{rank} of {suit}')}
                for suit in bc.SUITS
            ]
        # When the tree's system assigns cards to this sephira itself
        # (hebrew_letter values like 'כֶּתֶר / Kether'), those cards ARE
        # the sephira's cards — they replace the rank-derived minors
        # and preference courts in the panel, split pips from courts.
        system_cards = [
            {'archetype_id': ref['archetype_id'], 'name': ref['name'],
             'card_id': by_card_name(ref['name'])['card_id']}
            for ref in _assigned(index, 'hebrew_letter', s['name'],
                                 *_SEPHIRA_ALIASES.get(s['name'], []))
        ]
        pips = [c for c in system_cards if not _is_court_name(c['name'])]
        court_cards = [c for c in system_cards if _is_court_name(c['name'])]
        if pips:
            entry['cards'] = pips
        if court_cards:
            entry['court_cards'] = court_cards
        sephiroth.append(entry)
    paths = []
    for p in rc.TREE_PATHS:
        # The system's own cards for this letter (hebrew_letter field,
        # alias spellings included), with images from the tree's deck.
        letter_cards = [
            {'archetype_id': ref['archetype_id'], 'name': ref['name'],
             'card_id': by_card_name(ref['name'])['card_id']}
            for ref in _assigned(index, 'hebrew_letter',
                                 p['letter'], p['glyph'],
                                 *_LETTER_ALIASES.get(p['letter'], []))
        ]
        paths.append({
            **p,
            'trump': major(p['trump'], canonical=True),
            'letter_cards': letter_cards,
        })
    return jsonify({'sephiroth': sephiroth, 'paths': paths,
                    'court_system': court_system})


# === Configured tree tabs (label + correspondence system + deck) ===

TREES_KEY = 'kabbalah_trees'


@reference_content_bp.route('/api/reference/kabbalah/trees')
def get_kabbalah_trees():
    raw = current_app.config['DB'].get_setting(TREES_KEY)
    try:
        trees = json.loads(raw) if raw else []
    except ValueError:
        trees = []
    return jsonify({'trees': trees if isinstance(trees, list) else []})


@reference_content_bp.route('/api/reference/kabbalah/trees', methods=['PUT'])
@require_json
def set_kabbalah_trees(data):
    trees = data.get('trees')
    if not isinstance(trees, list):
        return jsonify({'error': 'trees must be a list'}), 400
    cleaned = []
    for t in trees:
        if not isinstance(t, dict):
            return jsonify({'error': 'each tree must be an object'}), 400
        label = (t.get('label') or '').strip()
        system_id = t.get('system_id')
        deck_id = t.get('deck_id')
        if not label:
            return jsonify({'error': 'each tree needs a label'}), 400
        if not isinstance(system_id, int) or not isinstance(deck_id, int):
            return jsonify({'error': 'each tree needs system_id and deck_id'}), 400
        cleaned.append({'label': label, 'system_id': system_id,
                        'deck_id': deck_id})
    current_app.config['DB'].set_setting(TREES_KEY, json.dumps(cleaned))
    return jsonify({'trees': cleaned})


# Rank labels across deck traditions: display order plus which are
# courts (order >= 11). Unknown labels sort after these.
_RANK_ORDER = {
    'ace': 1, 'as': 1, 'one': 1, 'uno': 1,
    'two': 2, 'dos': 2, 'three': 3, 'tres': 3, 'four': 4, 'cuatro': 4,
    'five': 5, 'cinco': 5, 'six': 6, 'seis': 6, 'seven': 7, 'siete': 7,
    'eight': 8, 'ocho': 8, 'nine': 9, 'nueve': 9, 'ten': 10, 'diez': 10,
    'page': 11, 'jack': 11, 'sota': 11, 'fante': 11, 'knave': 11,
    'valet': 11, 'princess': 11, 'unter': 11,
    'ober': 13,
    'knight': 12, 'caballo': 12, 'cavallo': 12, 'cavalier': 12, 'prince': 12,
    'queen': 13, 'dame': 13, 'regina': 13, 'reina': 13,
    'king': 14, 'rey': 14, 're': 14, 'roi': 14,
}


def _rank_label(row):
    """Display rank: the rank field when it's a word label ('Ace',
    'Sota'); Tarot stores numeric sort codes, so fall back to the
    leading word of an 'X of Y' name."""
    rank = (row.get('rank') or '').strip()
    if rank and not rank.isdigit():
        return rank
    name = row.get('name') or ''
    if ' of ' in name:
        return name.split(' of ', 1)[0]
    return rank or '?'


def _rank_sort_key(label):
    low = label.lower()
    if low in _RANK_ORDER:
        return (_RANK_ORDER[low], '')
    if low.isdigit():
        return (int(low), '')
    return (99, low)


def _is_court_rank(label):
    return _RANK_ORDER.get(label.lower(), 0) >= 11


# Suit display order mirrors the Tarot suits (Wands, Cups, Swords,
# Pentacles) through their standard counterparts — so playing-card
# suits run Clubs, Hearts, Spades, Diamonds. Unknown suit names
# (runic aetts, custom types) follow alphabetically.
_SUIT_ORDER = {
    'wands': 0, 'clubs': 0, 'bastos': 0, 'batons': 0, 'acorns': 0,
    'cups': 1, 'hearts': 1, 'copas': 1,
    'swords': 2, 'spades': 2, 'espadas': 2, 'leaves': 2,
    'pentacles': 3, 'diamonds': 3, 'oros': 3, 'coins': 3, 'bells': 3,
}


def _suit_sort_key(name):
    return (_SUIT_ORDER.get(name.lower(), 99), name)


def _suit_types(db):
    """Deck types whose archetypes carry suits (Major Arcana excluded),
    Tarot first, the rest alphabetical. Petit Lenormand qualifies
    through its seeded playing-card inset rank/suit."""
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT DISTINCT cartomancy_type FROM card_archetypes "
        "WHERE suit IS NOT NULL AND TRIM(suit) != '' "
        "AND suit != 'Major Arcana' ORDER BY cartomancy_type")
    names = [r if isinstance(r, str) else dict(r)['cartomancy_type']
             for r in cursor.fetchall()]
    if 'Tarot' in names:
        names = ['Tarot'] + [n for n in names if n != 'Tarot']
    return names


def _suited_archetypes(db, cartomancy_type):
    """The type's suited archetypes, hydrated with card ids from the
    type's default deck, plus a display rank label."""
    from backend.routes.birth_cards import default_tarot_card_ids
    deck_id = db.get_default_deck(cartomancy_type)
    card_ids = default_tarot_card_ids(db, deck_id) if deck_id else {}
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT id, name, rank, suit FROM card_archetypes "
        "WHERE cartomancy_type = ? AND suit IS NOT NULL "
        "AND TRIM(suit) != '' AND suit != 'Major Arcana'",
        (cartomancy_type,))
    out = []
    for row in cursor.fetchall():
        r = row if isinstance(row, dict) else dict(row)
        out.append({
            'archetype_id': r['id'],
            'name': r['name'],
            'suit': r['suit'],
            'rank': _rank_label(r),
            'card_id': card_ids.get(r['name'].lower()),
        })
    out.sort(key=lambda c: (_rank_sort_key(c['rank']),
                            _suit_sort_key(c['suit']), c['name']))
    return out


def _resolve_suit_type(db):
    """The ?type= param validated against the suited types; Tarot (or
    the first suited type) when absent or unknown."""
    types = _suit_types(db)
    ctype = request.args.get('type')
    if ctype not in types:
        ctype = 'Tarot' if 'Tarot' in types or not types else types[0]
    return types, ctype


@reference_content_bp.route('/api/reference/suits')
def suits():
    """Suits per deck type. Tarot gets the curated four (elements,
    alternate names, playing-card counterparts) hydrated from the
    default Tarot deck; every other suited type derives its suits and
    cards from its archetypes, images from its own default deck. Pips
    and courts arrive split."""
    db = current_app.config['DB']
    types, ctype = _resolve_suit_type(db)

    if ctype == 'Tarot':
        _, eight_eleven, _court = _prefs(db)
        _major, minor, by_card_name = make_card_hydrators(db, eight_eleven)
        out = []
        for suit in rc.SUIT_INFO:
            pips = [minor({'rank': r, 'suit': suit['name']})
                    for r in range(1, 11)]
            courts = [
                {'rank': rank, 'suit': suit['name'],
                 **by_card_name(f"{rank} of {suit['name']}")}
                for rank in rc.COURT_RANKS
            ]
            out.append({**suit, 'pips': pips, 'courts': courts})
    else:
        cards = _suited_archetypes(db, ctype)
        suit_names = sorted({c['suit'] for c in cards}, key=_suit_sort_key)
        out = []
        for suit_name in suit_names:
            of_suit = [c for c in cards if c['suit'] == suit_name]
            out.append({
                'name': suit_name,
                'pips': [c for c in of_suit if not _is_court_rank(c['rank'])],
                'courts': [c for c in of_suit if _is_court_rank(c['rank'])],
            })
    return jsonify({'types': types, 'type': ctype, 'suits': out})


@reference_content_bp.route('/api/reference/ranks')
def ranks():
    """Rank groups per suited deck type: each distinct rank with its
    cards across the suits, in traditional rank order."""
    db = current_app.config['DB']
    types, ctype = _resolve_suit_type(db)
    cards = _suited_archetypes(db, ctype)
    groups: dict = {}
    for c in cards:
        groups.setdefault(c['rank'], []).append(c)
    ordered = sorted(groups, key=_rank_sort_key)
    return jsonify({
        'types': types,
        'type': ctype,
        'ranks': [{'rank': label, 'cards': groups[label]}
                  for label in ordered],
    })


@reference_content_bp.route('/api/reference/numerology')
def numerology():
    db = current_app.config['DB']
    _, eight_eleven, _court = _prefs(db)
    major, minor, _by_card_name = make_card_hydrators(db, eight_eleven)
    index = _assignments_index(db)

    entries = []
    for entry in rc.NUMBERS:
        out = dict(entry)
        # Derived blocks attach only where they apply, so future
        # entries outside these ranges ('11', '22', a second system's
        # numbers) still render their text cleanly with nothing broken.
        try:
            n = int(entry['number'])
        except (TypeError, ValueError):
            n = None
        if n == 0:
            out['majors'] = [major(22)]
        elif n is not None and n in bc.CONSTELLATIONS:
            out['majors'] = [major(m) for m in bc.CONSTELLATIONS[n]]
        if n is not None and 1 <= n <= 10:
            out['minors'] = [minor({'rank': n, 'suit': s}) for s in bc.SUITS]
        out['assigned'] = _assigned(index, 'numerology', entry['number'])
        entries.append(out)

    # The Numerology & Ranks section's per-type rank tabs come from
    # /api/reference/ranks; the type list rides along here so the UI
    # can render its tabs from one request.
    return jsonify({'entries': entries, 'suit_types': _suit_types(db)})


_CHAKRA_ORDINALS = ['First', 'Second', 'Third', 'Fourth',
                    'Fifth', 'Sixth', 'Seventh']


@reference_content_bp.route('/api/reference/chakras')
def chakras():
    db = current_app.config['DB']
    index = _assignments_index(db)
    return jsonify({'chakras': [
        {**c,
         'assigned': _assigned(index, 'chakra', c['name'], c['sanskrit'],
                               f"{c['name']} Chakra",
                               f'{_CHAKRA_ORDINALS[i]} Chakra')}
        for i, c in enumerate(rc.CHAKRAS)
    ]})


# === Entity source notes (signs / planets / sephiroth / paths /
#     chakras / numbers × reference sources) ===

@reference_content_bp.route('/api/reference/entity-notes')
def get_entity_notes():
    kind = request.args.get('kind', '')
    key = request.args.get('key', '')
    if kind not in ENTITY_KINDS or not key:
        return jsonify({'error': f'kind must be one of {ENTITY_KINDS}, '
                                 'key required'}), 400
    db = current_app.config['DB']
    return jsonify({'notes': db.get_entity_notes(kind, key)})


@reference_content_bp.route('/api/reference/entity-notes', methods=['PUT'])
@require_json
def set_entity_note(data):
    kind = data.get('kind', '')
    key = (data.get('key') or '').strip()
    source_id = data.get('source_id')
    if kind not in ENTITY_KINDS or not key:
        return jsonify({'error': f'kind must be one of {ENTITY_KINDS}, '
                                 'key required'}), 400
    if not isinstance(source_id, int):
        return jsonify({'error': 'source_id required'}), 400
    db = current_app.config['DB']
    if not db.get_reference_source(source_id):
        return jsonify({'error': 'No such reference source'}), 404
    db.set_entity_note(kind, key, source_id, data.get('content') or '')
    return jsonify({'notes': db.get_entity_notes(kind, key)})
