# Tarot Journal

A desktop application for serious tarot practitioners to catalog cartomancy decks and maintain a visual reading journal. Built with Electron, React, and a Python backend.

Tarot Journal is designed to support your practice, not replace it. It won't interpret your readings or automate card selection. Instead, it gives you a beautiful, organized space to store your deck collections and record your readings with cards arranged visually in their spread layouts.

## Features at a Glance

- **Deck Library** -- Store and browse your entire collection of tarot, lenormand, oracle, and playing card decks with full-size images and metadata
- **Visual Reading Journal** -- Record readings with cards arranged in their spread positions, rich text notes, and follow-up entries
- **Spread Designer** -- Create custom spread layouts with a drag-and-drop visual editor, including multi-deck spreads
- **Profiles** -- Track querents and readers with birth data for astrological reference
- **Flexible Tagging** -- Color-coded tags for entries, decks, and individual cards
- **Statistics** -- Charts showing your most-drawn cards, reading frequency, tag trends, and deck/spread usage
- **Theming** -- Fully customizable color scheme with preset themes
- **Backup & Restore** -- Create and restore full backups of your data, optionally including card images

---

## Requirements

- **Node.js** 20 or later
- **Python** 3.9 or later
- **pip** (Python package manager, usually included with Python)

## Installation

1. **Clone or download** the repository:
   ```bash
   git clone https://github.com/alexslyon/tarot-journal.git
   cd tarot-journal
   ```

