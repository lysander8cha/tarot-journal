import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getDeck, updateDeck, deleteDeck, getDeckTagAssignments, setDeckTags, getCartomancyTypes,
  getDeckCustomFields, addDeckCustomField, updateDeckCustomField, deleteDeckCustomField,
  getDeckTypes, setDeckTypes, updateDeckSuitNames, updateDeckCourtNames,
  getDeckGroups, addDeckGroup, updateDeckGroup, deleteDeckGroup,
} from '../../api/decks';
import { getDeckTags } from '../../api/tags';
import { deckBackUrl } from '../../api/images';
import { exportDeckUrl } from '../../api/importExport';
import type { Deck, Tag, DeckCustomField, CardGroup } from '../../types';
import Modal from '../common/Modal';
import RichTextEditor from '../common/RichTextEditor';
import './DeckEditModal.css';

/** Convert plain text (with newlines) to HTML paragraphs if it doesn't already contain HTML tags. */
function ensureHtml(text: string): string {
  if (!text) return '';
  // If it already contains HTML tags, return as-is
  if (/<[a-z][\s\S]*>/i.test(text)) return text;
  // Convert plain text: split on newlines, wrap each line in <p>
  return text
    .split('\n')
    .map((line) => `<p>${line || '<br>'}</p>`)
    .join('');
}

interface InitialDeckFormState {
  name: string;
  datePublished: string;
  publisher: string;
  credits: string;
  notes: string;
  bookletInfo: string;
  selectedTypeIds: number[];
  selectedTagIds: number[];
  suitNames: Record<string, string>;
  courtNames: Record<string, string>;
}

interface DeckEditModalProps {
  deckId: number | null;
  onClose: () => void;
  onSaved: () => void;
  onDeleted?: () => void;
}

