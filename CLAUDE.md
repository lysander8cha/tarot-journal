# Tarot Journal - Development Notes




## Project Mission Statement: Tarot Library & Journal App

Core Purpose
A desktop application for serious tarot practitioners to catalog cartomancy decks and maintain a visual reading journal—not to automate or replace the intuitive practice of reading cards.
Primary Functions
Deck Library

Store and organize images and metadata for tarot/cartomancy decks
Robust search and filtering across individual decks or the entire collection
Intuitive, visually pleasing, easily navigable UI

Reading Journal

Log readings with card images arranged visually in their spread layout
Quick entry workflow that produces readable, attractive journal entries for later reference
Associate entries with Querent and Reader profiles

Supporting Data Structures

Spreads: Store 2D positional layouts, position meanings, and spread metadata for visual arrangement in journal entries
User Profiles: Name, birth date/time/place, gender; assignable as Querent or Reader per entry

Planned Future Features

Data visualization: Display trends and patterns across journal entries (customizable)
Export journal entries and data graphs as formatted PDFs
Export reading data in LLM-readable format for analysis
Export decks to Anki-compatible format for SRS study
Import/export for sharing decks, spreads, profiles, and entries between users
Automatic astrological chart retrieval for profiles (natal) and entries (event charts)

Explicit Non-Goals
This app does not aim to:

Replace physical card reading
Serve primarily as a tarot learning tool
Interpret readings or substitute for human intuition in cartomancy


## User Context

- **The user is not a programmer** - explain technical choices and concepts in simple, plain language
- When making changes, briefly explain *why* a particular approach was chosen, not just *what* was done
- Avoid jargon where possible; when technical terms are necessary, provide a brief explanation.
- However, if asked explicitly for a technical explanation, be willing to explain as if to an expert.

## Git Workflow

- **Push automatically after committing** — no need to ask for approval before `git push` (user decision 2026-08-30; previously pushes required explicit approval)

## Architecture

- **Frontend**: Electron/React in `frontend/src/` (React components, pages, API calls). All UI work happens here.
- **Backend**: Flask in `backend/` (port 5678), spawned by `electron/main.js`
- **Database layer**: SQLite mixins in `database/`
- **User data**: the live database and automatic backups live in `~/Library/Application Support/TarotJournal/`, NOT in the repo
- Root-level Python modules (`theme_config.py`, `thumbnail_cache.py`, `card_metadata.py`, `import_presets.py`, `astrology.py`, `geocoder.py`, `logger_config.py`) are shared helpers used by the backend — they are live code
- Planning/design documents live in `docs/planning/`

The legacy wxPython UI (`main.py`, `mixin_*.py`, `ui_library/`, `ui_journal/`, `card_dialogs/`) was deleted in July 2026; recover from git history if ever needed.

---

## Card Image Naming Conventions

When renaming card image files for deck folders, use these naming schemes:

**Playing Cards:**
- h01-h13 for Ace of Hearts through King of Hearts
- c01-c13 for Clubs (same pattern)
- s01-s13 for Spades
- d01-d13 for Diamonds
- j1 and j2 for Jokers

**Tarot:**
- Major Arcana: 00 for The Fool through 21 for The World
- Minor Arcana: w01-w14 for Ace through King of Wands
- c01-c14 for Cups, s01-s14 for Swords, p01-p14 for Pentacles

**Lenormand:**
- 01-36, starting with Rider and ending with Cross

**Oracle:**
- Look for numbers on the card and use those if available

---

## UI Styling (Dark Theme)

The app uses a custom dark theme driven by CSS variables:

- Theme variables are defined in `frontend/src/styles/globals.css` and injected at runtime by `frontend/src/context/ThemeContext.tsx` (user-customizable in Settings → General)
- **Always use `var(--...)` theme variables** for colors and font sizes — never hardcode hex values or px font sizes in component CSS
- Common variables: `--text-primary`, `--text-secondary`, `--text-dim`, `--bg-primary`, `--bg-secondary`, `--accent`, `--danger`, `--font-size-body`, `--font-size-small`
- Shared `button`, `button.primary`, `button.danger` base styles live in globals.css
- Modals must use the shared `Modal` component (`frontend/src/components/common/Modal.tsx`) — it provides focus trapping, Escape handling, and the unsaved-changes guard. Footer Cancel buttons must use `ModalCancelButton`, never a raw `onClick={onClose}`
- Failed data fetches must show the shared `QueryError` component, not an empty state