2. **Set up a Python virtual environment** (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # macOS / Linux
   # .venv\Scripts\activate          # Windows
   ```

3. **Install Python dependencies:**
   ```bash
   pip install flask flask-cors Pillow
   ```

4. **Install Node.js dependencies** (root and frontend):
   ```bash
   npm install
   cd frontend && npm install && cd ..
   ```

5. **Run the app:**
   ```bash
   npm run dev
   ```
   This starts the Electron window, the Flask backend, and the Vite development server together. The app will open automatically once everything is ready.

### Production Build

To build and run without a development server:
```bash
npm run start
```

To package as a distributable desktop app:
```bash
npm run package     # Creates a packaged app
npm run make        # Creates platform-specific installers
```

---

## Quick Start Guide

### Importing Your First Deck

1. Open the **Library** tab
2. Click **Import Deck** in the toolbar
3. Select the folder containing your card images
4. Choose an import preset that matches your deck type (Standard Tarot, Lenormand, Oracle, Playing Cards, etc.)
5. Customize suit names and court card names if needed
6. Preview the detected cards and click **Import**

The app supports JPG, PNG, GIF, and WebP image formats. Thumbnails are generated automatically for fast browsing.

### Recording a Reading

1. Open the **Journal** tab
2. Click **New Entry**
3. Give your entry a title, set the date/time, and optionally assign a querent and reader
4. In the reading section, select a spread and a deck
5. Click on card positions in the spread to assign cards from your deck
6. Mark any cards as reversed if needed
7. Write your notes using the rich text editor
8. Click **Save**

You can add multiple readings to a single journal entry (useful for multi-part sessions) and come back later to add follow-up notes as a reading unfolds.

### Creating a Custom Spread

1. Open the **Spreads** tab
2. Click **New Spread**
3. Click **Add Position** to place card positions on the canvas
4. Drag positions to arrange them and resize them as needed
5. Give each position a label and meaning
6. Save your spread -- it will appear as an option when recording readings

---

## Feature Guide

### Library Tab

The Library is where you manage your deck collection. The left panel shows your deck list; the right panel shows the cards in the selected deck.

**Deck management:**
- Import decks from folders of card images using configurable presets
- Edit deck details: name, publication date, publisher, credits, notes, booklet information
- Assign one or more cartomancy types (Tarot, Lenormand, Oracle, Playing Cards, etc.)
- Customize suit names and court card names per deck
- Set a card back image for each deck
- Tag decks with colored labels
- Export decks as shareable JSON files

**Card management:**
- View cards in a thumbnail grid
- Double-click a card to view it full-size, or right-click to edit
- Edit card properties: name, sort order, archetype, rank, suit, and notes
- Add custom fields to a deck (text or dropdown type), then fill them in per card
- Organize cards into named groups with colors
- Tag individual cards
- Navigate between cards with previous/next buttons while editing

**Search:**
- Search across all cards or within the current deck
- Filter by deck type, category (Major Arcana, Minor Arcana, Court Cards), archetype, suit, rank, and more
- Sort results by name, deck, or card order

**Batch editing:**
- Select multiple cards and edit their properties in bulk
- Batch-assign or remove tags and group memberships
- Append notes to multiple cards at once

### Journal Tab

The Journal is where you record and review your readings. The left panel lists your entries; the right panel shows the selected entry's full details.

**Entry creation:**
- Title, date/time, and optional location
- Rich text editor for detailed notes (bold, italic, underline, lists, links)
- Assign querent(s) and a reader from your saved profiles
- Tag entries with colored labels

**Readings:**
- Each entry can contain multiple readings (e.g., a main reading plus a clarifier)
- Select a spread to see the visual layout with labeled positions
- Choose which deck to use for each reading
- Click positions to assign cards, with the option to mark them as reversed
- Multi-deck spreads let you combine cards from different decks in one reading

**Viewing entries:**
- See cards arranged visually in their spread positions
- Click any card to view it full-size or open the card editor
- Read your notes and see all associated metadata
- Browse follow-up notes with timestamps

**Follow-up notes:**
- Add timestamped follow-up notes to any entry after the fact
- Useful for tracking how a reading unfolds over time
- Edit or delete follow-up notes as needed

**Search and filter:**
- Search entries by text (searches titles, content, and notes)
- Filter by tag
- Combine search text with tag filters

### Spreads Tab

The Spreads tab provides a visual editor for designing card layouts.

- Drag-and-drop canvas for positioning cards
- Resize card positions with handles
- Optional grid snapping for precise alignment
- Toggle position labels on the canvas
- Set a name, description, and allowed deck types for each spread
- Clone existing spreads to create variations

**Multi-deck spreads:**
- Define multiple deck slots (e.g., "Tarot Deck" and "Oracle Deck")
- Assign a cartomancy type requirement to each slot
- Link each card position to a specific deck slot
- When recording a reading, you choose which deck fills each slot

### Profiles Tab

Store information about the people involved in your readings.

- Create profiles for querents (the person asking) and readers (the person reading)
- Record name, gender, birth date, birth time, and birth place
- Mark profiles as querent-only if they should never appear as a reader option
- Assign profiles to journal entries as querent or reader

### Tags Tab

Manage your tags across three categories from one central location:

- **Entry tags** -- for organizing journal entries by theme or topic
- **Deck tags** -- for organizing your deck collection
- **Card tags** -- for labeling individual cards across decks

Each tag has a custom name and color. Create, rename, recolor, or delete tags here, and assign them in their respective tabs.

### Stats Tab

Visualize patterns in your reading practice with interactive charts:

- **Overview metrics** -- total entries, readings this month, unique cards drawn, average cards per reading, total decks
- **Activity timeline** -- bar chart showing entries and readings per month over the last 12 months
- **Most drawn cards** -- horizontal bar chart of your top 20 most frequently drawn cards, with reversed counts
- **Tag trends** -- color-coded chart of your most-used entry tags
- **Deck and spread usage** -- side-by-side charts of your top 10 most-used decks and spreads

### Settings Tab

**Theme customization:**
- Choose from preset themes or customize every color individually
- Adjust background colors, accent colors, text colors, borders, and more
- Changes apply immediately with live preview

**Default profiles and decks:**
- Set a default reader and querent (auto-filled when creating new entries)
- Set a default deck for each cartomancy type (auto-selected when choosing a spread)

**Backup and restore:**
- Create a backup of your entire database as a ZIP file
- Optionally include all card images in the backup
- Restore from a backup file (a safety backup is created automatically before restoring)

**Thumbnail cache:**
- View cache statistics (number of thumbnails and total size)
- Clear the cache to free disk space (thumbnails regenerate automatically)

---

## Data Storage

All data is stored locally on your machine:

| File/Folder | Contents |
|---|---|
| `tarot_journal.db` | SQLite database with all entries, decks, cards, spreads, profiles, tags, and settings |
| `.thumbnail_cache/` | Auto-generated card image thumbnails for fast loading |
| Deck image folders | Your original card images, referenced by the database |

The database uses WAL (Write-Ahead Logging) mode for crash safety, so your data is protected even if the app closes unexpectedly.

---

## Troubleshooting

**App won't start:**
- Make sure Python 3.9+ is installed: `python3 --version`
- Make sure Node.js 20+ is installed: `node --version`
- Verify Python dependencies are installed: `pip install flask flask-cors Pillow`
- If using a virtual environment, make sure it's activated or located at `.venv/` in the project root

**Images not loading:**
- Check that image files still exist at their original paths (the app references images by file path, not by copying them)
- Supported formats: JPG, PNG, GIF, WebP

**Slow first load of a deck:**
- The first time you view a deck, thumbnails are generated for all its cards
- Subsequent views will be much faster
- You can check cache status in Settings

**Backup and restore issues:**
- Backups are saved as ZIP files containing a database snapshot
- When restoring, the app creates a safety backup first, so you can always go back
