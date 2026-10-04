/** TypeScript interfaces matching the database schema */

export interface CartomancyType {
  id: number;
  name: string;
  /** Built-ins are re-seeded on startup; only custom types can be
   *  renamed or deleted. */
  builtin?: boolean;
}

export interface Deck {
  id: number;
  name: string;
  cartomancy_type_id?: number;
  image_folder: string | null;
  suit_names: string | null;
  court_names: string | null;
  date_published: string | null;
  publisher: string | null;
  credits: string | null;
  notes: string | null;
  card_back_image: string | null;
  booklet_info: string | null;
  correspondence_system_id: number | null;
  /** Favorited decks are the subset synced to the phone companion. */
  favorite?: number;
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
  /** Within-name-group ordering for the reading editor's variant picker.
   *  Independent of card_order so users can reorder same-name variants
   *  without disturbing deck display order. Null = use insertion order. */
  variant_order: number | null;
  archetype: string | null;
  rank: string | null;
  suit: string | null;
  notes: string | null;
  custom_fields: string | null;
  // Joined fields:
  deck_name?: string;
  cartomancy_type?: string;
}

/** A deck slot defines the deck type(s) allowed in a spread position */
export interface DeckSlot {
  /** Unique key for this slot (e.g., "A", "B", "1", "2") */
  key: string;
  /** Legacy single-type field ('Any' or one type name). Kept in sync
   *  when possible so older data/readers stay coherent; new code
   *  should go through slotTypes() in utils/formatting instead. */
  cartomancy_type?: string;
  /** The cartomancy types allowed for this slot. Empty/missing with
   *  no legacy value means any type is allowed. */
  cartomancy_types?: string[];
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
  /** 0/1 — archived spreads are hidden from pickers and tucked into
   *  the list's Archived group; never deleted (old entries keep
   *  rendering with them). */
  archived?: number;
  /** Reference source the spread is attributed to. */
  source_id?: number | null;
  source_name?: string | null;
  /** Spread tags (own namespace, like deck tags) — attached by the list endpoint. */
  tags?: Tag[];
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
  /** Controls visual stacking order (higher = on top). Defaults to array index. */
  z_index?: number;
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
  /** JSON-encoded BreakdownSettings; null until first save. */
  breakdown_settings: string | null;
}

/** Per-entry UI state for the Reading Breakdown panel. */
export interface BreakdownSettings {
  /** Whether the panel is expanded. */
  open: boolean;
  /** Last-viewed tab — "all" for the aggregate, otherwise an EntryReading.id. */
  last_tab: 'all' | number;
  /** Per-correspondence-type visibility toggles. Missing keys default to true. */
  visible: Record<string, boolean>;
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
  /** Per-reading notes — used when an entry holds several readings. */
  notes: string | null;
}

/** A card placed in a reading (parsed from cards_used JSON) */
export interface CardUsed {
  name: string;
  reversed?: boolean;
  deck_id?: number;
  deck_name?: string;
  position_index?: number;
  card_id?: number;
  /** For extra cards beyond the spread's positions: the position
   *  index this card clarifies (undefined = plain additional card) */
  clarifies?: number;
  /** Current name from database (if card was renamed after entry was created) */
  current_name?: string;
  // Enriched server-side for the Reading Breakdown when card_id resolves:
  archetype?: string | null;
  rank?: string | null;
  suit?: string | null;
  cartomancy_type?: string | null;
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
  notes: string | null;
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
  /** Multiple querents for this entry */
  querents: Profile[];
  /** Legacy single querent name (first querent, for backwards compatibility) */
  querent_name: string | null;
  reader_name: string | null;
}

