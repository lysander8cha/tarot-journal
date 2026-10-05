"""
Insights — one aggregate payload for the dashboard (Nocturne 5b).

Counting happens here, in code, over the entries the filters select:
per-card frequency (by archetype where known, so the same card across
decks aggregates), monthly cadence, suit distribution, reversal rate
and the position it concentrates in, plus the headline stat cards.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

insights_bp = Blueprint('insights', __name__)

CADENCE_MONTHS = 14
MIN_POSITION_SAMPLE = 5   # a "highest reversal position" needs this many draws
# Readings larger than this are skipped for pair-counting: in a Grand
# Tableau every card co-occurs with every other, so big spreads drown
# the signal of pairs that genuinely recur across readings.
MAX_CARDS_FOR_PAIRS = 12
MIN_PAIR_COUNT = 2


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _shift_month(dt: datetime, back: int) -> datetime:
    y, m = dt.year, dt.month - back
    while m <= 0:
        y -= 1
        m += 12
    return datetime(y, m, 1)


@insights_bp.route('/api/stats/insights')
def get_insights():
    db = current_app.config['DB']
    cur = db.conn.cursor()

    days = request.args.get('days', type=int)          # None = all time
    querent_id = request.args.get('querent_id', type=int)
    deck_id = request.args.get('deck_id', type=int)
    deck_type_id = request.args.get('deck_type_id', type=int)

    # ── Entries in scope ────────────────────────────────────────────
    sql = '''
        SELECT DISTINCT e.id, COALESCE(e.reading_datetime, e.created_at) AS when_
        FROM journal_entries e
        LEFT JOIN entry_querents q ON q.entry_id = e.id
        WHERE 1=1
    '''
    params: list = []
    if querent_id:
        sql += ' AND (q.profile_id = ? OR e.querent_id = ?)'
        params += [querent_id, querent_id]
    if days:
        sql += " AND COALESCE(e.reading_datetime, e.created_at) >= ?"
        params.append((datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'))
    rows = cur.execute(sql, params).fetchall()
    entry_when = {r['id']: str(r['when_'] or '') for r in rows}
    entry_ids = set(entry_when)

    # ── Readings + cards ────────────────────────────────────────────
    readings = [dict(r) for r in cur.execute(
        'SELECT entry_id, spread_id, spread_name, deck_id, deck_name, cards_used,'
        ' querent_id FROM entry_readings'
    ).fetchall() if r['entry_id'] in entry_ids]
    # A reading marked "for" one querent belongs to that person alone;
    # unmarked readings belong to all of the entry's querents.
    if querent_id:
        readings = [r for r in readings if r['querent_id'] in (None, querent_id)]

    # Parse each reading's cards once, and collect every deck involved.
    # Most readings carry deck ids on their CARDS, not on the reading
    # row (the editor has stored them per-card since early 2026), so
    # deck/type filters must look at both levels or they silently drop
    # nearly everything.
    for rd in readings:
        try:
            rd['_cards'] = [c for c in json.loads(rd['cards_used'] or '[]')
                            if isinstance(c, dict)]
        except ValueError:
            rd['_cards'] = []
        involved = set()
        if rd['deck_id']:
            involved.add(rd['deck_id'])
        for c in rd['_cards']:
            if c.get('deck_id'):
                involved.add(c['deck_id'])
        rd['_deck_ids'] = involved

    # Per-card inclusion under a deck/type filter: a multi-deck reading
    # may involve the filtered deck, but only ITS cards should count.
    allowed_decks: set | None = None
    if deck_id:
        allowed_decks = {deck_id}
    elif deck_type_id:
        allowed_decks = {r['deck_id'] for r in cur.execute(
            'SELECT deck_id FROM deck_type_assignments WHERE type_id = ?',
            (deck_type_id,)).fetchall()}
    if allowed_decks is not None:
        readings = [r for r in readings if r['_deck_ids'] & allowed_decks]
        entry_ids = {r['entry_id'] for r in readings}
        entry_when = {k: v for k, v in entry_when.items() if k in entry_ids}

    def card_included(rd, c) -> bool:
        if allowed_decks is None:
            return True
        cd = c.get('deck_id') or rd['deck_id']
        return cd in allowed_decks

    # Lookups: card_id → archetype/name; archetype name → suit
    card_info = {r['id']: (r['archetype'], r['name']) for r in cur.execute(
        'SELECT id, archetype, name FROM cards').fetchall()}
    suit_of = {}
    for r in cur.execute('SELECT name, suit FROM card_archetypes').fetchall():
        if r['suit']:
            suit_of.setdefault(r['name'].lower(), r['suit'])
    positions_of = {r['id']: json.loads(r['positions'] or '[]') for r in cur.execute(
        'SELECT id, positions FROM spreads').fetchall()}
    deck_names = {r['id']: r['name'] for r in cur.execute(
        'SELECT id, name FROM decks').fetchall()}
    spread_names = {r['id']: r['name'] for r in cur.execute(
        'SELECT id, name FROM spreads').fetchall()}

    # Entry → querent names, for the per-querent panel (modern
    # entry_querents rows plus the legacy single querent_id column).
    querents_of: defaultdict = defaultdict(set)
    for r in cur.execute('''
        SELECT eq.entry_id, p.name FROM entry_querents eq
        JOIN profiles p ON p.id = eq.profile_id
    ''').fetchall():
        if r['entry_id'] in entry_ids:
            querents_of[r['entry_id']].add(r['name'])
    for r in cur.execute('''
        SELECT e.id, p.name FROM journal_entries e
        JOIN profiles p ON p.id = e.querent_id
        WHERE e.querent_id IS NOT NULL
    ''').fetchall():
        if r['id'] in entry_ids:
            querents_of[r['id']].add(r['name'])

    profile_names = {r['id']: r['name'] for r in cur.execute(
        'SELECT id, name FROM profiles').fetchall()}

    card_counts: Counter = Counter()
    suit_counts: Counter = Counter()
    pos_totals: Counter = Counter()
    pos_reversed: Counter = Counter()
    pair_counts: Counter = Counter()
    deck_usage: Counter = Counter()
    deck_last: dict = {}
    spread_usage: Counter = Counter()
    spread_last: dict = {}
    querent_entries: Counter = Counter()
    querent_cards: defaultdict = defaultdict(Counter)
    total_cards = 0
    reversed_count = 0

    for eid, qnames in querents_of.items():
        for qn in qnames:
            querent_entries[qn] += 1

    for rd in readings:
        cards = [c for c in rd['_cards'] if card_included(rd, c)]
        positions = positions_of.get(rd['spread_id']) or []
        when = entry_when.get(rd['entry_id'], '')

        # Deck usage: each deck involved in a reading counts once for
        # that reading (multi-deck spreads credit every deck used).
        reading_decks = set()
        if allowed_decks is None or rd['deck_id'] in allowed_decks:
            rd_deck = rd.get('deck_name') or deck_names.get(rd.get('deck_id'))
            if rd_deck:
                reading_decks.add(rd_deck)
        for c in cards:
            cd = c.get('deck_name') or deck_names.get(c.get('deck_id'))
            if cd:
                reading_decks.add(cd)
        for dn in reading_decks:
            deck_usage[dn] += 1
            if when and when > deck_last.get(dn, ''):
                deck_last[dn] = when

        sn = rd.get('spread_name') or spread_names.get(rd.get('spread_id'))
        if sn:
            spread_usage[sn] += 1
            if when and when > spread_last.get(sn, ''):
                spread_last[sn] = when

        rd_querents = ({profile_names[rd['querent_id']]}
                       if rd['querent_id'] in profile_names
                       else querents_of.get(rd['entry_id'], ()))
        reading_displays = set()
        for c in cards:
            archetype, fallback = card_info.get(c.get('card_id'), (None, None))
            display = archetype or fallback or (c.get('name') or '').strip()
            if not display:
                continue
            total_cards += 1
            card_counts[display] += 1
            reading_displays.add(display)
            for qn in rd_querents:  # per-querent tallies
                querent_cards[qn][display] += 1
            suit = suit_of.get(display.lower())
            if suit:
                suit_counts[suit] += 1
            is_reversed = bool(c.get('reversed'))
            if is_reversed:
                reversed_count += 1
            idx = c.get('position_index')
            if isinstance(idx, int) and 0 <= idx < len(positions):
                label = positions[idx].get('label') or f'Position {idx + 1}'
                pos_totals[label] += 1
                if is_reversed:
                    pos_reversed[label] += 1

        # Co-occurring pairs within this reading (skip huge spreads —
        # see MAX_CARDS_FOR_PAIRS).
        if 2 <= len(reading_displays) <= MAX_CARDS_FOR_PAIRS:
            names = sorted(reading_displays)
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pair_counts[(names[i], names[j])] += 1

    # ── Cadence: entries per month, last CADENCE_MONTHS ─────────────
    per_month = Counter(w[:7] for w in entry_when.values() if len(w) >= 7)
    now = datetime.now()
    cadence = []
    for back in range(CADENCE_MONTHS - 1, -1, -1):
        m = _shift_month(now, back)
        key = _month_key(m)
        cadence.append({
            'month': key,
            'label': m.strftime('%b'),
            'count': per_month.get(key, 0),
            'current': back == 0,
        })

    this_month = per_month.get(_month_key(now), 0)
    prev_month = per_month.get(_month_key(_shift_month(now, 1)), 0)

    # ── Highest-reversal position (with a minimum sample) ───────────
    top_pos = None
    best_rate = 0.0
    for label, total in pos_totals.items():
        if total < MIN_POSITION_SAMPLE:
            continue
        rate = pos_reversed[label] / total
        if pos_reversed[label] and rate > best_rate:
            best_rate = rate
            top_pos = {'label': label, 'rate': round(rate * 100, 1)}

    whens = sorted(w for w in entry_when.values() if w)
    return jsonify({
        'entries': len(entry_ids),
        'date_range': {
            'from': whens[0][:10] if whens else None,
            'to': whens[-1][:10] if whens else None,
        },
        'cards_drawn': total_cards,
        'reversed_count': reversed_count,
        'reversal_rate': round(reversed_count / total_cards * 100, 1) if total_cards else 0.0,
        'distinct_cards': len(card_counts),
        'entries_this_month': this_month,
        'entries_prev_month': prev_month,
        'top_cards': [
            {'name': n, 'count': c} for n, c in card_counts.most_common(14)
        ],
        'cadence': cadence,
        'suits': [
            {'suit': s, 'count': c} for s, c in suit_counts.most_common()
        ],
        'top_reversed_position': top_pos,
        'deck_usage': [
            {'name': n, 'count': c, 'last_used': (deck_last.get(n) or '')[:10] or None}
            for n, c in deck_usage.most_common(8)
        ],
        'spread_usage': [
            {'name': n, 'count': c, 'last_used': (spread_last.get(n) or '')[:10] or None}
            for n, c in spread_usage.most_common(8)
        ],
        'co_occurrence': [
            {'a': a, 'b': b, 'count': c}
            for (a, b), c in pair_counts.most_common(10)
            if c >= MIN_PAIR_COUNT
        ],
        # Hidden while a querent filter narrows to one person.
        'querent_breakdown': [] if querent_id else [
            {
                'name': n,
                'entries': c,
                'top_cards': [name for name, _ in querent_cards[n].most_common(3)],
            }
            for n, c in querent_entries.most_common(6)
        ],
    })
