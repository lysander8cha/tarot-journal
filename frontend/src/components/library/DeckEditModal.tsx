import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getDeck, updateDeck, deleteDeck, getDeckTagAssignments, setDeckTags, getCartomancyTypes,
  getDeckCustomFields, addDeckCustomField, updateDeckCustomField, deleteDeckCustomField,
  getDeckTypes, setDeckTypes, updateDeckSuitNames, updateDeckCourtNames,
  getDeckGroups, addDeckGroup, updateDeckGroup, deleteDeckGroup,
} from '../../api/decks';
import { getCards, updateCard } from '../../api/cards';
import { getDeckTags, addDeckTag } from '../../api/tags';
import { deckBackUrl, cardThumbnailUrl } from '../../api/images';
import { exportDeckUrl } from '../../api/importExport';
import { getCorrespondenceSystems } from '../../api/correspondences';
import type { Card, Deck, Tag, DeckCustomField, CardGroup, CorrespondenceSystem } from '../../types';
import DeckCorrespondenceOverrides from './DeckCorrespondenceOverrides';
import { ensureHtml } from '../../utils/formatting';
import { useToast } from '../../context/ToastContext';
import Modal, { ModalCancelButton } from '../common/Modal';
import RichTextEditor from '../common/RichTextEditor';
import AnkiExportModal from './AnkiExportModal';
import ScribeModal from '../scribe/ScribeModal';
import ApplyLanguageNamesModal from './ApplyLanguageNamesModal';
import './DeckEditModal.css';
import { confirmDialog } from '../common/ConfirmDialog';

interface InitialDeckFormState {
  name: string;
  datePublished: string;
  publisher: string;
  credits: string;
  notes: string;
  bookletInfo: string;
  selectedTypeIds: number[];
  selectedTagIds: number[];
  corrSystemId: number | null;
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
  const { showToast } = useToast();

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

  const { data: corrSystems = [] } = useQuery<CorrespondenceSystem[]>({
    queryKey: ['correspondence-systems'],
    queryFn: getCorrespondenceSystems,
    enabled: deckId !== null,
  });

  // Cards in this deck — used for the Variants section to surface and
  // re-order groups of same-name cards. Shares the cache with elsewhere
  // in the app via the ['cards', deckId] key.
  const { data: deckCards = [] } = useQuery<Card[]>({
    queryKey: ['cards', deckId],
    queryFn: () => (deckId != null ? getCards(deckId) : Promise.resolve([])),
    enabled: deckId !== null,
  });

  // Same-slot groups: cards sharing a card_order, regardless of whether
  // they also share a name. This covers Terra Volatile's two patterns —
  // genuine duplicates (three "Two of Cups" at card_order=202) and slot-
  // variants under different names (The Fool / The Fooless / Chaos at
  // card_order=0). Within a group cards are sorted by variant_order
  // (nulls last by id) — same tiebreak the entry editor uses.
  const variantGroups = useMemo(() => {
    const byOrder = new Map<number, Card[]>();
    for (const c of deckCards) {
      const arr = byOrder.get(c.card_order);
      if (arr) arr.push(c);
      else byOrder.set(c.card_order, [c]);
    }
    const cmp = (a: Card, b: Card) => {
      const av = a.variant_order;
      const bv = b.variant_order;
      if (av != null && bv != null) return av - bv;
      if (av != null) return -1;
      if (bv != null) return 1;
      return a.id - b.id;
    };
    return [...byOrder.entries()]
      .filter(([, list]) => list.length > 1)
      .map(([order, list]) => {
        const sorted = [...list].sort(cmp);
        const names = new Set(sorted.map(c => c.name));
        // Header uses the shared name when all cards in the slot
        // happen to share one; otherwise just identifies the slot.
        const label = names.size === 1
          ? `${sorted[0].name} (card_order ${order})`
          : `card_order ${order}`;
        return { order, label, cards: sorted };
      })
      .sort((a, b) => a.order - b.order);
  }, [deckCards]);