export default function DeckEditModal({ deckId, onClose, onSaved, onDeleted }: DeckEditModalProps) {
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

  const { data: groups = [], refetch: refetchGroups } = useQuery<CardGroup[]>({
    queryKey: ['deck-groups', deckId],
    queryFn: () => getDeckGroups(deckId!),
    enabled: deckId !== null,
  });

  // Local ordered copy for optimistic drag reordering
  const [localFields, setLocalFields] = useState<DeckCustomField[]>([]);
  const [dragOverId, setDragOverId] = useState<number | null>(null);
  const draggingIdRef = useRef<number | null>(null);
  const localFieldsRef = useRef<DeckCustomField[]>([]);

  const { data: deckTypeAssignments = [] } = useQuery<{ id: number; name: string }[]>({
    queryKey: ['deck-types', deckId],
    queryFn: () => getDeckTypes(deckId!),
    enabled: deckId !== null,
  });

  // Standard suit/court keys (lowercase for database) with default display names
  const TAROT_SUIT_DEFAULTS: Record<string, string> = {
    wands: 'Wands', cups: 'Cups', swords: 'Swords', pentacles: 'Pentacles'
  };
  const PLAYING_SUIT_DEFAULTS: Record<string, string> = {
    hearts: 'Hearts', diamonds: 'Diamonds', clubs: 'Clubs', spades: 'Spades'
  };
  const COURT_CARD_DEFAULTS: Record<string, string> = {
    page: 'Page', knight: 'Knight', queen: 'Queen', king: 'King'
  };

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
  const [originalSuitNames, setOriginalSuitNames] = useState<Record<string, string>>({});
  const [originalCourtNames, setOriginalCourtNames] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Track initial form state for dirty checking
  const initialStateRef = useRef<InitialDeckFormState | null>(null);
  const formPopulatedRef = useRef(false);

  // Determine which suit/court options to show based on selected types
  const selectedTypeNames = types
    .filter(t => selectedTypeIds.includes(t.id))
    .map(t => t.name.toLowerCase());

  const hasTarot = selectedTypeNames.some(n => n.includes('tarot'));
  const hasPlayingCards = selectedTypeNames.some(n =>
    n.includes('playing') || n.includes('poker') || n.includes('bridge')
  );
  const hasSuitedDeck = hasTarot || hasPlayingCards;

  // Get the appropriate default suits for current deck type
  const getDefaultSuits = (): Record<string, string> => {
    if (hasTarot) return TAROT_SUIT_DEFAULTS;
    if (hasPlayingCards) return PLAYING_SUIT_DEFAULTS;
    return TAROT_SUIT_DEFAULTS; // fallback
  };

  // Capitalize key for display label
  const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

  useEffect(() => {
    setConfirmingDelete(false);
  }, [deckId]);

  useEffect(() => {
    if (deck) {
      setName(deck.name);
      setDatePublished(deck.date_published || '');
      setPublisher(deck.publisher || '');
      setCredits(deck.credits || '');
      setNotes(deck.notes || '');
      setBookletInfo(deck.booklet_info || '');

      // Parse suit and court names JSON, and save originals for card renaming
      try {
        const parsed = deck.suit_names ? JSON.parse(deck.suit_names) : {};
        setSuitNames(parsed);
        setOriginalSuitNames(parsed);
      } catch {
        setSuitNames({});
        setOriginalSuitNames({});
      }
      try {
        const parsed = deck.court_names ? JSON.parse(deck.court_names) : {};
        setCourtNames(parsed);
        setOriginalCourtNames(parsed);
      } catch {
        setCourtNames({});
        setOriginalCourtNames({});
      }
    }
  }, [deck]);

  useEffect(() => {
    setSelectedTagIds(deckTagAssignments.map(t => t.id));
  }, [deckTagAssignments]);

  useEffect(() => {
    setSelectedTypeIds(deckTypeAssignments.map(t => t.id));
  }, [deckTypeAssignments]);

  // Store initial state once all data is loaded (only once per deck)
  useEffect(() => {
    if (deck && !formPopulatedRef.current) {
      formPopulatedRef.current = true;
      const suitNamesVal = (() => {
        try {
          return deck.suit_names ? JSON.parse(deck.suit_names) : {};
        } catch { return {}; }
      })();
      const courtNamesVal = (() => {
        try {
          return deck.court_names ? JSON.parse(deck.court_names) : {};
        } catch { return {}; }
      })();

      initialStateRef.current = {
        name: deck.name,
        datePublished: deck.date_published || '',
        publisher: deck.publisher || '',
        credits: deck.credits || '',
        notes: deck.notes || '',
        bookletInfo: deck.booklet_info || '',
        selectedTypeIds: deckTypeAssignments.map(t => t.id),
        selectedTagIds: deckTagAssignments.map(t => t.id),
        suitNames: suitNamesVal,
        courtNames: courtNamesVal,
      };
    }
  }, [deck, deckTagAssignments, deckTypeAssignments]);

  // Reset tracking when deck changes
  useEffect(() => {
    formPopulatedRef.current = false;
    initialStateRef.current = null;
  }, [deckId]);

  // Sync local fields from server (but not while dragging)
  useEffect(() => {
    if (!draggingIdRef.current) {
      setLocalFields([...customFields]);
    }
  }, [customFields]);

  // Keep ref in sync so drag handlers always see current order
  useEffect(() => {
    localFieldsRef.current = localFields;
  }, [localFields]);

  // Compute whether form has unsaved changes
  // NOTE: This must be before any early returns to comply with Rules of Hooks
  const isDirty = useMemo(() => {
    const initial = initialStateRef.current;
    if (!initial) return false;

    if (name !== initial.name) return true;
    if (datePublished !== initial.datePublished) return true;
    if (publisher !== initial.publisher) return true;
    if (credits !== initial.credits) return true;
    if (notes !== initial.notes) return true;
    if (bookletInfo !== initial.bookletInfo) return true;

    // Compare type selections
    if (selectedTypeIds.length !== initial.selectedTypeIds.length) return true;
    if (!selectedTypeIds.every(id => initial.selectedTypeIds.includes(id))) return true;

    // Compare tag selections
    if (selectedTagIds.length !== initial.selectedTagIds.length) return true;
    if (!selectedTagIds.every(id => initial.selectedTagIds.includes(id))) return true;

    // Compare suit/court names
    if (JSON.stringify(suitNames) !== JSON.stringify(initial.suitNames)) return true;
    if (JSON.stringify(courtNames) !== JSON.stringify(initial.courtNames)) return true;

    return false;
  }, [name, datePublished, publisher, credits, notes, bookletInfo, selectedTypeIds, selectedTagIds, suitNames, courtNames]);

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

  const handleUpdateCustomField = async (fieldId: number, updates: { field_name?: string; field_type?: string; field_options?: string[] }) => {
    await updateDeckCustomField(fieldId, updates);
    refetchCustomFields();
    // If a field was renamed, the backend cascades the rename to all card data.
    // Remove card caches so CardEditModal fetches fresh data with new field names.
    if (updates.field_name) {
      queryClient.removeQueries({ queryKey: ['card-detail'] });
      queryClient.invalidateQueries({ queryKey: ['cards'] });
    }
  };

  const handleDeleteCustomField = async (fieldId: number) => {
    if (!window.confirm('Delete this custom field? This will not remove existing values from cards.')) return;
    await deleteDeckCustomField(fieldId);
    refetchCustomFields();
  };

  const handleFieldDragStart = (fieldId: number) => {
    draggingIdRef.current = fieldId;
  };

  const handleFieldDragOver = (e: React.DragEvent, overFieldId: number) => {
    e.preventDefault();
    setDragOverId(overFieldId);
  };

  const handleFieldDrop = (e: React.DragEvent, overFieldId: number) => {
    e.preventDefault();
    const fromId = draggingIdRef.current;
    draggingIdRef.current = null;
    setDragOverId(null);
    if (!fromId || fromId === overFieldId) return;

    const next = [...localFieldsRef.current];
    const fromIdx = next.findIndex(f => f.id === fromId);
    const toIdx = next.findIndex(f => f.id === overFieldId);
    if (fromIdx === -1 || toIdx === -1) return;
    next.splice(toIdx, 0, next.splice(fromIdx, 1)[0]);
    setLocalFields(next);

    Promise.all(
      next.map((field, idx) => updateDeckCustomField(field.id, { field_order: idx }))
    ).then(() => refetchCustomFields());
  };

  const handleFieldDragEnd = () => {
    setDragOverId(null);
    draggingIdRef.current = null;
  };

  const handleAddGroup = async () => {
    if (!deck) return;
    try {
      await addDeckGroup(deck.id, { name: 'New Group' });
      refetchGroups();
    } catch (err) {
      console.error('Failed to add group:', err);
    }
  };

  const handleUpdateGroup = async (groupId: number, data: { name?: string; color?: string }) => {
    try {
      await updateDeckGroup(groupId, data);
      refetchGroups();
    } catch (err) {
      console.error('Failed to update group:', err);
    }
  };

  const handleDeleteGroup = async (groupId: number) => {
    try {
      await deleteDeckGroup(groupId);
      refetchGroups();
    } catch (err) {
      console.error('Failed to delete group:', err);
    }
  };

  const handleSave = async () => {
    if (!deck) return;
    setSaving(true);
    setError('');
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
      });

      // Update suit names using dedicated endpoint (also renames cards)
      const suitNamesChanged = JSON.stringify(suitNames) !== JSON.stringify(originalSuitNames);
      if (suitNamesChanged && Object.keys(suitNames).length > 0) {
        await updateDeckSuitNames(deck.id, suitNames, originalSuitNames);
      }

      // Update court names using dedicated endpoint (also renames cards)
      const courtNamesChanged = JSON.stringify(courtNames) !== JSON.stringify(originalCourtNames);
      if (courtNamesChanged && Object.keys(courtNames).length > 0) {
        await updateDeckCourtNames(deck.id, courtNames, originalCourtNames);
      }

      await setDeckTags(deck.id, selectedTagIds);
      await setDeckTypes(deck.id, selectedTypeIds);

      queryClient.invalidateQueries({ queryKey: ['deck-detail', deckId] });
      queryClient.invalidateQueries({ queryKey: ['decks'] });
      queryClient.invalidateQueries({ queryKey: ['deck-tag-assignments', deckId] });
      queryClient.invalidateQueries({ queryKey: ['deck-types', deckId] });
      queryClient.invalidateQueries({ queryKey: ['cards', deckId] }); // Refresh cards list

      onSaved();
      onClose();
    } catch (err) {
      console.error('Failed to save deck:', err);
      setError('Failed to save deck. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deck) return;
    setDeleting(true);
    setError('');
    try {
      await deleteDeck(deck.id);
      queryClient.invalidateQueries({ queryKey: ['decks'] });
      onDeleted?.();
      onClose();
    } catch (err) {
      console.error('Failed to delete deck:', err);
      setError('Failed to delete deck. Please try again.');
    } finally {
      setDeleting(false);
      setConfirmingDelete(false);
    }
  };

  return (
    <Modal open={true} onClose={onClose} width={600} isDirty={isDirty}>
      {isLoading ? (
        <div className="deck-edit__loading">Loading...</div>
      ) : deck ? (
        <div className="deck-edit">
          {error && <div className="deck-edit__error">{error}</div>}
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
              <RichTextEditor
                key={`notes-${deckId}`}
                content={ensureHtml(notes)}
                onChange={setNotes}
                placeholder="Deck notes..."
                minHeight={100}
              />
            </div>

            <div className="deck-edit__section">
              <h3 className="deck-edit__section-title">Booklet Info</h3>
              <RichTextEditor
                key={`booklet-${deckId}`}
                content={ensureHtml(bookletInfo)}
                onChange={setBookletInfo}
                placeholder="Info from the included booklet..."
                minHeight={100}
              />
            </div>

            {hasSuitedDeck && (
              <div className="deck-edit__section">
                <h3 className="deck-edit__section-title">Suit Names</h3>
                {Object.keys(suitNames).length > 0 ? (
                  <div className="deck-edit__row deck-edit__row--wrap">
                    {Object.entries(suitNames).map(([key, value]) => (
                      <div key={key} className="deck-edit__field deck-edit__field--quarter">
                        <label className="deck-edit__label">{capitalize(key)}</label>
                        <input
                          type="text"
                          value={value}
                          onChange={e => setSuitNames(prev => ({ ...prev, [key]: e.target.value }))}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="deck-edit__init-section">
                    <p className="deck-edit__init-hint">
                      No custom suit names set. Use defaults or customize below.
                    </p>
                    <button
                      type="button"
                      className="deck-edit__init-btn"
                      onClick={() => {
                        const defaults = { ...getDefaultSuits() };
                        setSuitNames(defaults);
                        setOriginalSuitNames(defaults);
                      }}
                    >
                      Set Custom Suit Names
                    </button>
                  </div>
                )}
              </div>
            )}

            {hasTarot && (
              <div className="deck-edit__section">
                <h3 className="deck-edit__section-title">Court Card Names</h3>
                {Object.keys(courtNames).length > 0 ? (
                  <div className="deck-edit__row deck-edit__row--wrap">
                    {Object.entries(courtNames).map(([key, value]) => (
                      <div key={key} className="deck-edit__field deck-edit__field--quarter">
                        <label className="deck-edit__label">{capitalize(key)}</label>
                        <input
                          type="text"
                          value={value}
                          onChange={e => setCourtNames(prev => ({ ...prev, [key]: e.target.value }))}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="deck-edit__init-section">
                    <p className="deck-edit__init-hint">
                      No custom court card names set. Use defaults or customize below.
                    </p>
                    <button
                      type="button"
                      className="deck-edit__init-btn"
                      onClick={() => {
                        const defaults = { ...COURT_CARD_DEFAULTS };
                        setCourtNames(defaults);
                        setOriginalCourtNames(defaults);
                      }}
                    >
                      Set Custom Court Names
                    </button>
                  </div>
                )}
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
                <h3 className="deck-edit__section-title">Groups</h3>
                <button
                  className="deck-edit__add-field-btn"
                  onClick={handleAddGroup}
                >
                  + Add Group
                </button>
              </div>
              <p className="deck-edit__section-hint">
                Organize cards into groups (e.g. Major Arcana, Suit of Cups).
              </p>
              {groups.length > 0 ? (
                <div className="deck-edit__custom-fields">
                  {groups.map(group => (
                    <div key={group.id} className="deck-edit__custom-field">
                      <div className="deck-edit__custom-field-row">
                        <input
                          type="color"
                          className="deck-edit__group-color"
                          defaultValue={group.color}
                          onChange={e => handleUpdateGroup(group.id, { color: e.target.value })}
                          title="Group color"
                        />
                        <input
                          className="deck-edit__custom-field-name"
                          type="text"
                          defaultValue={group.name}
                          onBlur={e => {
                            const val = e.target.value.trim();
                            if (val && val !== group.name) {
                              handleUpdateGroup(group.id, { name: val });
                            }
                          }}
                          placeholder="Group name"
                        />
                        <button
                          className="deck-edit__custom-field-delete"
                          onClick={() => handleDeleteGroup(group.id)}
                          title="Delete group"
                        >
                          &times;
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="deck-edit__custom-fields-empty">
                  No groups defined.
                </div>
              )}
            </div>

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
              {localFields.length > 0 ? (
                <div className="deck-edit__custom-fields">
                  {localFields.map(field => (
                    <div
                      key={field.id}
                      className={`deck-edit__custom-field${dragOverId === field.id ? ' deck-edit__custom-field--drag-over' : ''}`}
                      onDragOver={e => handleFieldDragOver(e, field.id)}
                      onDrop={e => handleFieldDrop(e, field.id)}
                    >
                      <div className="deck-edit__custom-field-row">
                        <div
                          className="deck-edit__drag-handle"
                          draggable
                          onDragStart={() => handleFieldDragStart(field.id)}
                          onDragEnd={handleFieldDragEnd}
                          title="Drag to reorder"
                        >
                          ⠿
                        </div>
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
                      {field.field_type === 'select' && (
                        <div className="deck-edit__custom-field-options">
                          <label className="deck-edit__custom-field-options-label">
                            Options (one per line):
                          </label>
                          <textarea
                            className="deck-edit__custom-field-options-input"
                            defaultValue={(() => {
                              if (!field.field_options) return '';
                              try {
                                const opts = JSON.parse(field.field_options);
                                return Array.isArray(opts) ? opts.join('\n') : '';
                              } catch { return ''; }
                            })()}
                            onBlur={e => {
                              const lines = e.target.value.split('\n').map(l => l.trim()).filter(Boolean);
                              handleUpdateCustomField(field.id, { field_options: lines });
                            }}
                            placeholder="Option 1&#10;Option 2&#10;Option 3"
                            rows={4}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : customFields.length === 0 ? (
                <div className="deck-edit__custom-fields-empty">
                  No custom fields defined.
                </div>
              ) : null}
            </div>
          </div>

          {confirmingDelete ? (
            <div className="deck-edit__delete-confirm">
              <p className="deck-edit__delete-warning">
                Are you sure you want to delete <strong>{name || 'this deck'}</strong>?
              </p>
              <p className="deck-edit__delete-warning-detail">
                This will permanently delete the deck, all its cards, custom fields, and tags.
                This action cannot be undone.
              </p>
              <div className="deck-edit__delete-confirm-actions">
                <button onClick={() => setConfirmingDelete(false)} disabled={deleting}>
                  Cancel
                </button>
                <button
                  className="deck-edit__delete-btn"
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  {deleting ? 'Deleting...' : 'Yes, delete permanently'}
                </button>
              </div>
            </div>
          ) : (
            <div className="deck-edit__footer">
              <a
                className="deck-edit__export-link"
                href={exportDeckUrl(deckId)}
                download
              >
                Export JSON
              </a>
              <button
                className="deck-edit__delete-trigger"
                onClick={() => setConfirmingDelete(true)}
              >
                Delete Deck
              </button>
              <div className="deck-edit__footer-spacer" />
              <button onClick={onClose}>Cancel</button>
              <button
                className="deck-edit__save-btn"
                onClick={handleSave}
                disabled={saving || !name.trim()}
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          )}
        </div>
      ) : null}
    </Modal>
  );
}