export interface Profile {
  id: number;
  name: string;
  /** Full birth name — feeds the name-cards calculator. */
  full_name?: string | null;
  gender: string | null;
  birth_date: string | null;
  birth_time: string | null;
  birth_place_name: string | null;
  birth_place_lat: number | null;
  birth_place_lon: number | null;
  querent_only: boolean;
  hidden: boolean;
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

export interface CorrespondenceSystem {
  id: number;
  name: string;
  description: string | null;
  is_builtin: boolean;
  cartomancy_type: string | null;
  naming_style: string | null;
  archetype_count?: number;
  assignment_count?: number;
  created_at: string;
}

export interface CorrespondenceAssignment {
  id: number;
  system_id: number;
  archetype_id: number;
  archetype_name: string;
  cartomancy_type: string;
  rank: string | null;
  suit: string | null;
  card_type: string | null;
  field_name: string;
  field_value: string;
  source_group: string | null;
}

export interface ResolvedCorrespondence {
  field_name: string;
  value: string | null;
  values: string[];
  source: 'override' | 'deck-override' | 'inherited' | 'none';
}

export const CORRESPONDENCE_FIELDS = [
  'element', 'planet', 'zodiac_sign', 'decan',
  'hebrew_letter', 'numerology', 'rune', 'i_ching_hexagram',
  'chakra', 'modality', 'astrological_house',
] as const;

export const CORRESPONDENCE_FIELD_LABELS: Record<string, string> = {
  element: 'Element',
  planet: 'Planet',
  zodiac_sign: 'Zodiac Sign',
  decan: 'Decan',
  hebrew_letter: 'Kabbalah',
  numerology: 'Numerology',
  rune: 'Rune',
  i_ching_hexagram: 'I Ching Hexagram',
  chakra: 'Chakra',
  modality: 'Modality',
  astrological_house: 'Astrological House',
};

// === Reference Sources ===
// Each source is typed (cartomancy_type) and implicitly grants every
// archetype of that type a "field" under the source. Per-cell content
// lives in archetype_source_entries.

export interface ReferenceSource {
  id: number;
  name: string;
  /** Every cartomancy type this source covers. A single source can
   *  belong to multiple types; the field set is then scoped per type
   *  via SourceField.cartomancy_type. */
  cartomancy_types: string[];
  /** Free-text author names; multi-author supported. */
  authors: string[];
  created_at: string;
}

/** A field defined on a reference source (e.g. "Upright Meaning").
 *  Each field is scoped to one cartomancy type within its source so a
 *  cross-type source can have different field sets per deck type. */
export interface SourceField {
  id: number;
  source_id: number;
  cartomancy_type: string;
  name: string;
  sort_order: number;
  /** Backend stores this as 0/1 — JSON-serialise as a number. The UI
   *  treats it as boolean. Marks the field as one the Archetype Notes
   *  editor should render with a chevron disclosure (collapsed by
   *  default) so long-form fields don't fill the page. */
  collapsible: number;
  created_at: string;
}

/** Hydrated for the Archetypes viewer — one row per non-empty
 *  (archetype, source-field) cell the active archetype owns. */
export interface ArchetypeSourceEntry {
  entry_id: number;
  archetype_id: number;
  field_id: number;
  content: string;
  updated_at: string;
  field_name: string;
  field_sort_order: number;
  field_cartomancy_type: string;
  /** 0/1 — fields marked collapsible render behind a disclosure,
   *  collapsed by default, so long-form fields don't fill the page. */
  field_collapsible?: number;
  source_id: number;
  source_name: string;
}

/** Hydrated for the Settings authoring page — one row per (archetype,
 *  field) cell that has content under a source. */
export interface SourceAuthoringEntry {
  entry_id: number;
  archetype_id: number;
  field_id: number;
  content: string;
  updated_at: string;
  field_name: string;
  field_sort_order: number;
  field_cartomancy_type: string;
  archetype_name: string;
  archetype_rank: string | null;
}

// === Combinations ===

export interface CombinationMeaning {
  id: number;
  combination_id: number;
  meaning: string;
  source_id: number | null;
  source_name: string | null;
  sort_order: number;
  created_at: string;
  // Hydrated by the meanings-list endpoint:
  cartomancy_type?: string;
  archetype_1_id?: number;
  archetype_2_id?: number;
  archetype_1_name?: string;
  archetype_2_name?: string;
  /** 0/1 — reversal flags are part of the combination's identity. */
  archetype_1_reversed?: number;
  archetype_2_reversed?: number;
  /** Third card (null = two-card combination). */
  archetype_3_id?: number | null;
  archetype_3_name?: string | null;
  archetype_3_reversed?: number;
}

// === Archetype Languages ===

export interface ArchetypeLanguage {
  id: number;
  name: string;
  sort_order: number;
  created_at: string;
}

export interface ArchetypeLanguageName {
  id: number;
  archetype_id: number;
  language_id: number;
  name: string;
  romanization: string | null;
  ipa: string | null;
  sort_order: number;
  created_at: string;
  language_name: string;
  language_sort_order: number;
  /** Present only on the per-cartomancy-type fetch. */
  archetype_name?: string;
  archetype_rank?: string | null;
}

// (ArchetypeNoteField + ArchetypeNoteEntry retired — the Notes tab now
// shows ArchetypeSourceEntry rows from the source-as-typed-field model.)

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
  /** Stored server-side but not applied — the palette is fixed CSS. */
  colors?: ThemeColors;
  fonts: ThemeFonts;
}
