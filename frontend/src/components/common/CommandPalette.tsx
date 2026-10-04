/**
 * The ⌘K command palette: one keystroke from anywhere to jump to a
 * deck, spread, journal entry, tab, or settings page — or to start a
 * new entry. Type to filter; arrows + Enter to act. Rendered through
 * the shared Modal so it inherits the scrim, Escape handling, and
 * focus trapping.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Modal from './Modal';
import { getDecks } from '../../api/decks';
import { getSpreads } from '../../api/spreads';
import { getEntries, searchEntries } from '../../api/entries';
import { getArchetypes, type Archetype } from '../../api/correspondences';
import type { Deck, Spread, JournalEntry } from '../../types';
import type { TabId } from '../layout/TabNav';
import { formatDate } from '../../utils/formatting';
import './CommandPalette.css';

/** Everything the palette can do, expressed as one action object the
 *  App interprets (it owns tab state and the deep-link plumbing). */
export type PaletteAction =
  | { type: 'tab'; tab: TabId }
  | { type: 'settings'; section: string }
  | { type: 'reference'; section: string }
  | { type: 'new-entry' }
  | { type: 'scribe' }
  | { type: 'shortcuts' }
  | { type: 'deck'; id: number }
  | { type: 'archetype'; id: number; cartomancyType: string }
  | { type: 'spread'; id: number }
  | { type: 'entry'; id: number };

interface PaletteItem {
  key: string;
  group: string;
  label: string;
  hint?: string;
  action: PaletteAction;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onAction: (action: PaletteAction) => void;
}

const TAB_ITEMS: PaletteItem[] = ([
  ['library', 'Library'],
  ['spreads', 'Spreads'],
  ['journal', 'Journal'],
  ['profiles', 'Profiles'],
  ['reference', 'Reference'],
  ['insights', 'Insights'],
  ['settings', 'Settings'],
] as [TabId, string][]).map(([tab, label]) => ({
  key: `tab-${tab}`,
  group: 'Go to',
  label,
  action: { type: 'tab', tab },
}));

// Mirrors SECTION_GROUPS in SettingsLayout — ids must match.
const SETTINGS_ITEMS: PaletteItem[] = ([
  ['general', 'General'],
  ['ai', 'AI Assistant'],
  ['ai-prompts', 'AI Prompts'],
  ['backup', 'Backup & Restore'],
  ['cache', 'Thumbnail Cache'],
  ['tags', 'Tags'],
  ['deck-types', 'Deck Types'],
  ['correspondences', 'Correspondences'],
  ['archetype-notes', 'Archetype Notes'],
  ['archetype-languages', 'Archetype Languages'],
  ['combinations', 'Combinations'],
  ['reference-sources', 'Reference Sources'],
  ['import-presets', 'Import Presets'],
] as [string, string][]).map(([section, label]) => ({
  key: `settings-${section}`,
  group: 'Settings',
  label,
  action: { type: 'settings', section },
}));

// The Reference tab's content sections (its card-data sections are
// reachable through the tab itself; these are the lookup pages worth
// jumping straight to).
const REFERENCE_ITEMS: PaletteItem[] = ([
  ['astrology', 'Astrology'],
  ['kabbalah', 'Kabbalah'],
  ['suits', 'Suits'],
  ['numerology', 'Numerology & Ranks'],
  ['chakras', 'Chakras'],
] as [string, string][]).map(([section, label]) => ({
  key: `reference-${section}`,
  group: 'Reference',
  label,
  action: { type: 'reference', section },
}));

const ACTION_ITEMS: PaletteItem[] = [
  {
    key: 'action-new-entry',
    group: 'Actions',
    label: 'New journal entry',
    hint: '⌘N',
    action: { type: 'new-entry' },
  },
  {
    key: 'action-scribe',
    group: 'Actions',
    label: 'Open the Scribe (import a source)',
    action: { type: 'scribe' },
  },
  {
    key: 'action-shortcuts',
    group: 'Actions',
    label: 'Keyboard shortcuts',
    hint: '?',
    action: { type: 'shortcuts' },
  },
];

function entryLabel(entry: JournalEntry): string {
  return entry.title?.trim() || 'Untitled entry';
}

