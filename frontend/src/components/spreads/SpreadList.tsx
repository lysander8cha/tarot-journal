import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getSpreads, updateSpread } from '../../api/spreads';
import { getCartomancyTypes } from '../../api/decks';
import { getSpreadTags } from '../../api/tags';
import { useToast } from '../../context/ToastContext';
import type { Spread, Tag } from '../../types';
import { slotTypes } from '../../utils/formatting';
import QueryError from '../common/QueryError';
import ShareControls from '../common/ShareControls';
import { downloadSpreadsExport, importSpreads } from '../../api/share';
import './SpreadList.css';

interface SpreadListProps {
  selectedSpreadId: number | null;
  onSelect: (spread: Spread) => void;
  onNew: () => void;
  onClone: () => void;
  onDelete: () => void;
}

type SortKey = 'name' | 'positions';

function positionCount(spread: Spread): number {
  return Array.isArray(spread.positions) ? spread.positions.length : 0;
}

/** The deck types a spread declares. Deck slots are the current
 *  system and the only thing visible in the editor, so when a spread
 *  has slots they alone decide — many spreads still carry stale
 *  values in the older allowed-types / single-type fields, which
 *  would wrongly hide an "Any" spread under specific filters. Those
 *  legacy fields are consulted only for spreads with no slots.
 *  Empty means the spread works with any deck. */
function spreadDeckTypes(spread: Spread): string[] {
  let slots = spread.deck_slots;
  if (typeof slots === 'string') {
    try { slots = JSON.parse(slots); } catch { slots = []; }
  }
  if (Array.isArray(slots) && slots.length > 0) {
    const types = new Set<string>();
    for (const slot of slots) {
      for (const t of slotTypes(slot)) types.add(t);
    }
    return [...types];
  }
  const types = new Set<string>();
  let allowed = spread.allowed_deck_types;
  if (typeof allowed === 'string') {
    try { allowed = JSON.parse(allowed); } catch { allowed = []; }
  }
  if (Array.isArray(allowed)) allowed.forEach(t => types.add(t));
  if (spread.cartomancy_type) types.add(spread.cartomancy_type);
  return [...types];
}

