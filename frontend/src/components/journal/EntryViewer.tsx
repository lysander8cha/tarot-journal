import { useState, useMemo, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getEntry, deleteEntry, getEntryLlmMarkdown } from '../../api/entries';
import { useToast } from '../../context/ToastContext';
import RichTextViewer from '../common/RichTextViewer';
import SpreadDisplay from './SpreadDisplay';
import { useQuerentBirthCards, QuerentBirthCardsPanel } from './QuerentBirthCards';
import FollowUpNotes from './FollowUpNotes';
import ReadingBreakdown from './ReadingBreakdown';
import ChartModal from '../astrology/ChartModal';
import CardViewModal from '../library/CardViewModal';
import CardEditModal from '../library/CardEditModal';
import PdfExportModal from './PdfExportModal';
import MirrorModal from './MirrorModal';
import type { JournalEntryFull } from '../../types';
import './EntryViewer.css';

interface EntryViewerProps {
  entryId: number;
  onEdit: (entryId: number) => void;
  /** Start a new entry copying this one's structure (spread, deck,
   *  querent, reader, tags) with empty cards and today's date. */
  onNewFromEntry?: (entryId: number) => void;
  /** Filter the journal to entries containing a card (card viewer) */
  onFindCardInJournal?: (cardName: string) => void;
  onDeleted: () => void;
  /** Adjacent entries in the list, for Newer/Older navigation */
  newerEntryId?: number | null;
  olderEntryId?: number | null;
  onNavigateEntry?: (entryId: number) => void;
}

import { formatDateTime } from '../../utils/formatting';
import { confirmDialog } from '../common/ConfirmDialog';

