"""Card sorting and categorization methods for different cartomancy types."""

import re

from card_metadata import (
    LENORMAND_SUIT_MAP,
    MAJOR_ARCANA_ORDER,
    TAROT_SUIT_BASES,
    TAROT_SUIT_ALIASES,
    TAROT_RANK_ORDER,
    get_playing_card_sort_key,
)


class CardSortingMixin:
    """Mixin providing card sorting and categorization methods."""

    def _sort_lenormand_cards(self, cards):
        """Sort Lenormand cards by card_order field (set during import/auto-assign).
        Fallback: traditional order (1-36) based on card name."""
        # Map card names to their traditional order (for fallback)
        lenormand_order = {
            'rider': 1, 'clover': 2, 'ship': 3, 'house': 4, 'tree': 5,
            'clouds': 6, 'snake': 7, 'coffin': 8, 'bouquet': 9, 'flowers': 9,
            'scythe': 10, 'whip': 11, 'broom': 11, 'birds': 12, 'owls': 12,
            'child': 13, 'fox': 14, 'bear': 15, 'stars': 16, 'stork': 17,
            'dog': 18, 'tower': 19, 'garden': 20, 'mountain': 21,
            'crossroads': 22, 'paths': 22, 'mice': 23, 'heart': 24,
            'ring': 25, 'book': 26, 'letter': 27, 'man': 28, 'gentleman': 28,
            'woman': 29, 'lady': 29, 'lily': 30, 'lilies': 30, 'sun': 31,
            'moon': 32, 'key': 33, 'fish': 34, 'anchor': 35, 'cross': 36,
        }

        def get_lenormand_order(card):
            # Primary: use card_order if set (not 0 or None)
            try:
                card_order = card['card_order']
                if card_order is not None and card_order != 0:
                    return card_order
            except (KeyError, TypeError):
                pass

            # Fallback: parse card name
            name = card['name'].lower().strip()
            # Direct lookup
            if name in lenormand_order:
                return lenormand_order[name]
            # Try to extract number from name if present
            match = re.match(r'^(\d+)', name)
            if match:
                return int(match.group(1))
            return 999

        return sorted(cards, key=get_lenormand_order)

    def _sort_kipper_cards(self, cards):
        """Sort Kipper cards by card_order field (1-36).
        Fallback: traditional order based on card name."""
        kipper_order = {
            'main male': 1, 'hauptperson': 1,
            'main female': 2,
            'marriage': 3, 'union': 3,
            'meeting': 4, 'rendezvous': 4,
            'good gentleman': 5, 'good man': 5,
            'good lady': 6, 'good woman': 6,
            'pleasant letter': 7, 'good news': 7,
            'false person': 8, 'falsity': 8,
            'a change': 9, 'change': 9,
            'a journey': 10, 'journey': 10, 'travel': 10,
            'gain money': 11, 'win money': 11, 'wealth': 11,
            'rich girl': 12, 'wealthy girl': 12,
            'rich man': 13, 'wealthy man': 13,
            'sad news': 14, 'bad news': 14,
            'success in love': 15, 'love success': 15,
            'his thoughts': 16, 'her thoughts': 16, 'thoughts': 16,
            'a gift': 17, 'gift': 17, 'present': 17,
            'a small child': 18, 'small child': 18, 'child': 18,
            'a funeral': 19, 'funeral': 19, 'death': 19,
            'house': 20, 'home': 20,
            'living room': 21, 'parlor': 21, 'room': 21,
            'official person': 22, 'military': 22, 'official': 22,
            'court house': 23, 'courthouse': 23,
            'theft': 24, 'thief': 24, 'stealing': 24,
            'high honors': 25, 'honor': 25, 'achievement': 25,
            'great fortune': 26, 'fortune': 26, 'luck': 26,
            'unexpected money': 27, 'surprise': 27,
            'expectation': 28, 'hope': 28, 'waiting': 28,
            'prison': 29, 'confinement': 29, 'jail': 29,
            'court': 30, 'legal': 30, 'judge': 30, 'judiciary': 30,
            'short illness': 31, 'illness': 31, 'sickness': 31,
            'grief and adversity': 32, 'grief': 32, 'adversity': 32, 'sorrow': 32,
            'gloomy thoughts': 33, 'sadness': 33, 'melancholy': 33,
            'work': 34, 'employment': 34, 'occupation': 34, 'labor': 34,
            'a long way': 35, 'long way': 35, 'long road': 35, 'distance': 35,
            'hope, great water': 36, 'great water': 36, 'water': 36, 'ocean': 36,
        }

        def get_kipper_order(card):
            # Primary: use card_order if set (not 0, 999, or None)
            try:
                card_order = card['card_order']
                if card_order is not None and card_order != 0 and card_order != 999:
                    return card_order
            except (KeyError, TypeError):
                pass

            # Fallback: parse card name
            name = card['name'].lower().strip()
            # Sort by key length to match longer names first
            for key in sorted(kipper_order.keys(), key=len, reverse=True):
                if key in name:
                    return kipper_order[key]
            # Try to extract number from name if present
            match = re.match(r'^(\d+)', name)
            if match:
                return int(match.group(1))
            return 999

        return sorted(cards, key=get_kipper_order)

    def _sort_playing_cards(self, cards, suit_names):
        """Sort playing cards by card_order field (set by import/auto-assign).
        Order: Jokers first, then Spades, Hearts, Clubs, Diamonds (2-A within each suit)"""

        def get_sort_key(card):
            # Primary: use card_order if set
            try:
                card_order = card['card_order'] if card['card_order'] is not None else 999
            except (KeyError, TypeError):
                card_order = 999
            if card_order != 999:
                return card_order

            # Fallback: use shared parsing function
            return get_playing_card_sort_key(card['name'].lower())

        return sorted(cards, key=get_sort_key)

    def _sort_cards(self, cards, suit_names):
        """Sort cards by card_order field (set during import/auto-assign).
        Fallback: Major Arcana first (Fool-World), then Wands, Cups, Swords, Pentacles (Ace-King)"""

        # Build suit order including custom suit names
        suit_order = dict(TAROT_SUIT_BASES)  # Start with canonical bases
        # Add custom suit names if provided
        for key, base in [('wands', 100), ('cups', 200), ('swords', 300), ('pentacles', 400)]:
            custom = suit_names.get(key, '').lower()
            if custom:
                suit_order[custom] = base
        # Add lowercase canonical names and common aliases
        for alias, canonical in TAROT_SUIT_ALIASES.items():
            suit_order[alias] = TAROT_SUIT_BASES[canonical]

        def get_sort_key(card):
            # Primary: use card_order if set (not 0 or None)
            try:
                card_order = card['card_order']
                if card_order is not None and card_order != 0:
                    return (0, card_order, 0)
            except (KeyError, TypeError):
                pass

            # Fallback: parse card name
            name_lower = card['name'].lower()

            # Check if it's a major arcana
            if name_lower in MAJOR_ARCANA_ORDER:
                return (0, MAJOR_ARCANA_ORDER[name_lower], 0)

            # Check for suit cards
            for suit_name, suit_val in suit_order.items():
                if f'of {suit_name}' in name_lower:
                    # Find rank
                    for rank, rank_val in TAROT_RANK_ORDER.items():
                        if name_lower.startswith(rank):
                            return (1, suit_val, rank_val)
                    return (1, suit_val, 50)  # Unknown rank

            # Unknown card - put at end but preserve relative order
            return (2, 999, 0)

        return sorted(cards, key=get_sort_key)

    def _categorize_lenormand_cards(self, cards):
        """Categorize Lenormand cards by their traditional playing card suit associations"""
        categorized = {
            'Hearts': [],
            'Diamonds': [],
            'Clubs': [],
            'Spades': [],
        }

        for card in cards:
            name = card['name'].lower().strip()
            suit = LENORMAND_SUIT_MAP.get(name)
            if suit:
                categorized[suit].append(card)

        return categorized

    def _categorize_playing_cards(self, cards, suit_names):
        """Categorize playing cards by suit"""

        # Build suit name variations for matching
        suit_variations = {
            'Hearts': [suit_names.get('hearts', 'Hearts').lower(), 'hearts', 'heart'],
            'Diamonds': [suit_names.get('diamonds', 'Diamonds').lower(), 'diamonds', 'diamond'],
            'Clubs': [suit_names.get('clubs', 'Clubs').lower(), 'clubs', 'club'],
            'Spades': [suit_names.get('spades', 'Spades').lower(), 'spades', 'spade'],
        }

        categorized = {
            'Hearts': [],
            'Diamonds': [],
            'Clubs': [],
            'Spades': [],
        }

        for card in cards:
            name_lower = card['name'].lower()

            # Skip jokers - they don't belong to any suit
            if 'joker' in name_lower:
                continue

            for suit_key, variations in suit_variations.items():
                if any(var in name_lower for var in variations):
                    categorized[suit_key].append(card)
                    break

        return categorized

    def _categorize_cards(self, cards, suit_names):
        """Categorize cards into Major Arcana and suits"""
        # Check if this is a Gnostic/Eternal Tarot deck
        is_gnostic = any(card['suit'] == 'Minor Arcana' for card in cards)

        if is_gnostic:
            # Gnostic/Eternal Tarot: categorize by suit field (Major Arcana / Minor Arcana)
            categorized = {
                'Major Arcana': [],
                'Minor Arcana': [],
            }
            for card in cards:
                suit = card['suit'] or ''
                if suit == 'Major Arcana':
                    categorized['Major Arcana'].append(card)
                elif suit == 'Minor Arcana':
                    categorized['Minor Arcana'].append(card)
            return categorized

        # Standard Tarot categorization
        categorized = {
            'Major Arcana': [],
            'Wands': [],
            'Cups': [],
            'Swords': [],
            'Pentacles': [],
        }

        # Map suit names to category keys
        suit_map = {
            suit_names.get('wands', 'Wands').lower(): 'Wands',
            suit_names.get('cups', 'Cups').lower(): 'Cups',
            suit_names.get('swords', 'Swords').lower(): 'Swords',
            suit_names.get('pentacles', 'Pentacles').lower(): 'Pentacles',
            'wands': 'Wands', 'cups': 'Cups', 'swords': 'Swords',
            'pentacles': 'Pentacles', 'coins': 'Pentacles', 'disks': 'Pentacles',
        }

        major_arcana_names = {
            'the fool', 'fool', 'the magician', 'magician', 'the magus', 'magus',
            'the high priestess', 'high priestess', 'the priestess', 'priestess',
            'the empress', 'empress', 'the emperor', 'emperor',
            'the hierophant', 'hierophant', 'the lovers', 'lovers', 'the chariot',
            'chariot', 'strength', 'lust', 'the hermit', 'hermit', 'wheel of fortune',
            'the wheel', 'wheel', 'fortune', 'justice', 'adjustment', 'the hanged man', 'hanged man',
            'death', 'temperance', 'art', 'the devil', 'devil', 'the tower', 'tower',
            'the star', 'star', 'the moon', 'moon', 'the sun', 'sun',
            'judgement', 'judgment', 'the aeon', 'aeon', 'the world', 'world', 'the universe', 'universe'
        }

        for card in cards:
            name_lower = card['name'].lower()
            card_suit = card['suit'].lower() if card['suit'] else ''

            # First check the suit field directly
            if card_suit == 'major arcana':
                categorized['Major Arcana'].append(card)
                continue

            # Check if suit field matches a tarot suit
            if card_suit in suit_map:
                categorized[suit_map[card_suit]].append(card)
                continue

            # Fallback: Check major arcana by name
            if name_lower in major_arcana_names:
                categorized['Major Arcana'].append(card)
                continue

            # Check suits by name pattern
            found = False
            for suit_name, category in suit_map.items():
                if f'of {suit_name}' in name_lower:
                    categorized[category].append(card)
                    found = True
                    break

            # If not found, try to detect from numbered cards or other patterns
            if not found:
                # Could be a court card with different naming
                pass

        return categorized
