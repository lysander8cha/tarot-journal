import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getDeck, updateDeck, getDeckTagAssignments, setDeckTags, getCartomancyTypes,
  getDeckCustomFields, addDeckCustomField, updateDeckCustomField, deleteDeckCustomField,
  getDeckTypes, setDeckTypes,
} from '../../api/decks';
import { getDeckTags } from '../../api/tags';
import { deckBackUrl } from '../../api/images';
import { exportDeckUrl } from '../../api/importExport';
import type { Deck, Tag, DeckCustomField } from '../../types';
import Modal from '../common/Modal';
import './DeckEditModal.css';

interface DeckEditModalProps {
  deckId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

export default function DeckEditModal({ deckId, onClose, onSaved }: DeckEditModalProps) {
  const queryClient = useQueryClient();

  const { data: deck, isLoading } = useQuery<Deck>({
    queryKey: ['deck-detail', deckId],
    queryFn: () => getDeck(deckId!),
    enabled: deckId !== null,
  });

  const { data: deckTagAssignments = [] } = useQuery<Tag[]>({
    queryKey: ['deck-tag-assignments', deckId],
    queryFn: () => getDeckTagAssignments(deckId!),
    enabled: deckId !== null,
  });

  const { data: allDeckTags = [] } = useQuery({
    queryKey: ['deck-tags'],
    queryFn: getDeckTags,
    enabled: deckId !== null,
  });

  const { data: types = [] } = useQuery({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
    enabled: deckId !== null,
  });

  const { data: customFields = [], refetch: refetchCustomFields } = useQuery<DeckCustomField[]>({
    queryKey: ['deck-custom-fields', deckId],
    queryFn: () => getDeckCustomFields(deckId!),
    enabled: deckId !== null,
  });

  const { data: deckTypeAssignments = [] } = useQuery<{ id: number; name: string }[]>({
    queryKey: ['deck-types', deckId],
    queryFn: () => getDeckTypes(deckId!),
    enabled: deckId !== null,
  });

  // Form state
  const [name, setName] = useState('');
  const [selectedTypeIds, setSelectedTypeIds] = useState<number[]>([]);
  const [datePublished, setDatePublished] = useState('');
  const [publisher, setPublisher] = useState('');
  const [credits, setCredits] = useState('');
  const [notes, setNotes] = useState('');
  const [bookletInfo, setBookletInfo] = useState('');
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [suitNames, setSuitNames] = useState<Record<string, string>>({});
  const [courtNames, setCourtNames] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (deck) {
      setName(deck.name);
      setDatePublished(deck.date_published || '');
      setPublisher(deck.publisher || '');
      setCredits(deck.credits || '');
      setNotes(deck.notes || '');
      setBookletInfo(deck.booklet_info || '');

      // Parse suit and court names JSON
      try {
        setSuitNames(deck.suit_names ? JSON.parse(deck.suit_names) : {});
      } catch { setSuitNames({}); }
      try {
        setCourtNames(deck.court_names ? JSON.parse(deck.court_names) : {});
      } catch { setCourtNames({}); }
    }
  }, [deck]);

  useEffect(() => {
    setSelectedTagIds(deckTagAssignments.map(t => t.id));
  }, [deckTagAssignments]);

  useEffect(() => {
    setSelectedTypeIds(deckTypeAssignments.map(t => t.id));
  }, [deckTypeAssignments]);

  if (deckId === null) return null;

  const toggleTag = (tagId: number) => {
    setSelectedTagIds(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
  };

  const toggleType = (typeId: number) => {
    setSelectedTypeIds(prev => {
      if (prev.includes(typeId)) {
        // Don't allow removing the last type
        if (prev.length === 1) return prev;
        return prev.filter(id => id !== typeId);
      }
      return [...prev, typeId];
    });
  };

  const handleAddCustomField = async () => {
    if (!deckId) return;
    await addDeckCustomField(deckId, {
      field_name: 'New Field',
      field_type: 'text',
      field_order: customFields.length,
    });
    refetchCustomFields();
  };

  const handleUpdateCustomField = async (fieldId: number, updates: { field_name?: string; field_type?: string }) => {
    await updateDeckCustomField(fieldId, updates);
    refetchCustomFields();
  };

  const handleDeleteCustomField = async (fieldId: number) => {
    if (!window.confirm('Delete this custom field? This will not remove existing values from cards.')) return;
    await deleteDeckCustomField(fieldId);
    refetchCustomFields();
  };

  const handleSave = async () => {
    if (!deck) return;
    setSaving(true);
    try {
      // Use the first selected type as the primary cartomancy_type_id
      const primaryTypeId = selectedTypeIds[0] || deck.cartomancy_type_id;

      await updateDeck(deck.id, {
        name,
        cartomancy_type_id: primaryTypeId,
        date_published: datePublished || null,
        publisher: publisher || null,
        credits: credits || null,
        notes: notes || null,
        booklet_info: bookletInfo || null,
        suit_names: Object.keys(suitNames).length > 0 ? suitNames : null,
        court_names: Object.keys(courtNames).length > 0 ? courtNames : null,
      });

      await setDeckTags(deck.id, selectedTagIds);
      await setDeckTypes(deck.id, selectedTypeIds);

      queryClient.invalidateQueries({ queryKey: ['deck-detail', deckId] });
      queryClient.invalidateQueries({ queryKey: ['decks'] });
      queryClient.invalidateQueries({ queryKey: ['deck-tag-assignments', deckId] });
      queryClient.invalidateQueries({ queryKey: ['deck-types', deckId] });

      onSaved();
      onClose();
    } catch (err) {
      console.error('Failed to save deck:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={true} onClose={onClose} width={600}>
      {isLoading ? (
        <div className="deck-edit__loading">Loading...</div>
      ) : deck ? (
        <div className="deck-edit">
          <div className="deck-edit__header">
            {deck.card_back_image && (
              <img className="deck-edit__back-img" src={deckBackUrl(deck.id)} alt="Deck back" />
            )}
            <h2 className="deck-edit__title">Edit Deck</h2>
          </div>

          <div className="deck-edit__form">
            <div className="deck-edit__section">
              <div className="deck-edit__field">
                <label className="deck-edit__label">Name</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} />
              </div>

              <div className="deck-edit__field">
                <label className="deck-edit__label">Cartomancy Types</label>
                <div className="deck-edit__checkboxes deck-edit__checkboxes--types">
                  {types.map(t => (
                    <label key={t.id} className="deck-edit__check">
                      <input
                        type="checkbox"
                        checked={selectedTypeIds.includes(t.id)}
                        onChange={() => toggleType(t.id)}
                      />
                      <span>{t.name}</span>
                    </label>
                  ))}
                </div>
                <p className="deck-edit__type-hint">
                  Select all types that apply to this deck.
                </p>
              </div>
            </div>

            <div className="deck-edit__section">
              <h3 className="deck-edit__section-title">Publisher Info</h3>
              <div className="deck-edit__row">
                <div className="deck-edit__field" style={{ flex: 1 }}>
                  <label className="deck-edit__label">Date Published</label>
                  <input
                    type="text"
                    value={datePublished}
                    onChange={e => setDatePublished(e.target.value)}
                    placeholder="e.g. 2020"
                  />
                </div>
                <div className="deck-edit__field" style={{ flex: 1 }}>
                  <label className="deck-edit__label">Publisher</label>
                  <input
                    type="text"
                    value={publisher}
                    onChange={e => setPublisher(e.target.value)}
                  />
                </div>
              </div>
              <div className="deck-edit__field">
                <label className="deck-edit__label">Credits</label>
                <input
                  type="text"
                  value={credits}
                  onChange={e => setCredits(e.target.value)}
                  placeholder="Artist, author, etc."
                />
              </div>
            </div>

            <div className="deck-edit__section">
              <h3 className="deck-edit__section-title">Notes</h3>
              <textarea
                className="deck-edit__notes"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={4}
                placeholder="Deck notes..."
              />
            </div>

            <div className="deck-edit__section">
              <h3 className="deck-edit__section-title">Booklet Info</h3>
              <textarea
                className="deck-edit__notes"
                value={bookletInfo}
                onChange={e => setBookletInfo(e.target.value)}
                rows={3}
                placeholder="Info from the included booklet..."
              />
            </div>

            {Object.keys(suitNames).length > 0 && (
              <div className="deck-edit__section">
                <h3 className="deck-edit__section-title">Suit Names</h3>
                <div className="deck-edit__row deck-edit__row--wrap">
                  {Object.entries(suitNames).map(([key, value]) => (
                    <div key={key} className="deck-edit__field deck-edit__field--quarter">
                      <label className="deck-edit__label">{key}</label>
                      <input
                        type="text"
                        value={value}
                        onChange={e => setSuitNames(prev => ({ ...prev, [key]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(courtNames).length > 0 && (
              <div className="deck-edit__section">
                <h3 className="deck-edit__section-title">Court Names</h3>
                <div className="deck-edit__row deck-edit__row--wrap">
                  {Object.entries(courtNames).map(([key, value]) => (
                    <div key={key} className="deck-edit__field deck-edit__field--quarter">
                      <label className="deck-edit__label">{key}</label>
                      <input
                        type="text"
                        value={value}
                        onChange={e => setCourtNames(prev => ({ ...prev, [key]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {allDeckTags.length > 0 && (
              <div className="deck-edit__section">
                <h3 className="deck-edit__section-title">Tags</h3>
                <div className="deck-edit__checkboxes">
                  {allDeckTags.map(tag => (
                    <label key={tag.id} className="deck-edit__check">
                      <input
                        type="checkbox"
                        checked={selectedTagIds.includes(tag.id)}
                        onChange={() => toggleTag(tag.id)}
                      />
                      <span
                        className="deck-edit__tag-badge"
                        style={{ backgroundColor: tag.color }}
                      >
                        {tag.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className="deck-edit__section">
              <div className="deck-edit__section-header">
                <h3 className="deck-edit__section-title">Custom Fields</h3>
                <button
                  className="deck-edit__add-field-btn"
                  onClick={handleAddCustomField}
                >
                  + Add Field
                </button>
              </div>
              <p className="deck-edit__section-hint">
                Define extra fields that appear on each card in this deck.
              </p>
              {customFields.length > 0 ? (
                <div className="deck-edit__custom-fields">
                  {customFields.map(field => (
                    <div key={field.id} className="deck-edit__custom-field-row">
                      <input
                        className="deck-edit__custom-field-name"
                        type="text"
                        defaultValue={field.field_name}
                        onBlur={e => {
                          const val = e.target.value.trim();
                          if (val && val !== field.field_name) {
                            handleUpdateCustomField(field.id, { field_name: val });
                          }
                        }}
                        placeholder="Field name"
                      />
                      <select
                        className="deck-edit__custom-field-type"
                        defaultValue={field.field_type}
                        onChange={e => handleUpdateCustomField(field.id, { field_type: e.target.value })}
                      >
                        <option value="text">Text</option>
                        <option value="number">Number</option>
                        <option value="select">Dropdown</option>
                      </select>
                      <button
                        className="deck-edit__custom-field-delete"
                        onClick={() => handleDeleteCustomField(field.id)}
                        title="Delete field"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="deck-edit__custom-fields-empty">
                  No custom fields defined.
                </div>
              )}
            </div>
          </div>

          <div className="deck-edit__footer">
            <a
              className="deck-edit__export-link"
              href={exportDeckUrl(deckId)}
              download
            >
              Export JSON
            </a>
            <button onClick={onClose}>Cancel</button>
            <button
              className="deck-edit__save-btn"
              onClick={handleSave}
              disabled={saving || !name.trim()}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
