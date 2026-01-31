import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { updateCardMetadata, setCardTags, setCardGroups, getCard } from '../../api/cards';
import { getCardTags } from '../../api/tags';
import { getDeckGroups } from '../../api/decks';
import type { Tag, CardGroup } from '../../types';
import Modal from '../common/Modal';
import './BatchEditModal.css';

interface BatchEditModalProps {
  cardIds: number[];
  deckId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

type FieldAction = 'skip' | 'set' | 'clear';
type NotesAction = 'skip' | 'set' | 'append' | 'clear';
type TagAction = 'skip' | 'add' | 'remove' | 'set';

export default function BatchEditModal({ cardIds, deckId, onClose, onSaved }: BatchEditModalProps) {
  const queryClient = useQueryClient();

  const { data: allTags = [] } = useQuery({
    queryKey: ['card-tags'],
    queryFn: getCardTags,
    enabled: cardIds.length > 0,
  });

  const { data: allGroups = [] } = useQuery({
    queryKey: ['deck-groups', deckId],
    queryFn: () => getDeckGroups(deckId!),
    enabled: deckId !== null && cardIds.length > 0,
  });

  // Field actions
  const [archetypeAction, setArchetypeAction] = useState<FieldAction>('skip');
  const [archetype, setArchetype] = useState('');
  const [rankAction, setRankAction] = useState<FieldAction>('skip');
  const [rank, setRank] = useState('');
  const [suitAction, setSuitAction] = useState<FieldAction>('skip');
  const [suit, setSuit] = useState('');
  const [notesAction, setNotesAction] = useState<NotesAction>('skip');
  const [notes, setNotes] = useState('');

  // Tag/group actions
  const [tagAction, setTagAction] = useState<TagAction>('skip');
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [groupAction, setGroupAction] = useState<TagAction>('skip');
  const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([]);

  const [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [failedCards, setFailedCards] = useState<number[]>([]);

  if (cardIds.length === 0) return null;

  const toggleTag = (id: number) => {
    setSelectedTagIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };
  const toggleGroup = (id: number) => {
    setSelectedGroupIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const handleSave = async () => {
    setSaving(true);
    setProgress(0);
    setError(null);
    setFailedCards([]);

    const failed: number[] = [];

    for (let i = 0; i < cardIds.length; i++) {
      const cardId = cardIds[i];

      try {
        // Update metadata if any field action is not 'skip'
        if (archetypeAction !== 'skip' || rankAction !== 'skip' || suitAction !== 'skip' || notesAction !== 'skip') {
          const meta: Record<string, string> = {};

          if (archetypeAction === 'set') meta.archetype = archetype;
          else if (archetypeAction === 'clear') meta.archetype = '';

          if (rankAction === 'set') meta.rank = rank;
          else if (rankAction === 'clear') meta.rank = '';

          if (suitAction === 'set') meta.suit = suit;
          else if (suitAction === 'clear') meta.suit = '';

          if (notesAction === 'set') {
            meta.notes = notes;
          } else if (notesAction === 'append') {
            // Fetch existing notes and append
            const card = await getCard(cardId);
            meta.notes = ((card.notes || '') + '\n' + notes).trim();
          } else if (notesAction === 'clear') {
            meta.notes = '';
          }

          if (Object.keys(meta).length > 0) {
            await updateCardMetadata(cardId, meta);
          }
        }

        // Update tags if action is not 'skip'
        if (tagAction !== 'skip' && selectedTagIds.length > 0) {
          if (tagAction === 'set') {
            await setCardTags(cardId, selectedTagIds);
          } else {
            // For add/remove, fetch existing tags first
            const card = await getCard(cardId);
            const existingIds = (card as any).own_tags?.map((t: Tag) => t.id) || [];
            let newIds: number[];
            if (tagAction === 'add') {
              newIds = Array.from(new Set([...existingIds, ...selectedTagIds]));
            } else {
              newIds = existingIds.filter((id: number) => !selectedTagIds.includes(id));
            }
            await setCardTags(cardId, newIds);
          }
        }

        // Update groups if action is not 'skip'
        if (groupAction !== 'skip' && selectedGroupIds.length > 0) {
          if (groupAction === 'set') {
            await setCardGroups(cardId, selectedGroupIds);
          } else {
            const card = await getCard(cardId);
            const existingIds = (card as any).groups?.map((g: CardGroup) => g.id) || [];
            let newIds: number[];
            if (groupAction === 'add') {
              newIds = Array.from(new Set([...existingIds, ...selectedGroupIds]));
            } else {
              newIds = existingIds.filter((id: number) => !selectedGroupIds.includes(id));
            }
            await setCardGroups(cardId, newIds);
          }
        }
      } catch (err) {
        console.error(`Failed to update card ${cardId}:`, err);
        failed.push(cardId);
      }

      setProgress(i + 1);
    }

    queryClient.invalidateQueries({ queryKey: ['cards'] });
    queryClient.invalidateQueries({ queryKey: ['card-search'] });
    queryClient.invalidateQueries({ queryKey: ['card-detail'] });

    if (failed.length > 0) {
      setFailedCards(failed);
      const successCount = cardIds.length - failed.length;
      if (successCount === 0) {
        setError(`Failed to update all ${failed.length} cards.`);
      } else {
        setError(`Updated ${successCount} cards successfully, but ${failed.length} failed.`);
      }
      // Log full list to console for debugging
      if (failed.length > 10) {
        console.warn('Full list of failed card IDs:', failed);
      }
      setSaving(false);
    } else {
      onSaved();
      onClose();
      setSaving(false);
    }
  };

  const hasChanges =
    archetypeAction !== 'skip' ||
    rankAction !== 'skip' ||
    suitAction !== 'skip' ||
    notesAction !== 'skip' ||
    (tagAction !== 'skip' && selectedTagIds.length > 0) ||
    (groupAction !== 'skip' && selectedGroupIds.length > 0);

  return (
    <Modal open={true} onClose={onClose} width={550} isDirty={hasChanges}>
      <div className="batch-edit">
        <h2 className="batch-edit__title">
          Batch Edit ({cardIds.length} card{cardIds.length !== 1 ? 's' : ''})
        </h2>

        <div className="batch-edit__form">
          <FieldRow
            label="Archetype"
            action={archetypeAction}
            onActionChange={setArchetypeAction}
            value={archetype}
            onValueChange={setArchetype}
          />
          <FieldRow
            label="Rank"
            action={rankAction}
            onActionChange={setRankAction}
            value={rank}
            onValueChange={setRank}
          />
          <FieldRow
            label="Suit"
            action={suitAction}
            onActionChange={setSuitAction}
            value={suit}
            onValueChange={setSuit}
          />

          <div className="batch-edit__section">
            <div className="batch-edit__field-header">
              <span className="batch-edit__label">Notes</span>
              <select
                value={notesAction}
                onChange={e => setNotesAction(e.target.value as NotesAction)}
              >
                <option value="skip">Skip</option>
                <option value="set">Replace</option>
                <option value="append">Append</option>
                <option value="clear">Clear</option>
              </select>
            </div>
            {(notesAction === 'set' || notesAction === 'append') && (
              <textarea
                className="batch-edit__notes"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={3}
              />
            )}
          </div>

          {allTags.length > 0 && (
            <div className="batch-edit__section">
              <div className="batch-edit__field-header">
                <span className="batch-edit__label">Tags</span>
                <select
                  value={tagAction}
                  onChange={e => setTagAction(e.target.value as TagAction)}
                >
                  <option value="skip">Skip</option>
                  <option value="add">Add</option>
                  <option value="remove">Remove</option>
                  <option value="set">Replace All</option>
                </select>
              </div>
              {tagAction !== 'skip' && (
                <div className="batch-edit__checkboxes">
                  {allTags.map(tag => (
                    <label key={tag.id} className="batch-edit__check">
                      <input
                        type="checkbox"
                        checked={selectedTagIds.includes(tag.id)}
                        onChange={() => toggleTag(tag.id)}
                      />
                      <span className="batch-edit__tag-badge" style={{ backgroundColor: tag.color }}>
                        {tag.name}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {allGroups.length > 0 && (
            <div className="batch-edit__section">
              <div className="batch-edit__field-header">
                <span className="batch-edit__label">Groups</span>
                <select
                  value={groupAction}
                  onChange={e => setGroupAction(e.target.value as TagAction)}
                >
                  <option value="skip">Skip</option>
                  <option value="add">Add</option>
                  <option value="remove">Remove</option>
                  <option value="set">Replace All</option>
                </select>
              </div>
              {groupAction !== 'skip' && (
                <div className="batch-edit__checkboxes">
                  {allGroups.map(group => (
                    <label key={group.id} className="batch-edit__check">
                      <input
                        type="checkbox"
                        checked={selectedGroupIds.includes(group.id)}
                        onChange={() => toggleGroup(group.id)}
                      />
                      <span className="batch-edit__group-badge" style={{ borderColor: group.color }}>
                        {group.name}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="batch-edit__footer">
          {error && (
            <div className="batch-edit__error">
              <div>{error}</div>
              {failedCards.length > 0 && (
                <div className="batch-edit__failed-ids">
                  {failedCards.length <= 10 ? (
                    <>Failed card IDs: {failedCards.join(', ')}</>
                  ) : (
                    <>Failed card IDs: {failedCards.slice(0, 10).join(', ')} and {failedCards.length - 10} more (see browser console for full list)</>
                  )}
                </div>
              )}
            </div>
          )}
          <div className="batch-edit__footer-row">
            {saving && (
              <span className="batch-edit__progress">
                {progress} / {cardIds.length}
              </span>
            )}
            <div className="batch-edit__footer-buttons">
              <button onClick={onClose} disabled={saving}>
                {error ? 'Close' : 'Cancel'}
              </button>
              {!error && (
                <button
                  className="batch-edit__save-btn"
                  onClick={handleSave}
                  disabled={saving || !hasChanges}
                >
                  {saving ? 'Saving...' : 'Apply'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}

function FieldRow({
  label,
  action,
  onActionChange,
  value,
  onValueChange,
}: {
  label: string;
  action: FieldAction;
  onActionChange: (a: FieldAction) => void;
  value: string;
  onValueChange: (v: string) => void;
}) {
  return (
    <div className="batch-edit__section">
      <div className="batch-edit__field-header">
        <span className="batch-edit__label">{label}</span>
        <select value={action} onChange={e => onActionChange(e.target.value as FieldAction)}>
          <option value="skip">Skip</option>
          <option value="set">Set</option>
          <option value="clear">Clear</option>
        </select>
      </div>
      {action === 'set' && (
        <input type="text" value={value} onChange={e => onValueChange(e.target.value)} />
      )}
    </div>
  );
}
