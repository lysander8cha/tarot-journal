import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getEntry, deleteEntry } from '../../api/entries';
import RichTextViewer from '../common/RichTextViewer';
import SpreadDisplay from './SpreadDisplay';
import FollowUpNotes from './FollowUpNotes';
import CardViewModal from '../library/CardViewModal';
import type { JournalEntryFull } from '../../types';
import './EntryViewer.css';

interface EntryViewerProps {
  entryId: number;
  onEdit: (entryId: number) => void;
  onDeleted: () => void;
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export default function EntryViewer({ entryId, onEdit, onDeleted }: EntryViewerProps) {
  const queryClient = useQueryClient();
  const [viewingCardId, setViewingCardId] = useState<number | null>(null);

  const { data: entry, isLoading, error } = useQuery<JournalEntryFull>({
    queryKey: ['entry', entryId],
    queryFn: () => getEntry(entryId),
  });

  // Collect all card IDs from all readings for navigation in the modal
  const allCardIds = useMemo(() => {
    if (!entry) return [];
    const ids: number[] = [];
    for (const reading of entry.readings) {
      for (const card of reading.cards_used || []) {
        if (card.card_id && !ids.includes(card.card_id)) {
          ids.push(card.card_id);
        }
      }
    }
    return ids;
  }, [entry]);

  const handleDelete = async () => {
    if (!window.confirm('Delete this journal entry? This cannot be undone.')) return;
    try {
      await deleteEntry(entryId);
      queryClient.invalidateQueries({ queryKey: ['entries'] });
      queryClient.invalidateQueries({ queryKey: ['entry-search'] });
      onDeleted();
    } catch (err) {
      console.error('Failed to delete entry:', err);
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
            <button onClick={() => onEdit(entryId)}>Edit</button>
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
            <h3 className="entry-viewer__section-title">Readings</h3>
            {entry.readings.map((reading) => (
              <SpreadDisplay
                key={reading.id}
                reading={reading}
                onCardDoubleClick={setViewingCardId}
              />
            ))}
          </div>
        )}

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
        />
      )}
    </div>
  );
}