export default function SpreadList({
  selectedSpreadId,
  onSelect,
  onNew,
  onClone,
  onDelete,
}: SpreadListProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const { data: spreads = [], isLoading, isError, refetch } = useQuery<Spread[]>({
    queryKey: ['spreads'],
    queryFn: getSpreads,
  });

  const { data: types = [] } = useQuery({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });
  const { data: allTags = [] } = useQuery<Tag[]>({
    queryKey: ['spread-tags'],
    queryFn: getSpreadTags,
  });

  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [showArchived, setShowArchived] = useState(false);
  const [filterType, setFilterType] = useState('');
  const [filterTagId, setFilterTagId] = useState<number | ''>('');

  const selected = spreads.find(s => s.id === selectedSpreadId) ?? null;

  const { active, archived } = useMemo(() => {
    const q = search.trim().toLowerCase();
    const matches = (s: Spread) => {
      if (q && !s.name.toLowerCase().includes(q)) return false;
      if (filterType) {
        // Spreads with no declared type work with any deck, so they
        // stay visible under every type filter.
        const declared = spreadDeckTypes(s);
        if (declared.length > 0 && !declared.includes(filterType)) return false;
      }
      if (filterTagId !== '' && !(s.tags ?? []).some(t => t.id === filterTagId)) return false;
      return true;
    };
    const sorted = [...spreads].sort((a, b) =>
      Number(!!b.favorite) - Number(!!a.favorite)
      || (sortKey === 'positions'
        ? positionCount(a) - positionCount(b) || a.name.localeCompare(b.name)
        : a.name.localeCompare(b.name)));
    return {
      active: sorted.filter(s => !s.archived && matches(s)),
      archived: sorted.filter(s => !!s.archived && matches(s)),
    };
  }, [spreads, search, sortKey, filterType, filterTagId]);

  const handleArchiveToggle = async () => {
    if (!selected) return;
    const archiving = !selected.archived;
    try {
      await updateSpread(selected.id, { archived: archiving });
      queryClient.invalidateQueries({ queryKey: ['spreads'] });
      showToast(
        archiving
          ? `Archived "${selected.name}" — existing journal entries keep it.`
          : `Restored "${selected.name}".`,
        'success',
      );
      if (archiving && !showArchived) setShowArchived(true);
    } catch {
      showToast('Failed to update the spread.');
    }
  };

  const toggleFavorite = async (spread: Spread) => {
    try {
      await updateSpread(spread.id, { favorite: !spread.favorite });
      queryClient.invalidateQueries({ queryKey: ['spreads'] });
    } catch {
      showToast('Failed to update the spread.');
    }
  };

  const renderRow = (spread: Spread) => (
    <div
      key={spread.id}
      className={`spread-list__row ${spread.id === selectedSpreadId ? 'spread-list__row--selected' : ''}`}
      onClick={() => onSelect(spread)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(spread);
        }
      }}
    >
      <span className="spread-list__name">{spread.name}</span>
      {(spread.tags ?? []).length > 0 && (
        <span className="spread-list__tag-dots">
          {spread.tags!.map(tag => (
            <span
              key={tag.id}
              className="spread-list__tag-dot"
              style={{ backgroundColor: tag.color }}
              title={tag.name}
            />
          ))}
        </span>
      )}
      <span className="spread-list__count">{positionCount(spread)} pos</span>
      <button
        type="button"
        className={`spread-list__fav ${spread.favorite ? 'spread-list__fav--on' : ''}`}
        title={spread.favorite ? 'Favorite — click to unfavorite' : 'Mark as favorite'}
        aria-label={spread.favorite ? `Unfavorite ${spread.name}` : `Favorite ${spread.name}`}
        onClick={(e) => { e.stopPropagation(); toggleFavorite(spread); }}
        onKeyDown={(e) => e.stopPropagation()}
      >
        ★
      </button>
    </div>
  );

  return (
    <div className="spread-list">
      <div className="spread-list__header">
        <h2 className="spread-list__title">Spreads</h2>
        <div className="spread-list__actions">
          <button onClick={onNew} title="New spread" data-guide="new-spread">New</button>
          <button onClick={onClone} disabled={!selectedSpreadId} title="Clone selected">Clone</button>
          <button
            onClick={handleArchiveToggle}
            disabled={!selected}
            title={selected?.archived
              ? 'Restore this spread to the active list'
              : 'Hide from the list and pickers without deleting — older entries keep it'}
          >
            {selected?.archived ? 'Restore' : 'Archive'}
          </button>
          <button onClick={onDelete} disabled={!selectedSpreadId} title="Delete selected">Delete</button>
        </div>
      </div>

      <div className="spread-list__filters">
        <input
          type="search"
          className="spread-list__search"
          placeholder="Search spreads..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="spread-list__selects">
          <select
            className="spread-list__filter"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            title="Filter by deck type"
          >
            <option value="">All Types</option>
            {types.map((t) => (
              <option key={t.id} value={t.name}>{t.name}</option>
            ))}
          </select>
          {allTags.length > 0 && (
            <select
              className="spread-list__filter"
              value={filterTagId}
              onChange={(e) => setFilterTagId(e.target.value ? Number(e.target.value) : '')}
              title="Filter by tag"
            >
              <option value="">All Tags</option>
              {allTags.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          )}
        </div>
        <div className="spread-list__sort-bar">
          <span className="spread-list__sort-label">Sort:</span>
          <button
            className={`spread-list__sort-btn ${sortKey === 'name' ? 'spread-list__sort-btn--active' : ''}`}
            onClick={() => setSortKey('name')}
          >
            Name
          </button>
          <button
            className={`spread-list__sort-btn ${sortKey === 'positions' ? 'spread-list__sort-btn--active' : ''}`}
            onClick={() => setSortKey('positions')}
          >
            # Positions
          </button>
        </div>
      </div>

      <div className="spread-list__rows">
        {isLoading && <div className="spread-list__loading">Loading...</div>}
        {!isLoading && isError && (
          <QueryError what="spreads" onRetry={() => refetch()} />
        )}
        {active.map(renderRow)}
        {!isLoading && !isError && active.length === 0 && (
          <div className="spread-list__empty">
            {search ? 'No spreads match.' : 'No spreads yet'}
          </div>
        )}

        {archived.length > 0 && (
          <div className="spread-list__archived">
            <button
              className="spread-list__archived-toggle"
              aria-expanded={showArchived}
              onClick={() => setShowArchived(o => !o)}
            >
              <span className={`spread-list__chevron ${showArchived ? 'spread-list__chevron--open' : ''}`} aria-hidden="true">▸</span>
              Archived ({archived.length})
            </button>
            {showArchived && archived.map(renderRow)}
          </div>
        )}
      </div>

      <div className="spread-list__share">
        <ShareControls
          noun="spreads"
          selected={spreads.find(s => s.id === selectedSpreadId) ?? null}
          onExport={downloadSpreadsExport}
          onImport={async (data) => {
            const res = await importSpreads(data);
            queryClient.invalidateQueries({ queryKey: ['spreads'] });
            queryClient.invalidateQueries({ queryKey: ['spread-tags'] });
            const skipped = res.skipped.length
              ? ` ${res.skipped.length} skipped (already exist: ${res.skipped.slice(0, 3).join(', ')}${res.skipped.length > 3 ? '…' : ''}).`
              : '';
            return `Imported ${res.imported} spread${res.imported === 1 ? '' : 's'}.${skipped}`;
          }}
        />
      </div>
    </div>
  );
}
