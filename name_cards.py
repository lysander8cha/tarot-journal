"""
Name card calculator — Mary K. Greer's system from *Archetypal Tarot*
(2021), Ch. 17, per the spec in greer-name-cards-spec.md.

Companion to birth_cards.py, whose reduce_to_22 and CONSTELLATIONS are
reused (never reimplemented). The arithmetic here is trivial; the work
is normalization and classification, and every judgment call the source
leaves open (Y handling, suffixes, diacritics) is surfaced in the
output rather than silently applied.

Input is an ORDERED LIST of name parts — never a joined string. The
caller (UI) may suggest a whitespace split, but the user confirms it;
this module refuses to guess.

The strings "destiny card" / "destiny_card" are deliberately absent:
that phrase means three different things across the source's own
bibliography. The cards here are theme_note, rhythm, and melody.
"""

from __future__ import annotations

import unicodedata

from birth_cards import CONSTELLATIONS, reduce_to_22

# === The alphabet (Key Numbers) ===

# Latin alphabet in learned order onto Majors 1-22. W/X/Y/Z are
# nominally 23-26 but Greer is explicit that only the reduced values
# 5/6/7/8 ever enter arithmetic — hard-coded, never computed.
KEY_NUMBERS = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
    'I': 9, 'J': 10, 'K': 11, 'L': 12, 'M': 13, 'N': 14, 'O': 15,
    'P': 16, 'Q': 17, 'R': 18, 'S': 19, 'T': 20, 'U': 21, 'V': 22,
    'W': 5, 'X': 6, 'Y': 7, 'Z': 8,
}

# Paul Foster Case's musical attributions (Golden Dawn lineage).
# Swappable by design — Greer invites substituting other systems.
CASE_NOTES = {
    'A': 'E', 'B': 'G#', 'C': 'F#', 'D': 'C', 'E': 'C#', 'F': 'D',
    'G': 'D#', 'H': 'E', 'I': 'F', 'J': 'A#', 'K': 'F#', 'L': 'G#',
    'M': 'G', 'N': 'G#', 'O': 'A', 'P': 'C', 'Q': 'A#', 'R': 'B',
    'S': 'D', 'T': 'C', 'U': 'A', 'V': 'E', 'W': 'C#', 'X': 'D',
    'Y': 'D#', 'Z': 'E',
}

PLAIN_VOWELS = set('AEIOU')
GENERATIONAL_SUFFIXES = {'JR', 'SR', 'II', 'III', 'IV'}
Y_MODES = ('heuristic', 'always_vowel', 'always_consonant')
ROLES = ('first', 'middle', 'last')

# Characters silently dropped during normalization (spec §1.3).
_DROPPED_CHARS = set("'’.- ")


def digital_root(n: int) -> int:
    """Standard 1-9 reduction. Distinct from reduce_to_22:
    digital_root(21) == 3 while reduce_to_22(21) == 21."""
    return (n - 1) % 9 + 1


# === Normalization (spec §1) ===

def normalize_part(part: str) -> tuple[str, bool]:
    """Uppercase, strip diacritics via NFD, drop punctuation. Returns
    (normalized, diacritics_stripped). Rejects non-Latin scripts with
    a clear error — Greer's argument for the mapping rests on the
    learned Latin alphabet order, so transliteration would silently
    discard the method's own justification."""
    upper = part.upper()
    decomposed = unicodedata.normalize('NFD', upper)
    stripped = ''.join(ch for ch in decomposed
                       if not unicodedata.combining(ch))
    had_diacritics = stripped != upper
    kept = []
    for ch in stripped:
        if ch in _DROPPED_CHARS:
            continue
        if 'A' <= ch <= 'Z':
            kept.append(ch)
        else:
            raise ValueError(
                f'"{part}" contains {ch!r}, which is not a Latin letter. '
                'Name cards are defined only for Latin-alphabet names — '
                "transliterating would discard the system's own rationale."
            )
    return ''.join(kept), had_diacritics


# === Role assignment (spec §1) ===