  // Reorder a same-name group by writing variant_order (1, 2, 3, …) on
  // each card. Leaves card_order alone so deck display position is
  // preserved — important for decks that intentionally assign the same
  // card_order to every same-name card (Terra Volatile et al.).
  const [variantBusy, setVariantBusy] = useState(false);
  const reorderVariantGroup = async (newOrder: Card[]) => {
    if (variantBusy) return;
    setVariantBusy(true);
    try {
      for (let i = 0; i < newOrder.length; i++) {
        const want = i + 1;
        if (newOrder[i].variant_order !== want) {
          await updateCard(newOrder[i].id, { variant_order: want });
        }
      }
      queryClient.invalidateQueries({ queryKey: ['cards', deckId] });
    } catch (err) {
      console.error('Failed to reorder variants:', err);
      showToast('Failed to reorder variants.');
    } finally {
      setVariantBusy(false);
    }
  };

  const moveVariant = (group: Card[], idx: number, direction: -1 | 1) => {
    const target = idx + direction;
    if (target < 0 || target >= group.length) return;
    const next = [...group];
    [next[idx], next[target]] = [next[target], next[idx]];
    return reorderVariantGroup(next);
  };

  // Standard suit/court keys (lowercase for database) with default display names
  const TAROT_SUIT_DEFAULTS: Record<string, string> = {
    wands: 'Wands', cups: 'Cups', swords: 'Swords', pentacles: 'Pentacles'
  };
  const PLAYING_SUIT_DEFAULTS: Record<string, string> = {
    hearts: 'Hearts', diamonds: 'Diamonds', clubs: 'Clubs', spades: 'Spades'
  };
  const LATIN_SUIT_DEFAULTS: Record<string, string> = {
    coins: 'Coins', cups: 'Cups', swords: 'Swords', batons: 'Batons'
  };
  const GERMAN_SUIT_DEFAULTS: Record<string, string> = {
    hearts: 'Hearts', bells: 'Bells', leaves: 'Leaves', acorns: 'Acorns'
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
  const [corrSystemId, setCorrSystemId] = useState<number | null>(null);
  const [suitNames, setSuitNames] = useState<Record<string, string>>({});
  const [courtNames, setCourtNames] = useState<Record<string, string>>({});
  const [originalSuitNames, setOriginalSuitNames] = useState<Record<string, string>>({});
  const [originalCourtNames, setOriginalCourtNames] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // Typed confirmation: deleting a whole deck requires typing its
  // name, so a stray click can never wipe one out.
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [showAnkiExport, setShowAnkiExport] = useState(false);
  const [showScribe, setShowScribe] = useState(false);
  const [showLanguageNames, setShowLanguageNames] = useState(false);

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

  // Primary cartomancy type for the deck override UI — prefer whichever type
  // the deck's currently-selected correspondence system uses, else first
  // selected deck type, else fall back to Tarot.
  const selectedSystem = corrSystems.find(s => s.id === corrSystemId);
  const overridesCartomancyType = selectedSystem?.cartomancy_type
    || types.find(t => selectedTypeIds.includes(t.id))?.name
    || 'Tarot';

  // Get the appropriate default suits for current deck type
  const getDefaultSuits = (): Record<string, string> => {
    if (hasTarot) return TAROT_SUIT_DEFAULTS;
    if (selectedTypeNames.some(n => n.includes('latin-suited'))) return LATIN_SUIT_DEFAULTS;
    if (selectedTypeNames.some(n => n.includes('german-suited'))) return GERMAN_SUIT_DEFAULTS;
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
      setCorrSystemId(deck.correspondence_system_id ?? null);

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
        corrSystemId: deck.correspondence_system_id ?? null,
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

    // Compare correspondence system
    if (corrSystemId !== initial.corrSystemId) return true;

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
    if (!(await confirmDialog('Delete this custom field? This will not remove existing values from cards.'))) return;
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
      showToast('Failed to add group.');
    }
  };

  const handleUpdateGroup = async (groupId: number, data: { name?: string; color?: string }) => {
    try {
      await updateDeckGroup(groupId, data);
      refetchGroups();
    } catch (err) {
      console.error('Failed to update group:', err);
      showToast('Failed to update group.');
    }
  };

  const handleDeleteGroup = async (groupId: number) => {
    try {
      await deleteDeckGroup(groupId);
      refetchGroups();
    } catch (err) {
      console.error('Failed to delete group:', err);
      showToast('Failed to delete group.');
    }
  };