export default function CommandPalette({ open, onClose, onAction }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // Fresh start each time the palette opens.
  useEffect(() => {
    if (open) {
      setQuery('');
      setHighlight(0);
    }
  }, [open]);

  const { data: decks = [] } = useQuery<Deck[]>({
    queryKey: ['decks'],
    queryFn: () => getDecks(),
    enabled: open,
  });
  const { data: spreads = [] } = useQuery<Spread[]>({
    queryKey: ['spreads'],
    queryFn: getSpreads,
    enabled: open,
  });
  const { data: recentEntries = [] } = useQuery<JournalEntry[]>({
    queryKey: ['palette-recent-entries'],
    queryFn: () => getEntries(6),
    enabled: open,
  });
  const { data: archetypes = [] } = useQuery<Archetype[]>({
    queryKey: ['archetypes', undefined],
    queryFn: () => getArchetypes(),
    enabled: open,
  });

  // Debounced full-text entry search once the query is substantial —
  // recent entries alone would miss anything older than the first page.
  const [debouncedQuery, setDebouncedQuery] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 200);
    return () => clearTimeout(t);
  }, [query]);
  const { data: searchedEntries = [] } = useQuery<JournalEntry[]>({
    queryKey: ['palette-entry-search', debouncedQuery],
    queryFn: () => searchEntries({ query: debouncedQuery }),
    enabled: open && debouncedQuery.length >= 2,
  });

  const items = useMemo<PaletteItem[]>(() => {
    const q = query.trim().toLowerCase();
    const matches = (label: string) => !q || label.toLowerCase().includes(q);

    const result: PaletteItem[] = [];
    result.push(...ACTION_ITEMS.filter(i => matches(i.label)));
    result.push(...TAB_ITEMS.filter(i => matches(i.label)));
    // Decks, spreads, and settings pages only appear once the user
    // types — an empty palette dumping the whole catalog (hundreds of
    // rows) buries the useful starting points.
    if (q) {
      result.push(...REFERENCE_ITEMS.filter(i => matches(i.label)));
      result.push(...SETTINGS_ITEMS.filter(i => matches(i.label)));
      result.push(...decks.filter(d => matches(d.name)).map(d => ({
        key: `deck-${d.id}`,
        group: 'Decks',
        label: d.name,
        action: { type: 'deck', id: d.id } as PaletteAction,
      })));
      result.push(...spreads.filter(s => !s.archived && matches(s.name)).map(s => ({
        key: `spread-${s.id}`,
        group: 'Spreads',
        label: s.name,
        action: { type: 'spread', id: s.id } as PaletteAction,
      })));
      result.push(...archetypes.filter(a => matches(a.name)).slice(0, 20).map(a => ({
        key: `archetype-${a.id}`,
        group: 'Card Archetypes',
        label: a.name,
        hint: a.cartomancy_type,
        action: {
          type: 'archetype', id: a.id, cartomancyType: a.cartomancy_type,
        } as PaletteAction,
      })));
    }

    // Entries: recents when browsing; the server search (title, notes,
    // cards drawn) once typing — recents that also match stay on top.
    const seen = new Set<number>();
    const entryItems: PaletteItem[] = [];
    const pushEntry = (e: JournalEntry, group: string) => {
      if (seen.has(e.id)) return;
      seen.add(e.id);
      entryItems.push({
        key: `entry-${e.id}`,
        group,
        label: entryLabel(e),
        hint: formatDate(e.reading_datetime || e.created_at),
        action: { type: 'entry', id: e.id },
      });
    };
    if (!q) {
      recentEntries.forEach(e => pushEntry(e, 'Recent entries'));
    } else {
      recentEntries.filter(e => matches(entryLabel(e))).forEach(e => pushEntry(e, 'Entries'));
      if (debouncedQuery.length >= 2) {
        searchedEntries.slice(0, 12).forEach(e => pushEntry(e, 'Entries'));
      }
    }
    result.push(...entryItems);
    return result;
  }, [query, debouncedQuery, decks, spreads, archetypes, recentEntries, searchedEntries]);

  // Keep the highlight on a real row as the result set changes.
  useEffect(() => {
    setHighlight(h => Math.min(h, Math.max(0, items.length - 1)));
  }, [items]);

  const run = (item: PaletteItem) => {
    onClose();
    onAction(item.action);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight(h => Math.min(h + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight(h => Math.max(h - 1, 0));
    } else if (e.key === 'Enter' && items[highlight]) {
      e.preventDefault();
      run(items[highlight]);
    }
  };

  // Keep the highlighted row scrolled into view.
  useEffect(() => {
    listRef.current
      ?.querySelector('.command-palette__item--active')
      ?.scrollIntoView({ block: 'nearest' });
  }, [highlight, items]);

  // Rows render grouped: emit a kicker whenever the group changes.
  let lastGroup = '';

  return (
    <Modal open={open} onClose={onClose} width={560}>
      <div className="command-palette" onKeyDown={handleKeyDown}>
        <input
          className="command-palette__input"
          type="text"
          placeholder="Jump to a deck, spread, entry, or page…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Command palette search"
        />
        <div className="command-palette__list" ref={listRef} role="listbox">
          {items.length === 0 && (
            <div className="command-palette__empty">Nothing matches.</div>
          )}
          {items.map((item, idx) => {
            const showGroup = item.group !== lastGroup;
            lastGroup = item.group;
            return (
              <div key={item.key}>
                {showGroup && (
                  <div className="command-palette__group">{item.group}</div>
                )}
                <div
                  role="option"
                  aria-selected={idx === highlight}
                  className={`command-palette__item ${idx === highlight ? 'command-palette__item--active' : ''}`}
                  onMouseEnter={() => setHighlight(idx)}
                  onClick={() => run(item)}
                >
                  <span className="command-palette__label">{item.label}</span>
                  {item.hint && (
                    <span className="command-palette__hint">{item.hint}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="command-palette__footer">
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>esc close</span>
        </div>
      </div>
    </Modal>
  );
}
