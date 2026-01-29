/**
 * Constants for deck import functionality.
 * These match the Python import_presets.py definitions.
 */

// Court card naming presets for different tarot traditions
export const COURT_PRESETS: Record<string, Record<string, string> | null> = {
  "RWS (Page/Knight/Queen/King)": {
    page: "Page",
    knight: "Knight",
    queen: "Queen",
    king: "King",
  },
  "Thoth (Princess/Prince/Queen/Knight)": {
    page: "Princess",
    knight: "Prince",
    queen: "Queen",
    king: "Knight",
  },
  "Marseille (Valet/Cavalier/Queen/King)": {
    page: "Valet",
    knight: "Cavalier",
    queen: "Queen",
    king: "King",
  },
  "Custom...": null, // null indicates custom entry fields should be shown
};

// How to map card archetypes during import
export const ARCHETYPE_MAPPING_OPTIONS = [
  "Map to RWS archetypes",
  "Map to Thoth archetypes",
  "Create new archetypes",
];

// Suit keys for different deck types
export const TAROT_SUITS = ["wands", "cups", "swords", "pentacles"] as const;
export const PLAYING_SUITS = ["hearts", "diamonds", "clubs", "spades"] as const;

// Default suit names by deck type
export const DEFAULT_SUIT_NAMES: Record<string, Record<string, string>> = {
  Tarot: {
    wands: "Wands",
    cups: "Cups",
    swords: "Swords",
    pentacles: "Pentacles",
  },
  Oracle: {
    wands: "Wands",
    cups: "Cups",
    swords: "Swords",
    pentacles: "Pentacles",
  },
  Lenormand: {
    hearts: "Hearts",
    diamonds: "Diamonds",
    clubs: "Clubs",
    spades: "Spades",
  },
  "Playing Cards": {
    hearts: "Hearts",
    diamonds: "Diamonds",
    clubs: "Clubs",
    spades: "Spades",
  },
};

// Default court card names
export const DEFAULT_COURT_NAMES: Record<string, string> = {
  page: "Page",
  knight: "Knight",
  queen: "Queen",
  king: "King",
};