def assign_roles(count: int) -> list[str]:
    """Default roles for N parts: 3 = first/middle/last; 2 = first/last
    (middle ABSENT, never zero); 1 = mononym (first); 4+ = all interior
    parts are middles, later merged into one."""
    if count == 1:
        return ['first']
    if count == 2:
        return ['first', 'last']
    return ['first'] + ['middle'] * (count - 2) + ['last']


# === Y classification (spec §3) ===

def classify_y(normalized: str, index: int, y_mode: str) -> str:
    """One Y's bucket under the chosen mode. Heuristic: consonant iff
    word-initial or immediately followed by a plain vowel (YVONNE,
    MAYA), else vowel (MARY, KAYLA). Phonetics-adjacent, not phonetics;
    the caller must surface every Y for manual flipping."""
    if y_mode == 'always_vowel':
        return 'vowel'
    if y_mode == 'always_consonant':
        return 'consonant'
    if index == 0:
        return 'consonant'
    if index + 1 < len(normalized) and normalized[index + 1] in PLAIN_VOWELS:
        return 'consonant'
    return 'vowel'


# === The calculator ===

def calculate_name_cards(parts: list[str],
                         roles: list[str] | None = None,
                         y_mode: str = 'heuristic',
                         y_overrides: dict | list | None = None,
                         drop_suffixes: bool = True) -> dict:
    """Full NameCardProfile for an ordered list of name parts.

    y_overrides: {(part_index, letter_index): 'vowel'|'consonant'} or a
    list of {'part': i, 'index': j, 'as': ...} dicts (the JSON form).
    Indices refer to the input parts array and the NORMALIZED letters.
    """
    if not parts or not any(p.strip() for p in parts):
        raise ValueError('At least one name part is required')
    if y_mode not in Y_MODES:
        raise ValueError(f'y_mode must be one of {Y_MODES}')
    if roles is not None:
        if len(roles) != len(parts):
            raise ValueError('roles must parallel parts')
        for r in roles:
            if r not in ROLES:
                raise ValueError(f'Unknown role: {r!r}')

    overrides = {}
    if y_overrides:
        if isinstance(y_overrides, dict):
            overrides = dict(y_overrides)
        else:
            overrides = {(o['part'], o['index']): o['as'] for o in y_overrides}

    # Normalize every part; identify suffix parts.
    normalized_parts = []
    any_diacritics = False
    dropped_suffixes = []
    for i, part in enumerate(parts):
        norm, had = normalize_part(part)
        any_diacritics = any_diacritics or had
        if not norm:
            raise ValueError(f'Name part {i + 1} ({part!r}) has no letters')
        is_suffix = (drop_suffixes and norm in GENERATIONAL_SUFFIXES
                     and len(parts) > 1)
        if is_suffix:
            dropped_suffixes.append(part)
        normalized_parts.append({'original': part, 'normalized': norm,
                                 'input_index': i, 'suffix': is_suffix})

    active = [p for p in normalized_parts if not p['suffix']]
    if not active:
        raise ValueError('Every part was a generational suffix')

    if roles is None:
        default = assign_roles(len(active))
        for p, role in zip(active, default):
            p['role'] = role
    else:
        for p in active:
            p['role'] = roles[p['input_index']]

    # Letter-by-letter classification and sums.
    y_positions = []
    mandala = []
    letter_freq = {}
    constellation_count = {n: 0 for n in range(1, 10)}
    for p in active:
        norm = p['normalized']
        letters = []
        vowel_sum = consonant_sum = 0
        for j, ch in enumerate(norm):
            key = KEY_NUMBERS[ch]
            if ch == 'Y':
                classified = overrides.get(
                    (p['input_index'], j),
                    classify_y(norm, j, y_mode))
                is_vowel = classified == 'vowel'
                y_positions.append({
                    'part': p['input_index'],
                    'index': j,
                    'classified_as': classified,
                    'overridden': (p['input_index'], j) in overrides,
                })
            else:
                is_vowel = ch in PLAIN_VOWELS
            if is_vowel:
                vowel_sum += key
            else:
                consonant_sum += key
            entry = {'letter': ch, 'key': key, 'is_vowel': is_vowel,
                     'note': CASE_NOTES[ch]}
            letters.append(entry)
            mandala.append({**entry, 'part': p['input_index']})
            letter_freq[ch] = letter_freq.get(ch, 0) + 1
            constellation_count[digital_root(key)] += 1
        p['letters'] = letters
        p['vowel_sum'] = vowel_sum
        p['consonant_sum'] = consonant_sum
        p['sum'] = vowel_sum + consonant_sum

    # Per-role sums — explicit roles may repeat (two surnames, several
    # middles); parts sharing a role are summed together, matching the
    # spec's 4+-parts rule.
    role_sums = {}
    for p in active:
        role_sums[p['role']] = role_sums.get(p['role'], 0) + p['sum']

    def role_card(role):
        return reduce_to_22(role_sums[role]) if role in role_sums else None

    first_card = role_card('first')
    middle_card = role_card('middle')   # None when absent — NEVER zero
    last_card = role_card('last')
    theme_chord = [first_card, middle_card, last_card]

    all_vowels = sum(p['vowel_sum'] for p in active)
    all_consonants = sum(p['consonant_sum'] for p in active)
    all_letters = all_vowels + all_consonants

    # A sum of 0 (an all-consonant or all-vowel name) yields no card —
    # absent, never card zero, matching the missing-middle rule.
    desires = reduce_to_22(all_vowels) if all_vowels else None
    persona = reduce_to_22(all_consonants) if all_consonants else None
    # The three cards that differ only in WHERE reduction happens:
    theme_note = reduce_to_22(sum(c for c in theme_chord if c is not None))
    rhythm = reduce_to_22(sum(c for c in (desires, persona) if c is not None))
    melody = reduce_to_22(all_letters)

    shared_root = digital_root(melody)
    hidden_factor_name = sorted(
        set(CONSTELLATIONS[shared_root]) - {theme_note, rhythm, melody})

    max_count = max(constellation_count.values())
    most_represented = [n for n, c in constellation_count.items()
                        if c == max_count and c > 0]
    absent = [n for n, c in constellation_count.items() if c == 0]

    first_active = active[0]
    leading = first_active['letters'][0]
    first_vowel = next((entry for entry in mandala if entry['is_vowel']), None)

    return {
        'parts': [{
            'original': p['original'],
            'normalized': p['normalized'],
            'input_index': p['input_index'],
            'role': p['role'],
            'letters': p['letters'],
            'vowel_sum': p['vowel_sum'],
            'consonant_sum': p['consonant_sum'],
            'sum': p['sum'],
        } for p in active],
        'normalized': any_diacritics,
        'dropped_suffixes': dropped_suffixes,
        'y_mode': y_mode,
        'y_positions': y_positions,

        'first_name_card': first_card,
        'middle_name_card': middle_card,
        'last_name_card': last_card,
        'theme_chord': theme_chord,

        'all_vowels': all_vowels,
        'all_consonants': all_consonants,
        'all_letters': all_letters,
        'desires_inner_motivation': desires,
        'outer_persona': persona,
        'theme_note': theme_note,
        'rhythm': rhythm,
        'melody': melody,
        'shared_root': shared_root,
        'hidden_factor_name': hidden_factor_name,

        'constellation_count': constellation_count,
        'most_represented': most_represented,
        'absent': absent,

        'mandala': mandala,
        'max_letter_frequency': max(letter_freq.values()),
        'leading_letter': {'letter': leading['letter'],
                           'key': leading['key'],
                           'is_vowel': leading['is_vowel']},
        'first_vowel': ({'letter': first_vowel['letter'],
                         'key': first_vowel['key']}
                        if first_vowel else None),
        'rhythm_pattern': [
            ''.join('V' if letter['is_vowel'] else 'C'
                    for letter in p['letters'])
            for p in active],
    }


def life_potential(birth_base_number: int, all_letters: int) -> int:
    """The one card combining name and birth date — both inputs
    UNREDUCED: the birth module's four-digit base_number plus the raw
    all-letters total."""
    return reduce_to_22(birth_base_number + all_letters)
