#!/usr/bin/env python3
"""
Repair script for corrupted card names.

This script fixes card names that were corrupted by buggy suit rename operations.
It detects common corruption patterns and restores canonical suit names.
"""

import sqlite3
import re
import sys
from pathlib import Path

# Standard tarot suit names
CANONICAL_SUITS = ['Wands', 'Cups', 'Swords', 'Pentacles']

# Known corruption patterns -> correct suit
# These patterns match corrupted suit names at the end of card names
CORRUPTION_PATTERNS = [
    # Cups corruptions
    (r'Airups$', 'Cups'),
    (r'Fireirups$', 'Cups'),
    (r'irups$', 'Cups'),
    (r'ups$', 'Cups'),  # Catch partial "ups" if nothing else matches

    # Add more patterns here as they're discovered
]


def get_db_path():
    """Find the database path."""
    # Try common locations
    candidates = [
        Path.home() / '.tarot_journal' / 'tarot_journal.db',
        Path(__file__).parent.parent / 'tarot_journal.db',
        Path(__file__).parent.parent / 'data' / 'tarot_journal.db',
    ]

    for path in candidates:
        if path.exists():
            return path

    return None


def analyze_deck(conn, deck_id):
    """Analyze a deck for corrupted card names."""
    cursor = conn.cursor()

    # Get all cards for this deck
    cursor.execute('SELECT id, name FROM cards WHERE deck_id = ?', (deck_id,))
    cards = cursor.fetchall()

    # Major Arcana cards that contain "of" but aren't suited cards
    MAJOR_ARCANA_EXCEPTIONS = [
        'Wheel of Fortune',
    ]

    corrupted = []
    for card_id, card_name in cards:
        # Skip known Major Arcana cards
        if card_name in MAJOR_ARCANA_EXCEPTIONS:
            continue

        # Check if the card name ends with a known canonical suit
        has_canonical_suit = any(card_name.endswith(f'of {suit}') for suit in CANONICAL_SUITS)

        if not has_canonical_suit and ' of ' in card_name:
            # This card might have a corrupted suit name
            corrupted.append((card_id, card_name))

    return corrupted


def suggest_fix(card_name):
    """Suggest a fix for a corrupted card name."""
    for pattern, correct_suit in CORRUPTION_PATTERNS:
        if re.search(pattern, card_name):
            # Replace the corrupted ending with the correct suit
            fixed = re.sub(r' of \S+$', f' of {correct_suit}', card_name)
            return fixed, correct_suit

    return None, None


def repair_deck(conn, deck_id, dry_run=True):
    """Repair corrupted card names in a deck."""
    corrupted = analyze_deck(conn, deck_id)

    if not corrupted:
        print(f"No corrupted card names found in deck {deck_id}")
        return 0

    print(f"\nFound {len(corrupted)} potentially corrupted cards in deck {deck_id}:")
    print("-" * 60)

    repairs = []
    for card_id, card_name in corrupted:
        fixed_name, suit = suggest_fix(card_name)
        if fixed_name:
            repairs.append((card_id, card_name, fixed_name))
            print(f"  '{card_name}' -> '{fixed_name}'")
        else:
            print(f"  '{card_name}' (no automatic fix available)")

    if not repairs:
        print("\nNo automatic repairs available.")
        return 0

    if dry_run:
        print(f"\n[DRY RUN] Would repair {len(repairs)} cards.")
        print("Run with --apply to actually make changes.")
        return len(repairs)

    # Apply repairs
    cursor = conn.cursor()
    for card_id, old_name, new_name in repairs:
        cursor.execute('UPDATE cards SET name = ? WHERE id = ?', (new_name, card_id))

    conn.commit()
    print(f"\nRepaired {len(repairs)} cards.")
    return len(repairs)


def reset_to_canonical(conn, deck_id, dry_run=True):
    """Reset all suited cards back to canonical suit names (Wands, Cups, Swords, Pentacles)."""
    cursor = conn.cursor()

    # Get deck's suit_names to understand current naming
    cursor.execute('SELECT suit_names FROM decks WHERE id = ?', (deck_id,))
    row = cursor.fetchone()

    print(f"\nResetting deck {deck_id} to canonical suit names...")

    # Get all cards
    cursor.execute('SELECT id, name FROM cards WHERE deck_id = ?', (deck_id,))
    cards = cursor.fetchall()

    repairs = []
    for card_id, card_name in cards:
        if ' of ' not in card_name:
            continue

        # Check if it already has a canonical suit
        has_canonical = any(card_name.endswith(f'of {suit}') for suit in CANONICAL_SUITS)
        if has_canonical:
            continue

        # Try to determine which suit this should be based on position in deck
        # or use pattern matching
        fixed_name, _ = suggest_fix(card_name)
        if fixed_name:
            repairs.append((card_id, card_name, fixed_name))

    if not repairs:
        print("No cards need repair.")
        return 0

    print(f"\nWill repair {len(repairs)} cards:")
    for card_id, old_name, new_name in repairs:
        print(f"  '{old_name}' -> '{new_name}'")

    if dry_run:
        print(f"\n[DRY RUN] Would repair {len(repairs)} cards.")
        return len(repairs)

    for card_id, old_name, new_name in repairs:
        cursor.execute('UPDATE cards SET name = ? WHERE id = ?', (new_name, card_id))

    conn.commit()
    print(f"\nRepaired {len(repairs)} cards.")

    # Also reset the deck's suit_names to canonical
    import json
    canonical_suit_names = {
        'wands': 'Wands',
        'cups': 'Cups',
        'swords': 'Swords',
        'pentacles': 'Pentacles'
    }
    cursor.execute('UPDATE decks SET suit_names = ? WHERE id = ?',
                   (json.dumps(canonical_suit_names), deck_id))
    conn.commit()
    print("Reset deck suit_names to canonical values.")

    return len(repairs)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Repair corrupted card names in tarot journal database')
    parser.add_argument('--deck-id', type=int, default=75, help='Deck ID to repair (default: 75)')
    parser.add_argument('--db', type=str, help='Path to database file')
    parser.add_argument('--apply', action='store_true', help='Actually apply repairs (default is dry run)')
    parser.add_argument('--reset-canonical', action='store_true',
                        help='Reset all suits to canonical names (Wands, Cups, Swords, Pentacles)')
    parser.add_argument('--list-cards', action='store_true', help='List all cards in deck')

    args = parser.parse_args()

    # Find database
    if args.db:
        db_path = Path(args.db)
    else:
        db_path = get_db_path()

    if not db_path or not db_path.exists():
        print(f"Error: Could not find database. Use --db to specify path.")
        print(f"Tried: {db_path}")
        sys.exit(1)

    print(f"Using database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if args.list_cards:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM cards WHERE deck_id = ? ORDER BY id', (args.deck_id,))
            print(f"\nCards in deck {args.deck_id}:")
            for row in cursor.fetchall():
                print(f"  {row['id']}: {row['name']}")
            return

        if args.reset_canonical:
            reset_to_canonical(conn, args.deck_id, dry_run=not args.apply)
        else:
            repair_deck(conn, args.deck_id, dry_run=not args.apply)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
