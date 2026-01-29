/** TypeScript interfaces matching the database schema */

export interface CartomancyType {
  id: number;
  name: string;
}

export interface Deck {
  id: number;
  name: string;
  cartomancy_type_id: number;
  image_folder: string | null;
  suit_names: string | null;
  court_names: string | null;
  date_published: string | null;
  publisher: string | null;
  credits: string | null;
  notes: string | null;
  card_back_image: string | null;
  booklet_info: string | null;
  created_at: string;
  // Joined fields from get_deck():
  cartomancy_type?: string;
  /** Array of all cartomancy types this deck belongs to */
  cartomancy_types?: { id: number; name: string }[];
  card_count?: number;
  tags?: Tag[];
}

export interface Card {
  id: number;
  deck_id: number;
  name: string;
  image_path: string | null;
  card_order: number;
  archetype: string | null;
  rank: string | null;
  suit: string | null;
  notes: string | null;
  custom_fields: string | null;
  // Joined fields:
  deck_name?: string;
  cartomancy_type?: string;
}

/** A deck slot defines one deck type used in a spread */
export interface DeckSlot {
  /** Unique key for this slot (e.g., "A", "B", "1", "2") */
  key: string;
  /** The cartomancy type required for this slot */
  cartomancy_type: string;
  /** Optional display label (e.g., "Main Deck", "Oracle") */
  label?: string;
}

export interface Spread {
  id: number;
  name: string;
  description: string | null;
  positions: SpreadPosition[] | string;
  cartomancy_type: string | null;
  allowed_deck_types: string[] | string | null;
  default_deck_id: number | null;
  /** Deck slots for multi-deck spreads */
  deck_slots?: DeckSlot[] | string;
  created_at: string;
}

export interface SpreadPosition {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  key?: string;
  rotated?: boolean;
  /** Which deck slot this position uses (references DeckSlot.key) */
  deck_slot?: string;
}

export interface JournalEntry {
  id: number;
  title: string | null;
  content: string | null;
  created_at: string;
  updated_at: string;
  reading_datetime: string | null;
  location_name: string | null;
  location_lat: number | null;
  location_lon: number | null;
  querent_id: number | null;
  reader_id: number | null;
}

export interface EntryReading {
  id: number;
  entry_id: number;
  spread_id: number | null;
  spread_name: string | null;
  deck_id: number | null;
  deck_name: string | null;
  cartomancy_type: string | null;
  cards_used: string | null;
  position_order: number;
}

/** A card placed in a reading (parsed from cards_used JSON) */
export interface CardUsed {
  name: string;
  reversed?: boolean;
  deck_id?: number;
  deck_name?: string;
  position_index?: number;
  card_id?: number;
}

/** EntryReading with cards_used parsed from JSON string to typed array */
export interface EntryReadingParsed {
  id: number;
  entry_id: number;
  spread_id: number | null;
  spread_name: string | null;
  deck_id: number | null;
  deck_name: string | null;
  cartomancy_type: string | null;
  cards_used: CardUsed[];
  position_order: number;
}

/** Follow-up note on a journal entry */
export interface FollowUpNote {
  id: number;
  entry_id: number;
  content: string;
  created_at: string;
}

/** Full journal entry as returned by GET /api/entries/<id> */
export interface JournalEntryFull extends JournalEntry {
  readings: EntryReadingParsed[];
  tags: Tag[];
  follow_up_notes: FollowUpNote[];
  querent_name: string | null;
  reader_name: string | null;
}

export interface Profile {
  id: number;
  name: string;
  gender: string | null;
  birth_date: string | null;
  birth_time: string | null;
  birth_place_name: string | null;
  birth_place_lat: number | null;
  birth_place_lon: number | null;
  querent_only: boolean;
  created_at: string;
}

export interface Tag {
  id: number;
  name: string;
  color: string;
}

export interface DeckCustomField {
  id: number;
  deck_id: number;
  field_name: string;
  field_type: string;
  field_options: string | null;
  field_order: number;
}

export interface CardGroup {
  id: number;
  deck_id: number;
  name: string;
  color: string;
  sort_order: number;
}

export interface ThemeColors {
  bg_primary: string;
  bg_secondary: string;
  bg_tertiary: string;
  bg_input: string;
  accent: string;
  accent_hover: string;
  accent_dim: string;
  text_primary: string;
  text_secondary: string;
  text_dim: string;
  border: string;
  success: string;
  warning: string;
  danger: string;
  card_slot: string;
}

export interface ThemeFonts {
  family_display: string;
  family_text: string;
  family_mono: string;
  size_title: number;
  size_heading: number;
  size_body: number;
  size_small: number;
}

export interface Theme {
  colors: ThemeColors;
  fonts: ThemeFonts;
}