  const handleSave = async () => {
    if (!deck) return;
    setSaving(true);
    setError('');
    try {
      await updateDeck(deck.id, {
        name,
        date_published: datePublished || null,
        publisher: publisher || null,
        credits: credits || null,
        notes: notes || null,
        booklet_info: bookletInfo || null,
        correspondence_system_id: corrSystemId === null ? -1 : corrSystemId,
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
      showToast('Failed to save deck.');
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
      showToast('Failed to delete deck.');
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

              {corrSystems.length > 0 && (
                <div className="deck-edit__field">
                  <label className="deck-edit__label">Correspondence System</label>
                  <select
                    value={corrSystemId ?? ''}
                    onChange={e => setCorrSystemId(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">None</option>
                    {corrSystems.map(sys => (
                      <option key={sys.id} value={sys.id}>{sys.name}</option>
                    ))}
                  </select>
                  <p className="deck-edit__type-hint">
                    Cards in this deck will inherit correspondences from the selected system.
                  </p>
                </div>
              )}

              {deckId != null && (
                <div className="deck-edit__field">
                  <label className="deck-edit__label">Correspondence Overrides</label>
                  <DeckCorrespondenceOverrides
                    deckId={deckId}
                    cartomancyType={overridesCartomancyType}
                    namingStyle={
                      corrSystems.find(s => s.id === corrSystemId)?.naming_style ?? null
                    }
                  />
                </div>
              )}
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
                        setOriginalSuitNames({});
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
                        setOriginalCourtNames({});
                      }}
                    >
                      Set Custom Court Names
                    </button>
                  </div>
                )}
              </div>
            )}

            <div className="deck-edit__section">
              <h3 className="deck-edit__section-title">Tags</h3>
              {allDeckTags.length > 0 ? (
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
              ) : (
                <p className="deck-edit__hint">
                  No deck tags yet — add one below.
                </p>
              )}
              <AddDeckTagInline
                onCreated={id => {
                  // Auto-select the freshly-created tag so the user
                  // doesn't have to tick it themselves.
                  setSelectedTagIds(prev =>
                    prev.includes(id) ? prev : [...prev, id],
                  );
                }}
              />
            </div>

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

