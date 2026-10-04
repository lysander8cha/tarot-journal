"""
Birth-card endpoints (Greer "Lifetime Cards"). Pure computation over a
birth date via the root birth_cards module — nothing is stored except
the two display preferences (method, 8/11 naming) in settings.

Card references come back hydrated with display names and, where a
match exists, the Tarot card_archetypes id so the UI can link into the
Reference section.
"""

from datetime import date

from flask import Blueprint, jsonify, request, current_app

import birth_cards as bc
from backend.utils import require_json

birth_cards_bp = Blueprint('birth_cards', __name__)

METHOD_KEY = 'birth_cards_method'
EIGHT_ELEVEN_KEY = 'birth_cards_eight_eleven'
COURT_SYSTEM_KEY = 'birth_cards_court_system'


def _prefs(db):
    method = db.get_setting(METHOD_KEY) or bc.GREER
    eight_eleven = db.get_setting(EIGHT_ELEVEN_KEY) or 'golden_dawn'
    court_system = db.get_setting(COURT_SYSTEM_KEY) or 'golden_dawn'
    if method not in bc.METHODS:
        method = bc.GREER
    if eight_eleven not in ('golden_dawn', 'marseille'):
        eight_eleven = 'golden_dawn'
    if court_system not in bc.COURT_SYSTEMS:
        court_system = 'golden_dawn'
    return method, eight_eleven, court_system


def tarot_archetype_ids(db):
    """Map (rank, suit) -> archetype id for every Tarot archetype.
    Majors use rank '0'..'21' with suit 'Major Arcana'; Minors are
    matched by name instead (rank strings differ per deck tradition)."""
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT id, name, rank, suit FROM card_archetypes "
        "WHERE cartomancy_type = 'Tarot'")
    by_rank = {}
    by_name = {}
    for row in cursor.fetchall():
        r = row if isinstance(row, dict) else dict(row)
        if r['suit'] == 'Major Arcana' and r['rank'] is not None:
            by_rank[str(r['rank'])] = r['id']
        by_name[r['name'].lower()] = r['id']
    return by_rank, by_name


def default_tarot_card_ids(db, deck_id=None):
    """Map archetype name (lowercased) -> card id for images, from the
    given deck, or the user's default Tarot deck when none is named.
    Empty if neither exists."""
    if deck_id is None:
        deck_id = db.get_default_deck('Tarot')
    if not deck_id:
        return {}
    cursor = db.conn.cursor()
    cursor.execute(
        'SELECT id, name, archetype FROM cards WHERE deck_id = ? '
        'ORDER BY card_order', (deck_id,))
    out = {}
    for row in cursor.fetchall():
        r = row if isinstance(row, dict) else dict(row)
        for key in (r.get('archetype'), r.get('name')):
            if key and key.lower() not in out:
                out[key.lower()] = r['id']
    return out


def make_card_hydrators(db, eight_eleven='golden_dawn', deck_id=None):
    """Build (major, minor, by_card_name) hydrator functions that attach
    display names, archetype ids, and card ids for images — from
    deck_id when given, else the default Tarot deck. Shared with the
    reference-content routes.

    major(n, canonical=True) keeps the canonical Golden Dawn name even
    under the Marseille 8/11 preference — astrological/kabbalistic
    attributions are card identities (Leo IS the Strength card), so the
    numbering toggle deliberately doesn't rename those.
    """
    by_rank, by_name = tarot_archetype_ids(db)
    card_ids = default_tarot_card_ids(db, deck_id)

    def major(n, canonical=False):
        if n is None:
            return None
        # Image lookup tries both 8/11 labels plus Thoth aliases, so a
        # Marseille-style or Thoth default deck still resolves.
        candidates = [bc.major_name(n, eight_eleven), bc.MAJOR_NAMES[n]]
        if n == 8:
            candidates.append('Justice')
        if n == 11:
            candidates.append('Strength')
        candidates.extend(bc.MAJOR_ALIASES.get(n, []))
        card_id = next(
            (card_ids[c.lower()] for c in candidates if c.lower() in card_ids),
            None)
        return {
            'number': n,
            'name': bc.MAJOR_NAMES[n] if canonical else bc.major_name(n, eight_eleven),
            'archetype_id': by_rank.get(bc.major_archetype_rank(n)),
            'card_id': card_id,
        }

    def minor(ref):
        name = bc.card_ref_name(ref)
        return {
            'rank': ref['rank'],
            'suit': ref['suit'],
            'name': name,
            'archetype_id': by_name.get(name.lower()),
            'card_id': card_ids.get(name.lower()),
        }

    def by_card_name(name):
        """Hydrate an arbitrary card name (e.g. 'Queen of Wands')."""
        return {
            'name': name,
            'archetype_id': by_name.get(name.lower()),
            'card_id': card_ids.get(name.lower()),
        }

    return major, minor, by_card_name


