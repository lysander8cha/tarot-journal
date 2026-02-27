# Tarot Journal - Architecture Overview

This document provides a quick reference for understanding how the codebase is structured. For project goals, user context, and styling guidelines, see [CLAUDE.md](CLAUDE.md).

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19 + TypeScript |
| Build Tool | Vite 7 |
| Desktop Wrapper | Electron 33 |
| Backend | Flask (Python) |
| Database | SQLite with WAL mode |
| State Management | TanStack React Query v5 |
| Rich Text | TipTap 3 |
| Charts | Recharts |

---

## Project Structure

```
tarot_journal/
├── frontend/           # React/TypeScript frontend (ACTIVE)
│   └── src/
│       ├── api/        # Axios API client layer
│       ├── components/ # React components by feature
│       ├── context/    # React context (theme)
│       ├── types/      # TypeScript interfaces
│       └── styles/     # Global CSS
├── backend/            # Flask REST API
│   ├── routes/         # API endpoint blueprints
│   └── services/       # Business logic helpers
├── database/           # SQLite database layer (mixin pattern)
├── electron/           # Electron main process
│   ├── main.js         # App entry, spawns Flask
│   └── preload.js      # IPC bridge for file dialogs
└── [deck folders]      # User's deck image collections
```

### Deprecated Code (Ignore)
- `main.py`, `main_tk.py` - Legacy Python entry points
- `ui_journal/`, `ui_library/`, `card_dialogs/` - Legacy wxPython UI
- `mixin_*.py` - Legacy UI mixins

---

## Communication Flow

```
┌─────────────────┐     HTTP/REST      ┌─────────────────┐
│  React Frontend │ ◄──────────────────► │  Flask Backend  │
│  (localhost:5173)│     (JSON)          │  (localhost:5678)│
└─────────────────┘                     └─────────────────┘
                                               │
                                               ▼
                                        ┌─────────────────┐
                                        │   SQLite DB     │
                                        │ tarot_journal.db│
                                        └─────────────────┘
```

**In Development:**
- Frontend dev server runs on port 5173 (Vite)
- Backend API runs on port 5678 (Flask)
- Electron loads from the Vite dev server

**In Production:**
- Flask serves the built React app from `frontend/dist/`
- Single Electron window wraps everything

---

## Backend Architecture

### Flask App Structure (`/backend/`)

| File/Folder | Purpose |
|-------------|---------|
| `app.py` | Flask application factory |
| `config.py` | Port, CORS origins configuration |
| `security.py` | Input validation, security utilities |
| `utils.py` | Shared helpers (row_to_dict, sorting) |
| `routes/*.py` | API endpoint blueprints (12 files) |

### Key API Routes

| Route File | Endpoints | Purpose |
|------------|-----------|---------|
| `decks.py` | `/api/decks` | Deck CRUD, metadata |
| `cards.py` | `/api/cards` | Card CRUD, custom fields |
| `entries.py` | `/api/entries` | Journal entries, readings, search |
| `spreads.py` | `/api/spreads` | Spread layout CRUD |
| `profiles.py` | `/api/profiles` | Querent/reader profiles |
| `tags.py` | `/api/tags/*` | Tag management (entries, decks, cards) |
| `images.py` | `/api/images` | Card image serving |
| `settings.py` | `/api/settings` | Theme and app preferences |
| `stats.py` | `/api/stats` | Statistics and visualizations |
| `import_export.py` | `/api/import`, `/api/export` | Deck/entry import-export |

### Backend Features
- **CORS enabled** for Vite dev server
- **Transaction support** with automatic rollback
- **Thread-safe** database access with RLock
- **N+1 query optimization** via bulk queries
- **JSON validation** prevents malformed payloads

---

## Database Architecture

### Mixin Pattern (`/database/`)

The `Database` class combines multiple mixins, each handling a domain:

```python
class Database(CoreMixin, DecksMixin, CardsMixin, CardGroupsMixin,
               TagsMixin, EntriesMixin, ProfilesMixin, SettingsMixin,
               ImportExportMixin)
```

### Core Tables

| Table | Purpose |
|-------|---------|
| `decks` | Deck metadata, image folder, suit/court names |
| `cards` | Individual cards per deck |
| `spreads` | Saved spread layouts with 2D positions |
| `profiles` | Querent/reader data (supports `hidden` flag to exclude from dropdowns) |
| `journal_entries` | Journal entries (title, content, timestamps) |
| `entry_readings` | Links entries to spreads, decks, cards used |
| `follow_up_notes` | Additional notes added after entry creation |

### Relationship Tables

| Table | Purpose |
|-------|---------|
| `entry_tags` | Entry-to-tag associations |
| `entry_querents` | Entry-to-querent associations |
| `deck_tags` / `deck_tag_assignments` | Deck tagging |
| `card_tags` / `card_tag_assignments` | Card tagging |
| `deck_type_assignments` | Decks can have multiple cartomancy types |
| `card_groups` / `card_group_assignments` | Custom card groupings |

---