export default function EntryViewer({ entryId, onEdit, onNewFromEntry, onFindCardInJournal, onDeleted, newerEntryId, olderEntryId, onNavigateEntry }: EntryViewerProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [viewingCardId, setViewingCardId] = useState<number | null>(null);
  const [editingCardId, setEditingCardId] = useState<number | null>(null);
  const [chartOpen, setChartOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [mirrorOpen, setMirrorOpen] = useState(false);

  const { data: entry, isLoading, error } = useQuery<JournalEntryFull>({
    queryKey: ['entry', entryId],
    queryFn: () => getEntry(entryId),
  });

  // "Indicate Birth Cards": highlight the querents' Greer birth cards
  // inside Tarot spreads. Preference sticks across entries.
  const [indicateBirthCards, setIndicateBirthCards] = useState(
    () => localStorage.getItem('tj-indicate-birth-cards') === '1');
  const toggleIndicateBirthCards = () => setIndicateBirthCards(v => {
    try { localStorage.setItem('tj-indicate-birth-cards', v ? '0' : '1'); } catch { /* private mode */ }
    return !v;
  });
  const readingYear = entry?.reading_datetime
    ? new Date(entry.reading_datetime).getFullYear()
    : undefined;
  const querentBirthCards = useQuerentBirthCards(
    entry?.querents, readingYear, !!entry);
  const hasTarotReading = !!entry?.readings.some(r =>
    r.cartomancy_type === 'Tarot'
    || (r.cards_used || []).some(c => c.cartomancy_type === 'Tarot'));
  const showBirthCardControls =
    hasTarotReading && querentBirthCards.perQuerent.length > 0;

  // Collect all card IDs and their deck IDs from all readings for navigation/editing
  const { allCardIds, cardToDeckMap } = useMemo(() => {
    if (!entry) return { allCardIds: [], cardToDeckMap: new Map<number, number>() };
    const ids: number[] = [];
    const deckMap = new Map<number, number>();
    for (const reading of entry.readings) {
      for (const card of reading.cards_used || []) {
        if (card.card_id && !ids.includes(card.card_id)) {
          ids.push(card.card_id);
          if (card.deck_id) {
            deckMap.set(card.card_id, card.deck_id);
          }
        }
      }
    }
    return { allCardIds: ids, cardToDeckMap: deckMap };
  }, [entry]);

  // Left/right arrows flip between entries (newest first, so Left =
  // newer, Right = older) — same idiom as the card viewer. Ignored
  // while typing or while any dialog is open.
  useEffect(() => {
    if (!onNavigateEntry) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      )) return;
      if (document.querySelector('.modal-overlay, .confirm-dialog__overlay')) return;
      if (e.key === 'ArrowLeft' && newerEntryId) {
        e.preventDefault();
        onNavigateEntry(newerEntryId);
      } else if (e.key === 'ArrowRight' && olderEntryId) {
        e.preventDefault();
        onNavigateEntry(olderEntryId);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [newerEntryId, olderEntryId, onNavigateEntry]);

  // "Copy for AI": the entry as structured markdown on the clipboard,
  // ready to paste into Claude / ChatGPT / a local model. The app
  // itself never interprets — this hands the context to a
  // conversation the user drives.
  const handleCopyForAi = async () => {
    try {
      const markdown = await getEntryLlmMarkdown(entryId);
      await navigator.clipboard.writeText(markdown);
      showToast('Copied — paste into your AI chat of choice.', 'success');
    } catch (err) {
      console.error('Failed to copy entry for AI:', err);
      showToast('Failed to copy entry.');
    }
  };

  const handleDelete = async () => {
    if (!(await confirmDialog({ message: 'Delete this journal entry? This cannot be undone.', title: 'Delete Entry', confirmLabel: 'Delete' }))) return;
    try {
      await deleteEntry(entryId);
      queryClient.invalidateQueries({ queryKey: ['entries'] });
      queryClient.invalidateQueries({ queryKey: ['entry-search'] });
      onDeleted();
    } catch (err) {
      console.error('Failed to delete entry:', err);
      showToast('Failed to delete entry.');
    }
  };

  if (isLoading) {
    return <div className="entry-viewer__loading">Loading entry...</div>;
  }

  if (error || !entry) {
    return <div className="entry-viewer__error">Failed to load entry.</div>;
  }

  return (
    <div className="entry-viewer">
      <div className="entry-viewer__scroll">
        {/* Header */}
        <div className="entry-viewer__header">
          <h2 className="entry-viewer__title">{entry.title || 'Untitled Entry'}</h2>
          <div className="entry-viewer__actions">
            {onNavigateEntry && (
              <span className="entry-viewer__nav">
                <button
                  disabled={!newerEntryId}
                  onClick={() => newerEntryId && onNavigateEntry(newerEntryId)}
                  title="Newer entry (←)"
                >
                  &lsaquo; Newer
                </button>
                <button
                  disabled={!olderEntryId}
                  onClick={() => olderEntryId && onNavigateEntry(olderEntryId)}
                  title="Older entry (→)"
                >
                  Older &rsaquo;
                </button>
              </span>
            )}
            <button onClick={() => setChartOpen(true)} title="Open event chart">
              View Chart
            </button>
            <button
              onClick={() => setExportOpen(true)}
              title="Export this entry as a PDF"
              disabled={!entry.readings?.length}
            >
              Export PDF
            </button>
            <button
              onClick={handleCopyForAi}
              title="Copy this entry as structured text for pasting into an AI chat"
            >
              Copy for AI
            </button>
            <button
              onClick={() => setMirrorOpen(true)}
              title="Reflect on this entry with the Mirror — it asks questions, never interprets"
            >
              Reflect
            </button>
            <button onClick={() => onEdit(entryId)}>Edit</button>
            {onNewFromEntry && (
              <button
                onClick={() => onNewFromEntry(entryId)}
                title="Start a new entry with the same spread, deck, querent, and tags"
              >
                New Like This
              </button>
            )}
            <button className="danger" onClick={handleDelete}>Delete</button>
          </div>
        </div>

        {/* Metadata */}
        <div className="entry-viewer__meta">
          {entry.reading_datetime && (
            <div className="entry-viewer__meta-item">
              <span className="entry-viewer__meta-label">Date</span>
              <span>{formatDateTime(entry.reading_datetime)}</span>
            </div>
          )}
          {entry.location_name && (
            <div className="entry-viewer__meta-item">
              <span className="entry-viewer__meta-label">Location</span>
              <span>{entry.location_name}</span>
            </div>
          )}
          {entry.querents && entry.querents.length > 0 && (
            <div className="entry-viewer__meta-item">
              <span className="entry-viewer__meta-label">
                {entry.querents.length === 1 ? 'Querent' : 'Querents'}
              </span>
              <span>{entry.querents.map(q => q.name).join(', ')}</span>
              <QuerentBirthCardsPanel data={querentBirthCards} onCardClick={setViewingCardId} />
            </div>
          )}
          {entry.reader_name && (
            <div className="entry-viewer__meta-item">
              <span className="entry-viewer__meta-label">Reader</span>
              <span>{entry.reader_name}</span>
            </div>
          )}
        </div>

        {/* Tags */}
        {entry.tags.length > 0 && (
          <div className="entry-viewer__tags">
            {entry.tags.map((tag) => (
              <span
                key={tag.id}
                className="entry-viewer__tag"
                style={{ backgroundColor: tag.color }}
              >
                {tag.name}
              </span>
            ))}
          </div>
        )}

        {/* Readings */}
        {entry.readings.length > 0 && (
          <div className="entry-viewer__section">
            <div className="entry-viewer__section-head">
              <h3 className="entry-viewer__section-title">Readings</h3>
              {showBirthCardControls && (
                <label className="entry-viewer__birth-toggle">
                  <input
                    type="checkbox"
                    checked={indicateBirthCards}
                    onChange={toggleIndicateBirthCards}
                  />
                  <span>Indicate Birth &amp; Name Cards</span>
                </label>
              )}
            </div>
            {entry.readings.map((reading) => (
              <div key={reading.id} className="entry-viewer__reading">
                {reading.querent_id != null
                  && entry.querents?.some(q => q.id === reading.querent_id) && (
                  <div className="entry-viewer__reading-for">
                    For {entry.querents.find(q => q.id === reading.querent_id)!.name}
                  </div>
                )}
                <SpreadDisplay
                  reading={reading}
                  onCardDoubleClick={setViewingCardId}
                  birthLabels={indicateBirthCards && showBirthCardControls
                    ? querentBirthCards.labelsByArchetype
                    : undefined}
                />
                {(reading.notes || '').replace(/<[^>]*>/g, '').trim() && (
                  <div className="entry-viewer__reading-notes">
                    <RichTextViewer content={reading.notes!} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Reading Breakdown — collapsible category-count panel */}
        {entry.readings.length > 0 && <ReadingBreakdown entry={entry} />}

        {/* Notes / Content */}
        {entry.content && (
          <div className="entry-viewer__section">
            <h3 className="entry-viewer__section-title">Notes</h3>
            <RichTextViewer content={entry.content} />
          </div>
        )}

        {/* Follow-up Notes */}
        <div className="entry-viewer__section">
          <FollowUpNotes entryId={entryId} notes={entry.follow_up_notes} />
        </div>
      </div>

      {/* Card View Modal */}
      {viewingCardId !== null && (
        <CardViewModal
          cardId={viewingCardId}
          cardIds={allCardIds}
          onClose={() => setViewingCardId(null)}
          onNavigate={setViewingCardId}
          onEdit={(id) => {
            setViewingCardId(null);
            setEditingCardId(id);
          }}
          onFindInJournal={onFindCardInJournal}
        />
      )}

      {/* Card Edit Modal */}
      {editingCardId !== null && (
        <CardEditModal
          cardId={editingCardId}
          deckId={cardToDeckMap.get(editingCardId) ?? null}
          cardIds={allCardIds}
          onClose={() => setEditingCardId(null)}
          onSaved={() => {}}
          onNavigate={setEditingCardId}
        />
      )}

      {/* Event Chart Modal */}
      <ChartModal
        open={chartOpen}
        onClose={() => setChartOpen(false)}
        source={{ type: 'entry', id: entryId, name: entry.title }}
      />

      {/* PDF Export Modal */}
      <PdfExportModal
        entry={entry}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
      />

      {/* Mirror (reflection) Modal */}
      <MirrorModal
        entryId={entryId}
        entryTitle={entry.title}
        open={mirrorOpen}
        onClose={() => setMirrorOpen(false)}
      />
    </div>
  );
}