def _hydrate(profile, eight_eleven, court_system, db):
    """Attach display names, archetype ids, and (when a default Tarot
    deck is set) card ids for images to every card reference."""
    major, minor, by_card_name = make_card_hydrators(db, eight_eleven)

    def ruler_major(n):
        return major(n, canonical=True)

    rulers = bc.zodiacal_rulers(profile['zodiacal_card'])
    court = bc.decan_court(profile['zodiacal_card'], court_system)

    out = dict(profile)
    out['zodiacal_rulers'] = rulers
    out['decan_court'] = court
    out['cards'] = {
        'personality': major(profile['personality']),
        'soul': major(profile['soul']),
        'teacher': major(profile['teacher']),
        'hidden_factor': [major(n) for n in profile['hidden_factor']],
        'constellation_majors': [major(n) for n in profile['constellation']['majors']],
        'lessons_and_opportunities': [
            minor(ref) for ref in profile['lessons_and_opportunities']],
        'zodiacal': minor(profile['zodiacal_card']),
        'zodiacal_sign_ruler': ruler_major(rulers['sign_major']),
        'zodiacal_planet_ruler': ruler_major(rulers['planet_major']),
        'decan_court': {
            'rank': court['rank'],
            'suit': court['suit'],
            **by_card_name(court['name']),
        },
    }
    for key in ('year_card', 'generic_year', 'personal_month'):
        if key in profile:
            out['cards'][key] = major(profile[key])
    # One entry per Major so the year timeline renders without a
    # hydration per year.
    out['majors_by_number'] = {n: major(n) for n in range(1, 23)}
    return out


def _compute_response(db, birth: date, birth_date_str: str):
    method = request.args.get('method')
    eight_eleven = request.args.get('eight_eleven')
    court_system = request.args.get('court_system')
    saved_method, saved_ee, saved_court = _prefs(db)
    method = method if method in bc.METHODS else saved_method
    eight_eleven = eight_eleven if eight_eleven in ('golden_dawn', 'marseille') else saved_ee
    court_system = court_system if court_system in bc.COURT_SYSTEMS else saved_court

    today = date.today()
    try:
        reference_year = int(request.args.get('year', today.year))
        reference_month = int(request.args.get('month', today.month))
    except ValueError:
        return jsonify({'error': 'year and month must be integers'}), 400

    profile = bc.calculate(
        birth, method=method,
        reference_year=reference_year, reference_month=reference_month)
    hydrated = _hydrate(profile, eight_eleven, court_system, db)

    age = today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day))
    hydrated['birth_date'] = birth_date_str
    hydrated['age'] = age
    hydrated['eight_eleven'] = eight_eleven
    hydrated['court_system'] = court_system
    hydrated['reference_year'] = reference_year
    hydrated['reference_month'] = reference_month
    # Year Cards run in ~decade-long consecutive runs ("cycle themes");
    # the series is method-independent (one formula, month+day+year).
    # Birth year through ten years past the reference year gives the
    # UI enough to group into runs without a second request.
    hydrated['year_series'] = bc.year_card_series(
        birth, birth.year, max(reference_year, today.year) + 10)
    return jsonify(hydrated)


@birth_cards_bp.route('/api/profiles/<int:profile_id>/birth-cards')
def profile_birth_cards(profile_id):
    db = current_app.config['DB']
    row = db.get_profile(profile_id)
    if not row:
        return jsonify({'error': 'Profile not found'}), 404
    profile = row if isinstance(row, dict) else dict(row)
    birth_str = profile.get('birth_date')
    if not birth_str:
        return jsonify({'error': 'Profile has no birth date'}), 400
    try:
        birth = date.fromisoformat(birth_str)
    except ValueError:
        return jsonify({'error': f'Unreadable birth date: {birth_str}'}), 400
    return _compute_response(db, birth, birth_str)


@birth_cards_bp.route('/api/birth-cards/prefs', methods=['PUT'])
@require_json
def set_birth_card_prefs(data):
    db = current_app.config['DB']
    method = data.get('method')
    eight_eleven = data.get('eight_eleven')
    court_system = data.get('court_system')
    if method is not None:
        if method not in bc.METHODS:
            return jsonify({'error': f'method must be one of {bc.METHODS}'}), 400
        db.set_setting(METHOD_KEY, method)
    if eight_eleven is not None:
        if eight_eleven not in ('golden_dawn', 'marseille'):
            return jsonify({'error': 'eight_eleven must be golden_dawn or marseille'}), 400
        db.set_setting(EIGHT_ELEVEN_KEY, eight_eleven)
    if court_system is not None:
        if court_system not in bc.COURT_SYSTEMS:
            return jsonify({'error': f'court_system must be one of {bc.COURT_SYSTEMS}'}), 400
        db.set_setting(COURT_SYSTEM_KEY, court_system)
    method, eight_eleven, court_system = _prefs(db)
    return jsonify({'method': method, 'eight_eleven': eight_eleven,
                    'court_system': court_system})