## Frontend Architecture

### Component Organization (`/frontend/src/components/`)

| Folder | Purpose |
|--------|---------|
| `layout/` | Tab navigation, main layout |
| `library/` | Deck library, card management |
| `journal/` | Journal entries, reading editor |
| `spreads/` | Spread designer (visual SVG editor) |
| `profiles/` | Querent/reader profiles |
| `tags/` | Tag management |
| `stats/` | Statistics dashboard with visualizations |
| `settings/` | App settings |
| `common/` | Shared components (Modal, RichTextEditor, RichTextViewer) |

### Key Components

| Component | Purpose |
|-----------|---------|
| `App.tsx` | Root component with tab routing |
| `LibraryTab.tsx` | Deck library main view |
| `JournalTab.tsx` | Journal main view |
| `EntryEditorModal.tsx` | Create/edit journal entries |
| `ReadingEditor.tsx` | Complex multi-deck reading editor |
| `SpreadDesigner.tsx` | Visual spread layout editor (supports read-only viewer mode) |
| `SpreadsTab.tsx` | Spreads management with separate view/edit modes |
| `CardEditModal.tsx` | Edit individual card details |
| `DeckEditModal.tsx` | Edit deck metadata, rich text notes/booklet info |
| `ProfilesTab.tsx` | Profile management with debounced auto-save |
| `StatsTab.tsx` | Statistics dashboard with charts |

### State Management

- **TanStack React Query** for server state (caching, background refetch)
- **React useState** for local UI state
- **Context API** for global theme state (`ThemeContext.tsx`)

### API Layer (`/frontend/src/api/`)

Each file corresponds to a backend domain:
- `client.ts` - Axios instance (baseURL: localhost:5678)
- `decks.ts`, `cards.ts`, `entries.ts`, `stats.ts`, etc.

---

## Key Data Models

### Deck
```typescript
{
  id, name, cartomancy_type_id, image_folder,
  suit_names, court_names, date_published, publisher,
  card_back_image, tags, card_count
}
```

### Card
```typescript
{
  id, deck_id, name, image_path, card_order,
  archetype, rank, suit, notes, custom_fields
}
```

### Spread
```typescript
{
  id, name, description,
  positions: [{ x, y, width, height, label, key, rotated, deck_slot }],
  cartomancy_type, allowed_deck_types, default_deck_id, deck_slots
}
```

### JournalEntry
```typescript
{
  id, title, content, created_at, updated_at,
  reading_datetime, location_name, querent_id, reader_id
}
```

### Profile
```typescript
{
  id, name, gender, birth_date, birth_time,
  birth_place_name, birth_place_lat, birth_place_lon,
  querent_only, hidden, created_at
}
```

### EntryReading
```typescript
{
  id, entry_id, spread_id, spread_name,
  deck_id, deck_name, cartomancy_type,
  cards_used: [{ card_id, position_key, reversed }]
}
```

---

## Development Commands

### Root Level
```bash
npm run dev          # Start Electron + Flask + Vite dev server
npm run start        # Build frontend, then start Electron
npm run package      # Package for distribution
npm run make         # Create distributable installers
```

### Frontend (`/frontend/`)
```bash
npm run dev          # Vite dev server on :5173
npm run build        # Build to dist/
npm run lint         # ESLint check
```

---

## Electron Integration

### Process Flow
1. Electron starts → spawns Flask as subprocess
2. Flask initializes on port 5678
3. Electron polls `/api/health` until ready
4. BrowserWindow loads Vite (dev) or Flask (prod)

### IPC Handlers (via `preload.js`)
- `window.electronAPI.openFolderDialog()` - Native folder picker
- `window.electronAPI.openFileDialog()` - Native file picker

---

## Architecture Patterns

### Backend
- **Blueprint pattern** for route organization
- **Mixin pattern** for database domain separation
- **Transaction context managers** for atomicity
- **Bulk queries** to prevent N+1 problems

### Frontend
- **Feature-based component organization**
- **React Query** for server state + caching
- **CSS variables** for runtime theming
- **Modal pattern** for edit dialogs
- **`ensureHtml()` pattern** for backwards-compatible rich text: detects plain text with `\n` newlines and converts to HTML `<p>` tags before passing to TipTap editors/viewers (used in spreads, deck edit)
- **Debounced auto-save** with `useRef` timers and population guards (used in profiles)

---

## Recent Development Focus

Based on recent commits:
1. **Statistics dashboard** with visualizations (card frequency, timeline, tag trends, deck/spread usage)
2. Card frequency aggregation across all decks (unified view)
3. Timeline charts showing entries and readings over time
4. Preserved card_id in journal entries for accurate tracking
5. N+1 query elimination and transaction safety
6. **Rich text editors** for spread descriptions, deck notes, and booklet info (TipTap)
7. **Spreads tab view/edit mode split** with read-only viewer and label toggle
8. **Hidden profiles** feature to exclude rarely-used profiles from journal entry dropdowns
9. **Auto-save on profiles** with debounced saving and status indicator