            {variantGroups.length > 0 && (
              <div className="deck-edit__section">
                <h3 className="deck-edit__section-title">Card Variants</h3>
                <p className="deck-edit__section-hint">
                  Cards sharing a name appear as numbered variants in the
                  reading editor. Reorder here to control which is "variant
                  1", "variant 2", etc. Only the variant order changes —
                  each card's deck sort position (card_order) stays put.
                </p>
                <div className="deck-edit__variant-groups">
                  {variantGroups.map(group => (
                    <div key={group.order} className="deck-edit__variant-group">
                      <h4 className="deck-edit__variant-group-name">{group.label}</h4>
                      <ul className="deck-edit__variant-list">
                        {group.cards.map((card, idx) => (
                          <li key={card.id} className="deck-edit__variant-row">
                            <span className="deck-edit__variant-index">
                              variant {idx + 1}
                            </span>
                            {card.image_path ? (
                              <img
                                className="deck-edit__variant-thumb"
                                src={cardThumbnailUrl(card.id)}
                                alt={card.name}
                              />
                            ) : (
                              <div className="deck-edit__variant-thumb deck-edit__variant-thumb--empty">
                                —
                              </div>
                            )}
                            <span className="deck-edit__variant-name">
                              {card.name}
                            </span>
                            <span className="deck-edit__variant-order">
                              co {card.card_order}
                              {card.variant_order != null && (
                                <> · vo {card.variant_order}</>
                              )}
                            </span>
                            <div className="deck-edit__variant-buttons">
                              <button
                                type="button"
                                className="deck-edit__variant-btn"
                                disabled={idx === 0 || variantBusy}
                                onClick={() => moveVariant(group.cards, idx, -1)}
                                title="Move up"
                                aria-label={`Move ${card.name} variant ${idx + 1} up`}
                              >
                                ↑
                              </button>
                              <button
                                type="button"
                                className="deck-edit__variant-btn"
                                disabled={idx === group.cards.length - 1 || variantBusy}
                                onClick={() => moveVariant(group.cards, idx, 1)}
                                title="Move down"
                                aria-label={`Move ${card.name} variant ${idx + 1} down`}
                              >
                                ↓
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {confirmingDelete ? (
            <div className="deck-edit__delete-confirm">
              <p className="deck-edit__delete-warning">
                Are you sure you want to delete <strong>{name || 'this deck'}</strong>?
              </p>
              <p className="deck-edit__delete-warning-detail">
                This will permanently delete the deck, all its cards, custom fields, and tags.
                This action cannot be undone. Type the deck's name to confirm.
              </p>
              <input
                type="text"
                className="deck-edit__delete-confirm-input"
                placeholder={name || 'Deck name'}
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                autoFocus
              />
              <div className="deck-edit__delete-confirm-actions">
                <button
                  onClick={() => {
                    setConfirmingDelete(false);
                    setDeleteConfirmText('');
                  }}
                  disabled={deleting}
                >
                  Cancel
                </button>
                <button
                  className="deck-edit__delete-btn"
                  onClick={handleDelete}
                  disabled={
                    deleting
                    || deleteConfirmText.trim().toLowerCase() !== (name || '').trim().toLowerCase()
                  }
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
                className="deck-edit__export-link"
                onClick={() => setShowAnkiExport(true)}
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
              >
                Export for Anki
              </button>
              <button
                className="deck-edit__export-link"
                onClick={() => setShowScribe(true)}
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                title="Import book content into this deck's card fields with the AI assistant"
              >
                Import with AI
              </button>
              <button
                className="deck-edit__export-link"
                onClick={() => setShowLanguageNames(true)}
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                title="Rename all cards using a language's names from Archetype Languages"
              >
                Card Names…
              </button>
              <button
                className="deck-edit__delete-trigger"
                onClick={() => setConfirmingDelete(true)}
              >
                Delete Deck
              </button>
              <div className="deck-edit__footer-spacer" />
              <ModalCancelButton>Cancel</ModalCancelButton>
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

      {showAnkiExport && deckId && deck && (
        <AnkiExportModal
          deckId={deckId}
          deckName={deck.name}
          onClose={() => setShowAnkiExport(false)}
        />
      )}

      {deck && (
        <ScribeModal
          deck={deck}
          open={showScribe}
          onClose={() => setShowScribe(false)}
        />
      )}

      {deck && showLanguageNames && (
        <ApplyLanguageNamesModal
          deck={deck}
          open={showLanguageNames}
          onClose={() => setShowLanguageNames(false)}
        />
      )}
    </Modal>
  );
}

// =================================================================
// AddDeckTagInline — lightweight form for adding a new deck tag
// from inside the deck editor, so users don't have to leave and
// visit Settings → Tags. Calls back with the new tag id so the
// parent can auto-select it in the checkbox list.
// =================================================================

const DEFAULT_TAG_COLOR = '#6B5B95';

function AddDeckTagInline({ onCreated }: { onCreated: (tagId: number) => void }) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [color, setColor] = useState(DEFAULT_TAG_COLOR);
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setName('');
    setColor(DEFAULT_TAG_COLOR);
    setOpen(false);
  };

  const handleAdd = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      const { id } = await addDeckTag({ name: trimmed, color });
      // Refetch the deck-tags query so the new tag appears in the
      // parent's checkbox list. Auto-selection is done by
      // onCreated in the parent.
      await queryClient.invalidateQueries({ queryKey: ['deck-tags'] });
      onCreated(id);
      reset();
    } catch (err) {
      console.error('Failed to add deck tag:', err);
      showToast('Could not add tag (name may already exist).');
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="deck-edit__add-tag-btn"
        onClick={() => setOpen(true)}
      >
        + Add tag
      </button>
    );
  }
  return (
    <div className="deck-edit__add-tag">
      <input
        autoFocus
        type="text"
        className="deck-edit__add-tag-name"
        placeholder="Tag name"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter') handleAdd();
          if (e.key === 'Escape') reset();
        }}
      />
      <input
        type="color"
        className="deck-edit__add-tag-color"
        aria-label="Tag color"
        value={color}
        onChange={e => setColor(e.target.value)}
      />
      <button type="button" onClick={handleAdd} disabled={!name.trim() || saving}>
        {saving ? 'Adding…' : 'Add'}
      </button>
      <button type="button" onClick={reset} disabled={saving}>
        Cancel
      </button>
    </div>
  );
}
