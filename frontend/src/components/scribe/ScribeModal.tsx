/**
 * The Scribe — imports book/photo content into reference data with an
 * AI assistant, while keeping the user in charge of what gets written.
 *
 * Flow (all inside one modal):
 *   1. Setup — pick cartomancy type, which source fields to fill,
 *      optionally a deck + card custom fields, and add source material
 *      (EPUB/PDF/MOBI/text extracted server-side; photos read locally).
 *   2. Chat + review — the model extracts per-card proposals; they
 *      render in a review table beside the chat. The user refines by
 *      chatting ("split the keywords into their own field", "you
 *      garbled the Queen of Cups") and the model re-emits proposals.
 *   3. Apply — checked rows are written in one batch: source fields
 *      go to archetype notes, card fields to the deck's cards.
 *
 * The model returns proposals as a fenced ```json block in each
 * message; the block is parsed out and never shown raw in the chat.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Modal, { ModalCancelButton } from '../common/Modal';
import SearchCombobox from '../common/SearchCombobox';
import { useToast } from '../../context/ToastContext';
import { getSourceFields, getSourceEntries } from '../../api/referenceSources';
import { getArchetypes, type Archetype } from '../../api/correspondences';
import { getDecks, getDeckCustomFields, getDeckFieldCoverage, type DeckFieldCoverage } from '../../api/decks';
import { getCards } from '../../api/cards';
import { applyScribeWrites, type ScribeWrite } from '../../api/scribe';
import {
  ALL_ENTITY_KINDS,
  ENTITY_KIND_LABELS,
  TYPED_ENTITY_KINDS,
  entityTextToHtml,
  resolveEntityName,
  useEntityRosters,
} from './entityRosters';
import type { EntityKind } from '../../api/reference';
import {
  MAX_SOURCE_CHARS,
  ScribeMaterialsField,
  buildUnits,
  readScribeFiles,
  splitUnit,
  type ExtractionUnit,
  type Material,
  SCRIBE_CHAT_PLACEHOLDER,
  SCRIBE_CHAT_BUSY_PLACEHOLDER,
} from './scribeShared';
import ChatPanel, { type ChatDisplayMessage } from '../common/ChatPanel';
import { getReversedCombinationTypes } from '../../api/combinations';
import { useActivePrompt, renderScribePrompt } from '../../utils/assistantPrompts';
import { llmChat, getLlmConfig, type LlmMessage } from '../../api/llm';
import type { ReferenceSource, SourceField, Card, Deck, DeckCustomField } from '../../types';
import './ScribeModal.css';

/** Launched from a reference source (fills its archetype-note fields,
 *  optionally card fields on a deck too) or directly from a deck
 *  (fills that deck's card custom fields only). Exactly one of
 *  source/deck must be provided. */
interface ScribeModalProps {
  source?: ReferenceSource;
  deck?: Deck;
  open: boolean;
  onClose: () => void;
  /** Combinations-focused launch: extract-combinations starts checked
   *  and no fields are preselected (the user can still add some). */
  combinationsOnly?: boolean;
}

// Material and ExtractionUnit now live in scribeShared (used by both
// Scribe modes).

// ── One proposal row parsed from the model's JSON ────────────
interface Proposal {
  card: string;                    // the name the model used
  fields: Record<string, string>;  // field label → content
  flags?: string[];
  // resolved locally:
  archetypeId?: number;
  cardId?: number;
  checked: boolean;
}

// ── One combination row parsed from the model's JSON ─────────
interface RawCombo {
  cards?: unknown;
  meaning?: unknown;
  reversed?: unknown;
  flags?: unknown;
}

interface ComboProposal {
  cards: string[];                 // 2-3 names, source order
  meaning: string;
  reversed?: boolean[];
  flags?: string[];
  // resolved locally, parallel to cards (undefined = unmatched):
  archetypeIds: (number | undefined)[];
  checked: boolean;
}

// ── One reference-entry row parsed from the model's JSON ─────
interface RawEntry {
  kind?: unknown;
  entry?: unknown;
  content?: unknown;
  flags?: unknown;
}

interface EntityRow {
  kind: EntityKind;
  entry: string;                   // the name the model used
  content: string;
  flags?: string[];
  /** Resolved roster name ('' = unmatched). */
  resolved: string;
  checked: boolean;
}

// Parts are independent, so several can extract at once — wall-clock
// time divides accordingly. Kept modest to stay under API rate limits.
const CONCURRENT_PARTS = 3;
// Flags the model uses when a card's text was cut off at a boundary —
// these trigger the automatic completion pass after extraction.
const INCOMPLETE_FLAG = /cut\s*off|incomplete|truncat|continu/i;
// Attempts per part before it lands on the Resume list: transient
// failures (empty replies, overloads) usually clear on the second try.
const UNIT_ATTEMPTS = 2;
const RETRY_DELAY_MS = 3_000;

export default function ScribeModal({ source, deck, open, onClose, combinationsOnly }: ScribeModalProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  // Which cartomancy types this import can cover, and what to call it
  const availableTypes = useMemo(
    () => source
      ? source.cartomancy_types
      : (deck?.cartomancy_types || []).map(t => t.name),
    [source, deck],
  );
  const displayName = source?.name ?? deck?.name ?? '';

  // ── Setup state ────────────────────────────────────────────
  const [ctype, setCtype] = useState(availableTypes[0] || 'Tarot');
  const [selectedFieldIds, setSelectedFieldIds] = useState<number[]>([]);
  const [deckId, setDeckId] = useState<number | ''>(deck?.id ?? '');
  // Card fields: definitions ticked from the deck + free-typed extras
  const [selectedCardFields, setSelectedCardFields] = useState<string[]>([]);
  const [cardFieldsText, setCardFieldsText] = useState('');
  // Free-text guidance typed before starting — appended to the system
  // prompt so it steers every extraction part and refinement turn.
  const [customInstructions, setCustomInstructions] = useState('');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [stage, setStage] = useState<'setup' | 'chat'>('setup');

  // ── Chat state ─────────────────────────────────────────────
  const [messages, setMessages] = useState<LlmMessage[]>([]);
  const [displayMessages, setDisplayMessages] = useState<ChatDisplayMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [applying, setApplying] = useState(false);
  // Parts of the book still waiting to be sent (nonempty after a
  // mid-extraction failure — powers the Resume button).
  const [pendingUnits, setPendingUnits] = useState<ExtractionUnit[]>([]);
  const systemPromptRef = useRef('');
  // Source of truth for proposal logic. React state is only its render
  // mirror — EVERY change must go through updateProposals below, so
  // async merges and user checkbox clicks can never diverge (a merge
  // building on a stale copy would visually revert the panel).
  const proposalsRef = useRef<Proposal[]>([]);

  const updateProposals = (fn: (current: Proposal[]) => Proposal[]): Proposal[] => {
    const next = fn(proposalsRef.current);
    proposalsRef.current = next;
    setProposals(next);
    return next;
  };

  // Combination proposals — same ref-as-source-of-truth pattern.
  const [combos, setCombos] = useState<ComboProposal[]>([]);
  const combosRef = useRef<ComboProposal[]>([]);
  const updateCombos = (fn: (current: ComboProposal[]) => ComboProposal[]): ComboProposal[] => {
    const next = fn(combosRef.current);
    combosRef.current = next;
    setCombos(next);
    return next;
  };
  const [extractCombos, setExtractCombos] = useState(false);

  // Reference-entry extraction (merged imports): which entry kinds
  // this source covers, and the rows the model proposes for them.
  const [entityKinds, setEntityKinds] = useState<EntityKind[]>([]);
  const [entityRows, setEntityRows] = useState<EntityRow[]>([]);
  const entityRowsRef = useRef<EntityRow[]>([]);
  const updateEntityRows = (fn: (current: EntityRow[]) => EntityRow[]): EntityRow[] => {
    const next = fn(entityRowsRef.current);
    entityRowsRef.current = next;
    setEntityRows(next);
    return next;
  };

  // Mirrors for async code (same rationale as proposalsRef): user
  // events and worker loops need current values, not render-time ones.
  const busyRef = useRef(false);
  const messagesRef = useRef<LlmMessage[]>([]);
  // Messages typed while the model is working: they steer the parts
  // not yet sent, then get a real reply once the workers go quiet.
  const steeringNotesRef = useRef<string[]>([]);

  const setBusyTracked = (b: boolean) => { busyRef.current = b; setBusy(b); };
  const setMessagesTracked = (m: LlmMessage[]) => { messagesRef.current = m; setMessages(m); };

  const { data: llmConfig } = useQuery({ queryKey: ['llm-config'], queryFn: getLlmConfig, enabled: open });
  const { prompt: scribeTemplate, ready: scribePromptReady } = useActivePrompt('scribe', open);
  const { data: fields = [] } = useQuery<SourceField[]>({
    queryKey: ['source-fields', source?.id, ctype],
    queryFn: () => getSourceFields(source!.id, ctype),
    enabled: open && !!source,
  });
  const { data: archetypes = [] } = useQuery<Archetype[]>({
    queryKey: ['archetypes', ctype],
    queryFn: () => getArchetypes(ctype),
    enabled: open,
  });
  const { data: decks = [] } = useQuery<Deck[]>({
    queryKey: ['decks'],
    queryFn: () => getDecks(),
    enabled: open,
  });
  const { data: deckCards = [] } = useQuery<Card[]>({
    queryKey: ['cards', deckId],
    queryFn: () => getCards(deckId as number),
    enabled: open && deckId !== '',
  });
  const { data: existingEntries = [] } = useQuery({
    queryKey: ['source-entries', source?.id, ctype],
    queryFn: () => getSourceEntries(source!.id, ctype),
    enabled: open && !!source,
  });
  const { data: deckFieldDefs = [] } = useQuery<DeckCustomField[]>({
    queryKey: ['deck-custom-fields', deckId],
    queryFn: () => getDeckCustomFields(deckId as number),
    enabled: open && deckId !== '',
  });
  // Deck-mode coverage: how many cards already have content per
  // field, mirroring the archetype-side "(n of N filled)" hints.
  const { data: deckCoverage } = useQuery<DeckFieldCoverage>({
    queryKey: ['deck-field-coverage', deckId],
    queryFn: () => getDeckFieldCoverage(deckId as number),
    enabled: open && deckId !== '',
  });
  // Whether this type supports reversed-card combinations — steers
  // the prompt's combination instructions.
  const { data: reversedComboTypes = [] } = useQuery<string[]>({
    queryKey: ['combination-reversed-types'],
    queryFn: getReversedCombinationTypes,
    enabled: open,
  });
  // Rosters for the entry kinds this import covers (suit/rank rosters
  // are scoped to this import's cartomancy type).
  const { rosters: entityRosters } = useEntityRosters(
    entityKinds, ctype, open && entityKinds.length > 0);
  const rosterFor = (kind: EntityKind) => entityRosters.get(kind) ?? [];
  const cardFieldFilled = (fieldName: string): number => {
    if (!deckCoverage) return 0;
    const k = fieldName.trim().toLowerCase();
    for (const [name, n] of Object.entries(deckCoverage.fields)) {
      if (name.trim().toLowerCase() === k) return n;
    }
    return 0;
  };
  const cardFieldsWithGaps = deckFieldDefs.filter(f =>
    cardFieldFilled(f.field_name) < (deckCoverage?.card_count ?? 0));

  // Default: all source fields selected (none in a combinations-only
  // launch — the user can still opt fields in).
  useEffect(() => {
    setSelectedFieldIds(combinationsOnly ? [] : fields.map(f => f.id));
  }, [fields, combinationsOnly]);


  // Reset everything when the modal opens fresh
  useEffect(() => {
    if (!open) return;
    setStage('setup');
    setMaterials([]);
    setMessagesTracked([]);
    setDisplayMessages([]);
    updateProposals(() => []);
    setPendingUnits([]);
    steeringNotesRef.current = [];
    setCtype(availableTypes[0] || 'Tarot');
    setDeckId(deck?.id ?? '');
    setSelectedCardFields([]);
    setCardFieldsText('');
    setCustomInstructions('');
    setExtractCombos(!!combinationsOnly);
    setEntityKinds([]);
    updateEntityRows(() => []);
  }, [open, source?.id, deck?.id, availableTypes, combinationsOnly]); // eslint-disable-line react-hooks/exhaustive-deps

  // Deck mode: preselect the deck's existing field definitions.
  // Defined AFTER the reset effect (effects run in order) and keyed
  // on `open`, so opening the modal can't clear the preselection —
  // with cached defs the array identity never changes, so this
  // wouldn't re-fire on its own.
  useEffect(() => {
    if (open && deck) setSelectedCardFields(deckFieldDefs.map(f => f.field_name));
  }, [open, deck, deckFieldDefs]);

  const decksForType = useMemo(
    () => decks.filter(d => (d.cartomancy_types || []).some(t => t.name === ctype)),
    [decks, ctype],
  );

  const cardFieldNames = useMemo(() => {
    const typed = cardFieldsText.split(/[,;\n]/).map(s => s.trim()).filter(Boolean);
    const all = [...selectedCardFields, ...typed];
    // De-dupe case-insensitively, first occurrence wins
    const seen = new Set<string>();
    return all.filter(n => {
      const k = n.toLowerCase();
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }, [selectedCardFields, cardFieldsText]);

  const selectedFields = fields.filter(f => selectedFieldIds.includes(f.id));

  // What kinds of writes this session can actually perform. A row is
  // only truly "matched" if it can reach at least one write target —
  // e.g. in a deck-only import, matching an archetype that has no card
  // in the deck still means nothing can be written.
  const hasArchetypeTargets = !!source && selectedFields.length > 0;
  const hasCardTargets = deckId !== '' && cardFieldNames.length > 0;
  const isWritable = (p: Proposal) =>
    (p.archetypeId != null && hasArchetypeTargets) ||
    (p.cardId != null && hasCardTargets);

  // Existing archetype content, for overwrite badges: "archetypeId:fieldId"
  const existingKeys = useMemo(() => {
    const set = new Set<string>();
    for (const e of existingEntries) set.add(`${e.archetype_id}:${e.field_id}`);
    return set;
  }, [existingEntries]);

  // Per-field coverage: how many of this type's archetypes already
  // have content, straight from the data behind the overwrite badges.
  // Drives the "(12 of 78 filled)" hints and the gaps-only shortcut.
  const fieldCoverage = useMemo(() => {
    const map = new Map<number, number>();
    for (const f of fields) {
      map.set(f.id, new Set(
        existingEntries.filter(e => e.field_id === f.id).map(e => e.archetype_id),
      ).size);
    }
    return map;
  }, [fields, existingEntries]);

  const fieldsWithGaps = fields.filter(f =>
    (fieldCoverage.get(f.id) ?? 0) < archetypes.length);

  // ── File intake (shared with the entity Scribe) ────────────
  const handleAddFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setExtracting(true);
    const added = await readScribeFiles(files, showToast);
    setMaterials(prev => [...prev, ...added]);
    setExtracting(false);
  };

  // ── Start extraction ───────────────────────────────────────
  const targetLabels = [
    ...selectedFields.map(f => f.name),
    ...(deckId !== '' ? cardFieldNames : []),
  ];

  const canStart = materials.length > 0
    && (targetLabels.length > 0 || extractCombos || entityKinds.length > 0)
    && !extracting && scribePromptReady;

  const handleStart = async () => {
    systemPromptRef.current = renderScribePrompt(scribeTemplate, {
      cartomancyType: ctype,
      sourceName: displayName,
      archetypeNames: archetypes.map(a => a.name).join(', '),
      targetFields: targetLabels.length
        ? targetLabels.map(l => `"${l}"`).join(', ')
        : '(none — this import extracts card combinations only; send "proposals": [] in each block)',
    }, customInstructions,
    extractCombos
      ? { reversalsEnabled: reversedComboTypes.includes(ctype) }
      : undefined,
    entityKinds.length > 0
      ? {
          kinds: entityKinds.map(k => ({
            kind: k,
            label: TYPED_ENTITY_KINDS.includes(k)
              ? `${ctype} ${ENTITY_KIND_LABELS[k].toLowerCase()}`
              : ENTITY_KIND_LABELS[k],
            roster: rosterFor(k),
          })),
        }
      : undefined);

    const totalText = materials.reduce((n, m) => n + (m.text?.length || 0), 0);
    if (totalText > MAX_SOURCE_CHARS) {
      showToast(`This source is over ${Math.round(MAX_SOURCE_CHARS / 1_000_000)} million characters — only the first ${Math.round(MAX_SOURCE_CHARS / 1000)}k could be included. Import it as separate smaller files (e.g. split by chapters).`);
    }
    const units = buildUnits(materials);
    if (!units.length) return;

    setMessagesTracked([]);
    updateProposals(() => []);
    updateCombos(() => []);
    updateEntityRows(() => []);
    setDisplayMessages([]);
    setStage('chat');
    await runExtraction(units, []);
  };

  /** Extract every part, several at a time. Each part is its own
   *  independent request (system prompt + that part only), so they can
   *  run concurrently; results merge into the running list as they
   *  land. Afterwards the (part, reply) pairs are stitched into one
   *  conversation in book order so refinement chat has full context.
   *  Failed parts are collected for the Resume button. */
  const runExtraction = async (units: ExtractionUnit[], startHistory: LlmMessage[]) => {
    setBusyTracked(true);
    // Local copy — split-on-overflow appends sub-units while workers
    // are still draining the queue.
    const queue = [...units];
    const results: ({ userMsg: LlmMessage; reply: string } | null | undefined)[] = [];
    // Units whose overflowing reply was replaced by two queued halves —
    // not failures, so they don't go to the Resume list.
    const splitAway = new Set<number>();
    let nextIdx = 0;

    // One request with automatic retry: transient failures (an empty
    // reply, a momentary overload, a rate-limit blip) get a second
    // attempt after a pause before the part is declared failed.
    // Returns the userMsg actually sent — mid-import guidance from the
    // user is attached to parts not yet dispatched, and the stitched
    // history must reflect what the model really saw.
    const requestUnit = async (unit: ExtractionUnit) => {
      for (let attempt = 1; ; attempt++) {
        const notes = steeringNotesRef.current;
        const userMsg: LlmMessage = {
          role: 'user',
          content: notes.length
            ? [...unit.parts, {
                type: 'text' as const,
                text: `Guidance the user sent while this import is running — apply it to this part's extraction:\n- ${notes.join('\n- ')}`,
              }]
            : unit.parts,
        };
        try {
          const result = await llmChat({
            feature: 'scribe',
            messages: [...startHistory, userMsg],
            system: systemPromptRef.current,
            max_tokens: 64000,
            // One-shot: this part's content is never re-sent, so don't
            // pay the cache-write surcharge on it. (The stitched
            // conversation used for follow-ups and refinement IS
            // cached — that's where re-reading happens.)
            cache: false,
          });
          return { ...result, userMsg };
        } catch (err: unknown) {
          if (attempt >= UNIT_ATTEMPTS) throw err;
          const e = err as { response?: { data?: { error?: string } } };
          setDisplayMessages(prev => [...prev, {
            role: 'user',
            text: `[${unit.label}] ${e.response?.data?.error || 'The request failed.'} Retrying…`,
          }]);
          await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
        }
      }
    };

    const worker = async () => {
      while (nextIdx < queue.length) {
        const i = nextIdx++;
        const unit = queue[i];
        setDisplayMessages(prev => [...prev, { role: 'user', text: `Reading ${unit.label}…` }]);
        try {
          const { text: reply, truncated, userMsg } = await requestUnit(unit);
          const { visible, parsed, parsedCombos, parsedEntries } = splitReply(reply);
          if (parsedCombos) {
            updateCombos(current => mergeCombos(current, parsedCombos, archetypes));
          }
          if (parsedEntries) {
            updateEntityRows(current =>
              mergeEntities(current, parsedEntries, entityKinds, rosterFor));
          }
          if (parsed || parsedCombos || parsedEntries) {
            const merged = parsed
              ? updateProposals(current =>
                mergeProposals(current, parsed, archetypes, deckCards, true))
              : proposalsRef.current;
            const bits = [];
            if (parsed) bits.push(`${parsed.length} card${parsed.length === 1 ? '' : 's'} (${merged.length} total): ${summarizeCards(parsed)}`);
            if (parsedCombos) bits.push(`${parsedCombos.length} combination${parsedCombos.length === 1 ? '' : 's'} (${combosRef.current.length} total)`);
            if (parsedEntries) bits.push(`${parsedEntries.length} reference entr${parsedEntries.length === 1 ? 'y' : 'ies'} (${entityRowsRef.current.length} total)`);
            const summary = bits.join('; ');
            setDisplayMessages(prev => [...prev, {
              role: 'assistant',
              text: `[${unit.label}] ${trimProse(visible) ? `${trimProse(visible)}\n— ${summary}` : summary}`,
            }]);
          } else {
            setDisplayMessages(prev => [...prev, {
              role: 'assistant',
              text: `[${unit.label}] ${trimProse(visible || reply)}`,
            }]);
          }
          if (truncated) {
            const subUnits = splitUnit(unit);
            if (subUnits) {
              splitAway.add(i);
              queue.push(...subUnits);
              setDisplayMessages(prev => [...prev, {
                role: 'user',
                text: `[${unit.label}] The reply hit the length limit — re-reading this part in ${subUnits.length} smaller pieces (cards already extracted are kept; complete versions win).`,
              }]);
              continue; // don't stitch the overflowed round into history
            }
            setDisplayMessages(prev => [...prev, {
              role: 'error',
              text: `[${unit.label}] This reply was cut off at the length limit and the part can't be split further — some of its cards may be missing. Ask the model to re-check this part afterwards.`,
            }]);
          }
          results[i] = { userMsg, reply };
        } catch (err: unknown) {
          const e = err as { response?: { data?: { error?: string } } };
          setDisplayMessages(prev => [...prev, {
            role: 'error',
            text: `[${unit.label}] ${e.response?.data?.error || 'The model request failed.'} (retried ${UNIT_ATTEMPTS - 1}×)`,
          }]);
        }
      }
    };

    await Promise.all(
      Array.from({ length: Math.min(CONCURRENT_PARTS, queue.length) }, worker),
    );

    // Stitch successful rounds into one conversation, in book order,
    // so refinement questions can reference any part of the source.
    let history = startHistory;
    const failedUnits: ExtractionUnit[] = [];
    queue.forEach((unit, i) => {
      if (splitAway.has(i)) return;
      const r = results[i];
      if (r) history = [...history, r.userMsg, { role: 'assistant', content: r.reply }];
      else failedUnits.push(unit);
    });
    setMessagesTracked(history);
    setPendingUnits(failedUnits);
    if (failedUnits.length) {
      setDisplayMessages(prev => [...prev, {
        role: 'error',
        text: `${failedUnits.length} part${failedUnits.length === 1 ? '' : 's'} failed — cards already extracted are safe. "Resume extraction" retries just the failed parts.`,
      }]);
    }
    setBusyTracked(false);
    // With every part in, run the automatic follow-ups: complete
    // boundary-straddling cards, then audit field coverage. Both ride
    // the stitched conversation — the only place all parts are visible
    // at once. (After a Resume run finishes the missing parts, these
    // fire then instead.)
    if (!failedUnits.length) {
      const afterRepair = await completeFlaggedCards(history);
      await auditFieldCoverage(afterRepair ?? history);
      await auditMissingCards(messagesRef.current);
      // Notes typed during the run steered the remaining parts as they
      // went out; now that the full material is stitched, give them a
      // proper full-context turn. (With failed parts pending, notes
      // stay queued so they also steer the Resume run.)
      await flushQueuedNotes();
    }
  };

  /** Deliver mid-run messages as a real conversation turn once the
   *  workers are quiet. Loops because the user may keep typing while
   *  the flush turn itself is generating. */
  const flushQueuedNotes = async () => {
    while (steeringNotesRef.current.length && !busyRef.current) {
      const notes = steeringNotesRef.current;
      steeringNotesRef.current = [];
      const combined = notes.length === 1
        ? notes[0]
        : `While the import ran, I sent these notes:\n- ${notes.join('\n- ')}`;
      setDisplayMessages(prev => [...prev, {
        role: 'user',
        text: `Following up on the note${notes.length === 1 ? '' : 's'} sent during extraction…`,
      }]);
      await callModel([...messagesRef.current, {
        role: 'user',
        content:
          `${combined}\n\n(Sent while extraction was still running — later parts already saw it as guidance. ` +
          'Now that all material is above, apply anything still needed to the proposals — re-send only ' +
          'changed cards — and answer any questions.)',
      }], { thinking: true });
    }
  };

  /** One-shot follow-up: re-request full content for any card the
   *  model flagged as cut off at a part boundary. Returns the extended
   *  history, or null if there was nothing to repair. */
  const completeFlaggedCards = async (history: LlmMessage[]): Promise<LlmMessage[] | null> => {
    const flagged = proposalsRef.current.filter(p =>
      p.flags?.some(f => INCOMPLETE_FLAG.test(f)));
    if (!flagged.length) return null;
    const names = flagged.map(p => p.card).join(', ');
    setDisplayMessages(prev => [...prev, {
      role: 'user',
      text: `Auto-completing ${flagged.length} card${flagged.length === 1 ? '' : 's'} flagged as cut off: ${names}`,
    }]);
    return callModel([...history, {
      role: 'user',
      content:
        `These cards were flagged as incomplete or cut off at a part boundary: ${names}. ` +
        'All source parts are above in this conversation, and neighbouring parts overlap, ' +
        'so the complete text for each card should be visible across them. Re-send each of ' +
        'these cards with its complete field content assembled from all relevant parts. ' +
        'For every card you resolve, include "flags": [] (or a flag stating what is genuinely ' +
        'missing from the source, if the text truly ends mid-sentence in the book itself).',
    }], { thinking: true });
  };

  /** One-shot follow-up: when some target fields were filled for far
   *  fewer cards than others, ask the model to re-scan for them — the
   *  usual cause is the model economizing on dense parts, or a book
   *  keeping a field's content in its own section (all keywords in an
   *  appendix, say) that got extracted under the wrong name. */
  const auditFieldCoverage = async (history: LlmMessage[]) => {
    const props = proposalsRef.current;
    if (props.length < 5 || targetLabels.length < 2) return;
    const counts = targetLabels.map(label => ({
      label,
      count: props.filter(p =>
        Object.entries(p.fields).some(([k, v]) =>
          k.toLowerCase() === label.toLowerCase() && v?.trim())).length,
    }));
    const maxCount = Math.max(...counts.map(c => c.count));
    if (maxCount === 0) return;
    const sparse = counts.filter(c => c.count < maxCount * 0.5);
    if (!sparse.length) return;
    const description = sparse
      .map(c => `"${c.label}" (${c.count} of ${props.length} cards)`)
      .join(', ');
    setDisplayMessages(prev => [...prev, {
      role: 'user',
      text: `Auto-check: some target fields were rarely filled — ${description}. Asking the model to re-scan the source…`,
    }]);
    await callModel([...history, {
      role: 'user',
      content:
        `Field-coverage check: these target fields were filled for few or no cards: ${description}. ` +
        'Re-scan the source parts above for content belonging to these fields — it may sit in its own ' +
        'section (an appendix of keywords, a separate reversed-meanings chapter) or have been extracted ' +
        'under a different field name. If the source has the content, re-send the affected cards with ' +
        'those fields added, using the exact target field names (only changed cards, as usual). ' +
        'If the source genuinely does not provide this information, say so briefly — never invent content.',
    }], { thinking: true });
  };

  /** One-shot follow-up: cards from the app's archetype list that got
   *  NO proposal at all. Books hide cards under variant names, shared
   *  paragraphs, or out-of-order sections — a by-name checklist makes
   *  the model account for each one instead of stopping at what it
   *  noticed on the first pass. */
  const auditMissingCards = async (history: LlmMessage[]) => {
    const props = proposalsRef.current;
    if (props.length < 3 || archetypes.length === 0) return;
    const matchedIds = new Set(props.map(p => p.archetypeId).filter(Boolean));
    const namedLower = new Set(props.map(p => p.card.toLowerCase()));
    const missing = archetypes.filter(a =>
      !matchedIds.has(a.id) && !namedLower.has(a.name.toLowerCase()));
    if (!missing.length) return;
    const names = missing.map(a => a.name);
    if (names.length > archetypes.length / 2) {
      // Probably an intentionally partial source (one chapter, a
      // keywords sheet) — report instead of interrogating.
      setDisplayMessages(prev => [...prev, {
        role: 'user',
        text: `Coverage: ${props.length} of ${archetypes.length} ${ctype} cards have content; the rest don't appear to be in this source.`,
      }]);
      return;
    }
    setDisplayMessages(prev => [...prev, {
      role: 'user',
      text: `Auto-check: ${names.length} card${names.length === 1 ? ' has' : 's have'} no content yet — ${names.join(', ')}. Asking the model to re-scan…`,
    }]);
    await callModel([...history, {
      role: 'user',
      content:
        `Coverage check against the app's full ${ctype} card list — these cards have NO extracted content yet: ${names.join(', ')}. ` +
        'Re-scan ALL the source parts above specifically for them. They may appear under variant or translated names ' +
        '(apply the name-matching guide), share a paragraph or table row with other cards, or sit outside the main ' +
        'card-by-card section. Extract every one of them the source actually covers, mapped to the app\'s archetype ' +
        'names. For any of these cards the source genuinely does not cover, list it in one line of prose — never invent content.',
    }], { thinking: true });
  };

  // ── Chat plumbing ──────────────────────────────────────────

  /** One model round-trip: send history, show the reply, merge any
   *  proposals. Returns the new history, or null on failure.
   *  thinking=true turns on extended reasoning — used for the audit
   *  and refinement turns, which cross-reference the whole book. */
  const callModel = async (
    history: LlmMessage[],
    opts?: { thinking?: boolean },
  ): Promise<LlmMessage[] | null> => {
    setBusyTracked(true);
    try {
      const { text: reply, truncated } = await llmChat({
        feature: 'scribe',
        messages: history,
        system: systemPromptRef.current,
        max_tokens: 64000,
        thinking: opts?.thinking,
      });
      const { visible, parsed, parsedCombos, parsedEntries } = splitReply(reply);
      if (parsedEntries) {
        updateEntityRows(current =>
          mergeEntities(current, parsedEntries, entityKinds, rosterFor));
      }
      const newHistory: LlmMessage[] = [...history, { role: 'assistant', content: reply }];
      setMessagesTracked(newHistory);
      if (parsedCombos) {
        updateCombos(current => mergeCombos(current, parsedCombos, archetypes));
      }
      if (parsed || parsedCombos || parsedEntries) {
        const merged = parsed
          ? updateProposals(current =>
            mergeProposals(current, parsed, archetypes, deckCards))
          : proposalsRef.current;
        const bits = [];
        if (parsed) bits.push(`Updated ${parsed.length} card${parsed.length === 1 ? '' : 's'} (${merged.length} total): ${summarizeCards(parsed)}`);
        if (parsedCombos) bits.push(`${parsedCombos.length} combination${parsedCombos.length === 1 ? '' : 's'} (${combosRef.current.length} total)`);
        if (parsedEntries) bits.push(`${parsedEntries.length} reference entr${parsedEntries.length === 1 ? 'y' : 'ies'} (${entityRowsRef.current.length} total)`);
        const summary = bits.join('; ');
        setDisplayMessages(prev => [...prev, {
          role: 'assistant',
          text: visible ? `${visible}\n— ${summary}` : summary,
        }]);
      } else {
        setDisplayMessages(prev => [...prev, { role: 'assistant', text: visible || reply }]);
      }
      if (truncated) {
        setDisplayMessages(prev => [...prev, {
          role: 'error',
          text: 'This reply was cut off at the length limit, so some cards from this part may be missing. Once extraction finishes, ask the model to re-check this part.',
        }]);
      }
      return newHistory;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } };
      setDisplayMessages(prev => [...prev, {
        role: 'error',
        text: e.response?.data?.error || 'The model request failed. You can try sending again.',
      }]);
      return null;
    } finally {
      setBusyTracked(false);
    }
  };

  const handleSend = async (text: string) => {
    if (busyRef.current) {
      // Model's mid-work: queue it. It steers parts not yet sent and
      // gets a full-context reply when the current work finishes.
      steeringNotesRef.current = [...steeringNotesRef.current, text];
      setDisplayMessages(prev => [...prev,
        { role: 'user', text },
        { role: 'note', text: 'Noted — this will guide the remaining parts and get a reply when the current work finishes.' },
      ]);
      return;
    }
    setDisplayMessages(prev => [...prev, { role: 'user', text }]);
    await callModel([...messagesRef.current, { role: 'user', content: text }], { thinking: true });
    // Anything typed while that reply generated gets its turn now.
    await flushQueuedNotes();
  };

  // ── Apply ──────────────────────────────────────────────────
  // Only writable rows count — a checked row with no reachable target
  // must not inflate the Apply button's promise.
  // Review list in canonical card order (the archetype list's order,
  // deck order in deck-only imports), so gaps in a book's coverage
  // are visible at a glance; unmatched names keep arrival order at
  // the end. Sorting is render-only — merge logic is name-keyed.
  const archOrder = useMemo(
    () => new Map(archetypes.map((a, i) => [a.id, i])), [archetypes]);
  const deckOrder = useMemo(
    () => new Map(deckCards.map((c, i) => [c.id, i])), [deckCards]);
  const sortedProposals = useMemo(() => {
    const key = (p: Proposal, i: number) => {
      if (p.archetypeId != null && archOrder.has(p.archetypeId)) {
        return archOrder.get(p.archetypeId)!;
      }
      if (p.cardId != null && deckOrder.has(p.cardId)) {
        return deckOrder.get(p.cardId)!;
      }
      return 1_000_000 + i;
    };
    return proposals
      .map((p, i) => ({ p, k: key(p, i) }))
      .sort((a, b) => a.k - b.k)
      .map(x => x.p);
  }, [proposals, archOrder, deckOrder]);
  const sortedCombos = useMemo(() => {
    const pos = (id: number | undefined) =>
      id != null && archOrder.has(id) ? archOrder.get(id)! : 1_000_000;
    return [...combos].sort((a, b) =>
      pos(a.archetypeIds[0]) - pos(b.archetypeIds[0])
      || pos(a.archetypeIds[1]) - pos(b.archetypeIds[1])
      || pos(a.archetypeIds[2]) - pos(b.archetypeIds[2]));
  }, [combos, archOrder]);

  const checkedProposals = proposals.filter(p => p.checked && isWritable(p));
  const checkedEntities = entityRows.filter(r => r.checked && r.resolved !== '');
  const checkedCombos = combos.filter(c =>
    c.checked && c.archetypeIds.every(id => id != null));
  const fieldByName = useMemo(() => {
    const map = new Map<string, SourceField>();
    for (const f of selectedFields) map.set(f.name.toLowerCase(), f);
    return map;
  }, [selectedFields]);

  const handleApply = async () => {
    const writes: ScribeWrite[] = [];
    // Parallel to `writes`: a human label per write, so per-row apply
    // failures can be reported by name instead of a bare count.
    const writeLabels: string[] = [];
    // Everything skipped is surfaced with its actual reason — never silent.
    const unknownLabels = new Set<string>();
    const cardsWithoutDeckCard = new Set<string>();
    for (const p of checkedProposals) {
      for (const [label, content] of Object.entries(p.fields)) {
        if (!content?.trim()) continue;
        const sourceField = fieldByName.get(label.toLowerCase());
        const isCardField = cardFieldNames.some(n => n.toLowerCase() === label.toLowerCase());
        if (sourceField && p.archetypeId) {
          writes.push({
            target: 'archetype',
            archetype_id: p.archetypeId,
            field_id: sourceField.id,
            content,
          });
          writeLabels.push(`${p.card} → ${label}`);
        } else if (isCardField && p.cardId) {
          writes.push({
            target: 'card',
            card_id: p.cardId,
            field_name: label,
            content,
          });
          writeLabels.push(`${p.card} → ${label} (card field)`);
        } else if (isCardField && !p.cardId) {
          cardsWithoutDeckCard.add(p.card);
        } else if (!sourceField) {
          unknownLabels.add(label);
        }
      }
    }
    if (unknownLabels.size) {
      showToast(
        `Heads up: ${[...unknownLabels].map(l => `"${l}"`).join(', ')} ` +
        `${unknownLabels.size === 1 ? 'is' : 'are'} not among your target fields and won't be written. ` +
        'Ask the model to move that content into a target field, or add it as a field first.',
      );
    }
    if (cardsWithoutDeckCard.size) {
      showToast(
        `${[...cardsWithoutDeckCard].join(', ')}: no matching card in the deck, so their ` +
        'card fields can\'t be written. Use "Assign to card…" on those rows first.',
      );
    }
    for (const c of checkedCombos) {
      writes.push({
        target: 'combination',
        cartomancy_type: ctype,
        archetype_ids: c.archetypeIds as number[],
        reversed: c.reversed,
        content: c.meaning,
        source_id: source?.id ?? null,
      });
      writeLabels.push(`${c.cards
        .map((n, j) => `${n}${c.reversed?.[j] ? ' (rev)' : ''}`)
        .join(' + ')} (combination)`);
    }
    for (const r of checkedEntities) {
      writes.push({
        target: 'entity_note',
        kind: r.kind,
        key: TYPED_ENTITY_KINDS.includes(r.kind)
          ? `${ctype}::${r.resolved}`
          : r.resolved,
        source_id: source!.id,
        content: entityTextToHtml(r.content),
      });
      writeLabels.push(`${r.resolved} (${r.kind} entry)`);
    }
    if (!writes.length) {
      showToast('Nothing to apply — the checked cards have no writable fields.');
      return;
    }
    setApplying(true);
    try {
      const result = await applyScribeWrites(writes);
      queryClient.invalidateQueries({ queryKey: ['archetype-source-entries'] });
      queryClient.invalidateQueries({ queryKey: ['source-entries'] });
      queryClient.invalidateQueries({ queryKey: ['cards'] });
      queryClient.invalidateQueries({ queryKey: ['deck-custom-fields'] });
      if (checkedCombos.length) {
        queryClient.invalidateQueries({ queryKey: ['combination-meanings'] });
        queryClient.invalidateQueries({ queryKey: ['populated-combinations'] });
      }
      if (checkedEntities.length) {
        queryClient.invalidateQueries({
          predicate: q => q.queryKey[0] === 'entity-notes',
        });
      }
      const dupNote = result.skipped
        ? ` (${result.skipped} duplicate combination${result.skipped === 1 ? '' : 's'} skipped)`
        : '';
      if (result.errors.length) {
        // Name every failure with its server-reported reason, in the
        // chat log where it stays visible and copyable.
        const details = result.errors.map(e =>
          `• ${writeLabels[e.index] ?? `write #${e.index + 1}`} — ${e.error}`);
        setDisplayMessages(d => [...d, {
          role: 'note',
          text: `${result.errors.length} write${result.errors.length === 1 ? '' : 's'} failed:\n${details.join('\n')}`,
        }]);
        showToast(`Applied ${result.applied} of ${writes.length} — ${result.errors.length} failed (details in the chat panel).${dupNote}`);
      } else {
        showToast(`Imported ${result.applied} entries from ${displayName}.${dupNote}`, 'success');
        onClose();
      }
    } catch {
      showToast('Failed to apply the import.');
    } finally {
      setApplying(false);
    }
  };

  const dirty = stage === 'chat'
    && (proposals.length > 0 || combos.length > 0 || entityRows.length > 0);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Import with AI — ${displayName}`}
      width={stage === 'chat' ? 1100 : 640}
      isDirty={dirty}
      confirmMessage="Close the import? Unapplied proposals will be lost."
    >
      {llmConfig && !llmConfig.model && (
        <p className="scribe__warning">
          No AI model is configured yet — set one up in Settings → AI Assistant first.
        </p>
      )}

      {stage === 'setup' && (
        <div className="scribe__setup">
          {availableTypes.length > 1 && (
            <div className="scribe__field">
              <label>Cartomancy type</label>
              <select value={ctype} onChange={e => setCtype(e.target.value)}>
                {availableTypes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          )}

          {source && (
          <div className="scribe__field">
            <label>Fill these {source.name} fields ({ctype})</label>
            {fields.length === 0 && (
              <p className="scribe__hint">
                This source has no {ctype} fields yet — add them in the source's
                field list first, or target only deck card fields below.
              </p>
            )}
            {fields.map(f => {
              const filled = fieldCoverage.get(f.id) ?? 0;
              const total = archetypes.length;
              return (
                <label key={f.id} className="scribe__check">
                  <input
                    type="checkbox"
                    checked={selectedFieldIds.includes(f.id)}
                    onChange={e => setSelectedFieldIds(prev =>
                      e.target.checked ? [...prev, f.id] : prev.filter(id => id !== f.id))}
                  />
                  {f.name}
                  <span className={`scribe__coverage ${filled >= total && total > 0 ? 'scribe__coverage--full' : ''}`}>
                    {total > 0
                      ? filled === 0 ? '(empty)' : `(${filled} of ${total} filled)`
                      : ''}
                  </span>
                </label>
              );
            })}
            {fields.length > 1 && (
              <div className="scribe__select-shortcuts">
                <button onClick={() => setSelectedFieldIds(fields.map(f => f.id))}>
                  Check all
                </button>
                <button onClick={() => setSelectedFieldIds([])}>
                  Uncheck all
                </button>
                {fieldsWithGaps.length > 0 && (
                  <button onClick={() => setSelectedFieldIds(fieldsWithGaps.map(f => f.id))}>
                    Only fields with gaps ({fieldsWithGaps.length})
                  </button>
                )}
              </div>
            )}
          </div>
          )}

          <div className="scribe__field">
            {deck ? (
              <label>Fill card fields on {deck.name} ({ctype})</label>
            ) : (
              <>
                <label>Also fill card fields on a deck (optional)</label>
                <SearchCombobox
                  options={decksForType.map(d => ({ id: d.id, label: d.name }))}
                  value={deckId === '' ? undefined : deckId}
                  onSelect={opt => setDeckId(opt ? opt.id : '')}
                  placeholder="No deck — reference fields only"
                />
              </>
            )}
            {deckId !== '' && (
              <>
                {deckFieldDefs.map(f => {
                  const filled = cardFieldFilled(f.field_name);
                  const total = deckCoverage?.card_count ?? 0;
                  return (
                    <label key={f.id} className="scribe__check">
                      <input
                        type="checkbox"
                        checked={selectedCardFields.some(n => n.toLowerCase() === f.field_name.toLowerCase())}
                        onChange={e => setSelectedCardFields(prev =>
                          e.target.checked
                            ? [...prev, f.field_name]
                            : prev.filter(n => n.toLowerCase() !== f.field_name.toLowerCase()))}
                      />
                      {f.field_name}
                      <span className={`scribe__coverage ${filled >= total && total > 0 ? 'scribe__coverage--full' : ''}`}>
                        {total > 0
                          ? filled === 0 ? '(empty)' : `(${filled} of ${total} filled)`
                          : ''}
                      </span>
                    </label>
                  );
                })}
                {deckFieldDefs.length > 1 && (
                  <div className="scribe__select-shortcuts">
                    <button onClick={() => setSelectedCardFields(deckFieldDefs.map(f => f.field_name))}>
                      Check all
                    </button>
                    <button onClick={() => setSelectedCardFields([])}>
                      Uncheck all
                    </button>
                    {cardFieldsWithGaps.length > 0 && (
                      <button onClick={() => setSelectedCardFields(cardFieldsWithGaps.map(f => f.field_name))}>
                        Only fields with gaps ({cardFieldsWithGaps.length})
                      </button>
                    )}
                  </div>
                )}
                <input
                  type="text"
                  placeholder={deckFieldDefs.length
                    ? 'Additional new field names, comma-separated'
                    : 'Card field names, comma-separated (e.g. Keywords, Book Meaning)'}
                  value={cardFieldsText}
                  onChange={e => setCardFieldsText(e.target.value)}
                />
                <p className="scribe__hint">
                  These become custom fields on each card of the deck,
                  matched to cards through their archetypes.
                  {deck && !cardFieldNames.length && ' Pick at least one field (or type a new one) to import into.'}
                </p>
              </>
            )}
          </div>

          <ScribeMaterialsField
            materials={materials}
            onRemove={(id) => setMaterials(prev => prev.filter(x => x.id !== id))}
            onAddFiles={handleAddFiles}
            extracting={extracting}
          />

          <div className="scribe__field">
            <label className="scribe__combo-toggle">
              <input
                type="checkbox"
                checked={extractCombos}
                onChange={e => setExtractCombos(e.target.checked)}
                disabled={extracting}
              />
              <span>
                Extract card combinations
                <em className="scribe__hint-inline">
                  {' '}— pair/triad meanings ("Rider + Clover: …") go to the
                  Combinations reference{source ? `, attributed to ${source.name}` : ''}
                </em>
              </span>
            </label>
          </div>

          {source && (
            <div className="scribe__field">
              <label>Also extract reference entries (optional)</label>
              <p className="scribe__hint">
                For sources with chapters about the suits, numbers,
                sephiroth, signs… — check what this source covers.
                Texts land in the Reference sections, attributed
                to {source.name}.
              </p>
              <div className="scribe__entity-kinds">
                {ALL_ENTITY_KINDS.map(k => (
                  <label key={k} className="scribe__check">
                    <input
                      type="checkbox"
                      checked={entityKinds.includes(k)}
                      onChange={e => setEntityKinds(prev =>
                        e.target.checked ? [...prev, k] : prev.filter(x => x !== k))}
                      disabled={extracting}
                    />
                    {ENTITY_KIND_LABELS[k]}
                    {TYPED_ENTITY_KINDS.includes(k) && (
                      <span className="scribe__coverage">({ctype})</span>
                    )}
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="scribe__field">
            <label>Instructions for this import (optional)</label>
            <textarea
              className="scribe__instructions"
              value={customInstructions}
              onChange={e => setCustomInstructions(e.target.value)}
              rows={3}
              placeholder={'Anything the Scribe should know before it starts — e.g. "This is a Thoth book, so match the Knight to the King archetype" or "Skip the spreads chapter."'}
            />
          </div>

          <div className="scribe__actions">
            <button className="primary" onClick={handleStart} disabled={!canStart || !llmConfig?.model}>
              Start extraction
            </button>
            <ModalCancelButton>Cancel</ModalCancelButton>
          </div>
        </div>
      )}

      {stage === 'chat' && (
        <div className="scribe__workspace">
          <ChatPanel
            messages={displayMessages}
            busy={busy}
            onSend={handleSend}
            allowSendWhileBusy
            placeholder={SCRIBE_CHAT_PLACEHOLDER}
            busyPlaceholder={SCRIBE_CHAT_BUSY_PLACEHOLDER}
          >
            {pendingUnits.length > 0 && !busy && (
              <button
                className="scribe__resume"
                onClick={() => runExtraction(pendingUnits, messages)}
              >
                Resume extraction ({pendingUnits.length} part{pendingUnits.length === 1 ? '' : 's'} left)
              </button>
            )}
          </ChatPanel>

          <div className="scribe__review">
            <div className="scribe__review-head">
              <strong>{proposals.length} card{proposals.length === 1 ? '' : 's'} proposed</strong>
              {proposals.length > 0 && (
                <span className="scribe__review-bulk">
                  <button onClick={() => updateProposals(p => p.map(x => ({ ...x, checked: true })))}>All</button>
                  <button onClick={() => updateProposals(p => p.map(x => ({ ...x, checked: false })))}>None</button>
                </span>
              )}
            </div>
            <div className="scribe__review-list">
              {proposals.length === 0 && combos.length === 0
                && entityRows.length === 0 && !busy && (
                <p className="scribe__hint">
                  Proposals will appear here once the model has read the material.
                </p>
              )}
              {sortedProposals.map((p) => (
                <ProposalRow
                  key={p.card.toLowerCase()}
                  proposal={p}
                  selectedFields={selectedFields}
                  cardFieldNames={deckId !== '' ? cardFieldNames : []}
                  existingKeys={existingKeys}
                  writable={isWritable(p)}
                  // Assigning goes through whatever this session can
                  // write to: archetypes when reference fields are
                  // targeted, otherwise the deck's actual cards.
                  assignOptions={hasArchetypeTargets
                    ? archetypes.map(a => ({ id: a.id, label: a.name }))
                    : deckCards.map(c => ({ id: c.id, label: c.name }))}
                  resolvedName={
                    archetypes.find(a => a.id === p.archetypeId)?.name
                    ?? deckCards.find(c => c.id === p.cardId)?.name}
                  onToggle={() => updateProposals(prev =>
                    prev.map(x => x.card.toLowerCase() === p.card.toLowerCase()
                      ? { ...x, checked: !x.checked } : x))}
                  onAssign={(id) => {
                    if (hasArchetypeTargets) {
                      const arch = archetypes.find(a => a.id === id);
                      const key = (arch?.name || '').toLowerCase();
                      const card = deckCards.find(c =>
                        (c.archetype || '').toLowerCase() === key || c.name.toLowerCase() === key);
                      updateProposals(prev => prev.map(x =>
                        x.card.toLowerCase() === p.card.toLowerCase()
                          ? { ...x, archetypeId: id, cardId: card?.id ?? x.cardId, checked: true }
                          : x));
                    } else {
                      const card = deckCards.find(c => c.id === id);
                      const key = (card?.archetype || card?.name || '').toLowerCase();
                      const archetypeId = archetypes.find(a => a.name.toLowerCase() === key)?.id;
                      updateProposals(prev => prev.map(x =>
                        x.card.toLowerCase() === p.card.toLowerCase()
                          ? { ...x, cardId: id, archetypeId: archetypeId ?? x.archetypeId, checked: true }
                          : x));
                    }
                  }}
                  onEditField={(label, value) => updateProposals(prev =>
                    prev.map(x => x.card.toLowerCase() === p.card.toLowerCase()
                      ? { ...x, fields: { ...x.fields, [label]: value } }
                      : x))}
                />
              ))}

              {combos.length > 0 && (
                <>
                  <div className="scribe__review-head scribe__review-head--combos">
                    <strong>{combos.length} combination{combos.length === 1 ? '' : 's'}</strong>
                    <span className="scribe__review-bulk">
                      <button onClick={() => updateCombos(p => p.map(x =>
                        ({ ...x, checked: x.archetypeIds.every(id => id != null) })))}>All</button>
                      <button onClick={() => updateCombos(p => p.map(x => ({ ...x, checked: false })))}>None</button>
                    </span>
                  </div>
                  {sortedCombos.map((c, i) => (
                    <ComboRow
                      key={`combo-${i}`}
                      combo={c}
                      onToggle={() => updateCombos(prev =>
                        prev.map(x => x === c ? { ...x, checked: !x.checked } : x))}
                      onEditMeaning={(text) => updateCombos(prev =>
                        prev.map(x => x === c ? { ...x, meaning: text } : x))}
                    />
                  ))}
                </>
              )}

              {entityRows.length > 0 && (
                <>
                  <div className="scribe__review-head scribe__review-head--combos">
                    <strong>{entityRows.length} reference entr{entityRows.length === 1 ? 'y' : 'ies'}</strong>
                    <span className="scribe__review-bulk">
                      <button onClick={() => updateEntityRows(p => p.map(x =>
                        ({ ...x, checked: x.resolved !== '' })))}>All</button>
                      <button onClick={() => updateEntityRows(p => p.map(x => ({ ...x, checked: false })))}>None</button>
                    </span>
                  </div>
                  {entityRows.map((r, i) => (
                    <EntityRowView
                      key={`entity-${r.kind}-${i}`}
                      row={r}
                      roster={rosterFor(r.kind)}
                      typedLabel={TYPED_ENTITY_KINDS.includes(r.kind) ? ctype : null}
                      onToggle={() => updateEntityRows(prev =>
                        prev.map(x => x === r ? { ...x, checked: !x.checked } : x))}
                      onResolve={(name) => updateEntityRows(prev =>
                        prev.map(x => x === r ? { ...x, resolved: name } : x))}
                      onEditContent={(text) => updateEntityRows(prev =>
                        prev.map(x => x === r ? { ...x, content: text } : x))}
                    />
                  ))}
                </>
              )}
            </div>
            <div className="scribe__actions">
              <button
                className="primary"
                onClick={handleApply}
                disabled={applying || (checkedProposals.length === 0
                  && checkedCombos.length === 0 && checkedEntities.length === 0)}
              >
                {applying ? 'Applying…' : `Apply ${[
                  checkedProposals.length > 0 && `${checkedProposals.length} card${checkedProposals.length === 1 ? '' : 's'}`,
                  checkedCombos.length > 0 && `${checkedCombos.length} combination${checkedCombos.length === 1 ? '' : 's'}`,
                  checkedEntities.length > 0 && `${checkedEntities.length} entr${checkedEntities.length === 1 ? 'y' : 'ies'}`,
                ].filter(Boolean).join(' + ') || 'selection'}`}
              </button>
              <button onClick={() => setStage('setup')} disabled={busy}>Back to setup</button>
              <ModalCancelButton>Close</ModalCancelButton>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ── One proposal row ─────────────────────────────────────────

function ProposalRow({
  proposal, selectedFields, cardFieldNames, existingKeys, writable,
  assignOptions, resolvedName, onToggle, onAssign, onEditField,
}: {
  proposal: Proposal;
  selectedFields: SourceField[];
  cardFieldNames: string[];
  existingKeys: Set<string>;
  /** Whether this row can reach at least one write target as-is. */
  writable: boolean;
  /** What "Assign to card…" offers: archetypes when reference fields
   *  are targeted, the deck's cards in a deck-only import. */
  assignOptions: { id: number; label: string }[];
  /** The app card/archetype this row resolved to, when it differs
   *  from the name the book used. */
  resolvedName?: string;
  onToggle: () => void;
  onAssign: (id: number) => void;
  onEditField: (label: string, value: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const p = proposal;
  const unmatched = !writable;

  const overwrites = selectedFields.some(f =>
    p.archetypeId &&
    p.fields[f.name] != null &&
    existingKeys.has(`${p.archetypeId}:${f.id}`));

  return (
    <div className={`scribe__proposal ${unmatched ? 'scribe__proposal--unmatched' : ''}`}>
      <div className="scribe__proposal-head">
        <label>
          <input type="checkbox" checked={p.checked} onChange={onToggle} disabled={unmatched} />
          <strong>{p.card}</strong>
        </label>
        {resolvedName && resolvedName.toLowerCase() !== p.card.toLowerCase() && (
          <span className="scribe__resolved">→ {resolvedName}</span>
        )}
        {unmatched && (
          <>
            <span className="scribe__badge scribe__badge--warn">
              {p.archetypeId || p.cardId ? 'no card on this deck' : 'no matching card'}
            </span>
            <select
              className="scribe__assign"
              value=""
              onChange={e => { if (e.target.value) onAssign(Number(e.target.value)); }}
              title="Pick which of the app's cards this proposal belongs to"
            >
              <option value="">Assign to card…</option>
              {assignOptions.map(o => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </>
        )}
        {overwrites && <span className="scribe__badge">overwrites existing</span>}
        {(p.flags || []).map((f, i) => (
          <span key={i} className="scribe__badge scribe__badge--flag">{f}</span>
        ))}
        <button className="scribe__expand" onClick={() => setExpanded(e => !e)}>
          {expanded ? 'Hide' : 'Show / edit'}
        </button>
      </div>
      {expanded && (
        <div className="scribe__proposal-fields">
          {Object.entries(p.fields).map(([label, content]) => (
            <div key={label} className="scribe__proposal-field">
              <span className="scribe__proposal-field-name">
                {label}
                {cardFieldNames.some(n => n.toLowerCase() === label.toLowerCase()) && ' (card field)'}
                {!selectedFields.some(f => f.name.toLowerCase() === label.toLowerCase()) &&
                  !cardFieldNames.some(n => n.toLowerCase() === label.toLowerCase()) && (
                  <span className="scribe__badge scribe__badge--warn">
                    not a target field — won't be applied
                  </span>
                )}
                {editingField !== label && (
                  <button
                    className="scribe__field-edit-btn"
                    onClick={() => { setEditingField(label); setDraft(content); }}
                  >
                    Edit
                  </button>
                )}
              </span>
              {editingField === label ? (
                <div className="scribe__field-edit">
                  <textarea
                    value={draft}
                    onChange={e => setDraft(e.target.value)}
                    rows={Math.min(12, Math.max(4, draft.split('\n').length + 1))}
                    autoFocus
                  />
                  <div className="scribe__field-edit-actions">
                    <button
                      className="primary"
                      onClick={() => { onEditField(label, draft); setEditingField(null); }}
                    >
                      Save
                    </button>
                    <button onClick={() => setEditingField(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="scribe__proposal-field-text">{content}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EntityRowView({ row: r, roster, typedLabel, onToggle, onResolve, onEditContent }: {
  row: EntityRow;
  roster: string[];
  /** Deck type for suit/rank rows (shown beside the kind). */
  typedLabel: string | null;
  onToggle: () => void;
  onResolve: (name: string) => void;
  onEditContent: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  return (
    <div className="scribe__combo-row">
      <label className="scribe__combo-row-main">
        <input
          type="checkbox"
          checked={r.checked}
          disabled={r.resolved === ''}
          onChange={onToggle}
        />
        <span className="scribe__entity-kind">
          {r.kind}{typedLabel ? ` · ${typedLabel}` : ''}
        </span>
        <select
          className="scribe__entity-select"
          value={r.resolved}
          onClick={e => e.preventDefault()}
          onChange={e => onResolve(e.target.value)}
        >
          <option value="">— pick an entry —</option>
          {roster.map(name => <option key={name} value={name}>{name}</option>)}
        </select>
        {r.resolved === '' && (
          <span className="scribe__entity-unmatched">“{r.entry}”</span>
        )}
        {!editing && (
          <button
            type="button"
            className="scribe__field-edit-btn"
            onClick={(e) => { e.preventDefault(); setEditing(true); setDraft(r.content); }}
          >
            Edit
          </button>
        )}
      </label>
      {r.flags && r.flags.length > 0 && (
        <div className="scribe__entity-flags">⚑ {r.flags.join(' · ')}</div>
      )}
      {editing ? (
        <div className="scribe__field-edit">
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            rows={Math.min(12, Math.max(4, draft.split('\n').length + 1))}
            autoFocus
          />
          <div className="scribe__field-edit-actions">
            <button
              className="primary"
              onClick={() => { onEditContent(draft); setEditing(false); }}
            >
              Save
            </button>
            <button onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="scribe__proposal-field-text">{r.content}</div>
      )}
    </div>
  );
}

function ComboRow({ combo: c, onToggle, onEditMeaning }: {
  combo: ComboProposal;
  onToggle: () => void;
  onEditMeaning: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const unmatched = c.cards.filter((_, j) => c.archetypeIds[j] == null);
  return (
    <div className="scribe__combo-row">
      <label className="scribe__combo-row-main">
        <input
          type="checkbox"
          checked={c.checked}
          disabled={unmatched.length > 0}
          onChange={onToggle}
        />
        <span className="scribe__combo-cards">
          {c.cards.map((name, j) =>
            `${name}${c.reversed?.[j] ? ' (rev)' : ''}`).join(' + ')}
        </span>
        {!editing && (
          <button
            type="button"
            className="scribe__field-edit-btn"
            onClick={(e) => { e.preventDefault(); setEditing(true); setDraft(c.meaning); }}
          >
            Edit
          </button>
        )}
      </label>
      {editing ? (
        <div className="scribe__field-edit">
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            rows={Math.min(8, Math.max(3, draft.split('\n').length + 1))}
            autoFocus
          />
          <div className="scribe__field-edit-actions">
            <button
              className="primary"
              onClick={() => { onEditMeaning(draft); setEditing(false); }}
            >
              Save
            </button>
            <button onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="scribe__combo-meaning" title={c.meaning}>{c.meaning}</div>
      )}
      {unmatched.length > 0 && (
        <div className="scribe__combo-warn">
          Unmatched: {unmatched.join(', ')} — ask the model to
          use the app's archetype names for these.
        </div>
      )}
      {c.flags && c.flags.length > 0 && (
        <div className="scribe__combo-warn">{c.flags.join(' · ')}</div>
      )}
    </div>
  );
}

// ── Prompt + parsing helpers ─────────────────────────────────


type RawProposal = { card: string; fields: Record<string, string>; flags?: string[] };

/** Extraction-phase prose should be a short status note. When the
 *  model rambles (or quotes book text despite instructions), trim the
 *  chat display — the content that matters is in the review panel,
 *  and nothing in the chat is ever written to the database. */
function trimProse(text: string, max = 700): string {
  if (text.length <= max) return text;
  return text.slice(0, max).trimEnd() +
    `\n\n[…trimmed ${text.length - max} characters of extra prose. Extracted card content lives in the review panel on the right — if something you saw here is missing from a card there, ask the model to re-send that card.]`;
}

/** "The Fool, The Magician, … (+12 more)" — every chat round names the
 *  cards it touched, so anything odd is traceable to specific rows. */
function summarizeCards(cards: { card: string }[], max = 12): string {
  const names = cards.map(c => c.card);
  if (names.length <= max) return names.join(', ');
  return `${names.slice(0, max).join(', ')} (+${names.length - max} more)`;
}

/** Split a model reply into visible prose and the parsed proposals.
 *
 *  Deliberately forgiving about the block format: models sometimes tag
 *  the fence differently (```JSON, bare ```), skip the fence entirely,
 *  or get cut off at the reply-length limit mid-JSON. A truncated
 *  proposals array is salvaged up to its last complete card so a long
 *  extraction degrades to "most cards + a warning" instead of nothing. */
function splitReply(reply: string): {
  visible: string;
  parsed: RawProposal[] | null;
  parsedCombos: RawCombo[] | null;
  parsedEntries: RawEntry[] | null;
} {
  const KEY_RE = /"(proposals|combinations|entries)"/;
  const candidates: string[] = [];
  // Closed fences, any tag casing, last one wins
  for (const m of reply.matchAll(/```[a-zA-Z]*\s*([\s\S]*?)```/g)) {
    if (KEY_RE.test(m[1])) candidates.push(m[1]);
  }
  // Unterminated final fence (typical of a truncated reply)
  if (!candidates.length) {
    const open = reply.match(/```[a-zA-Z]*\s*([\s\S]*)$/);
    if (open && KEY_RE.test(open[1])) candidates.push(open[1]);
  }
  // No fence at all — bare JSON object somewhere in the reply
  if (!candidates.length) {
    const idx = reply.search(/\{\s*"(proposals|combinations|entries)"/);
    if (idx !== -1) candidates.push(reply.slice(idx));
  }

  let parsed: RawProposal[] | null = null;
  let parsedCombos: RawCombo[] | null = null;
  let parsedEntries: RawEntry[] | null = null;
  for (let i = candidates.length - 1;
       i >= 0 && !parsed && !parsedCombos && !parsedEntries; i--) {
    parsed = parseProposals(candidates[i]);
    parsedCombos = parseCombinations(candidates[i]);
    parsedEntries = parseEntries(candidates[i]);
  }

  // Prose = the reply minus fenced blocks (terminated or not) and any
  // bare proposals JSON we managed to parse.
  let visible = reply.replace(/```[\s\S]*?(```|$)/g, '');
  if (parsed || parsedCombos || parsedEntries) {
    visible = visible.replace(/\{\s*"(proposals|combinations|entries)"[\s\S]*$/, '');
  }
  visible = visible.replace(/\n{3,}/g, '\n\n').trim();
  return { visible, parsed, parsedCombos, parsedEntries };
}

/** Parse the "entries" array from a JSON block; null when missing or
 *  unparseable. */
function parseEntries(jsonText: string): RawEntry[] | null {
  try {
    const obj = JSON.parse(jsonText);
    return Array.isArray(obj?.entries) ? (obj.entries as RawEntry[]) : null;
  } catch {
    return null;
  }
}

/** Merge model-emitted entries into the running rows, keyed by
 *  (kind, entry). Only enabled kinds are accepted; a re-sent entry's
 *  content replaces the previous version (per the prompt contract). */
function mergeEntities(
  previous: EntityRow[],
  incoming: RawEntry[],
  enabledKinds: EntityKind[],
  rosterFor: (kind: EntityKind) => string[],
): EntityRow[] {
  const result = [...previous];
  for (const raw of incoming) {
    const kind = String(raw?.kind ?? '') as EntityKind;
    const entry = String(raw?.entry ?? '').trim();
    const content = String(raw?.content ?? '').trim();
    if (!enabledKinds.includes(kind) || !entry || !content) continue;
    const flags = Array.isArray(raw.flags)
      ? (raw.flags as unknown[]).filter((f): f is string => typeof f === 'string')
      : undefined;
    const resolved = resolveEntityName(entry, rosterFor(kind));
    const i = result.findIndex(r =>
      r.kind === kind && r.entry.toLowerCase() === entry.toLowerCase());
    if (i >= 0) {
      result[i] = {
        ...result[i], content, flags,
        resolved: result[i].resolved || resolved,
      };
    } else {
      result.push({ kind, entry, content, flags, resolved, checked: true });
    }
  }
  // Kind order first, then roster order, unmatched rows at the end.
  return result.sort((a, b) => {
    const ka = enabledKinds.indexOf(a.kind);
    const kb = enabledKinds.indexOf(b.kind);
    if (ka !== kb) return ka - kb;
    const ra = a.resolved ? rosterFor(a.kind).indexOf(a.resolved) : 999;
    const rb = b.resolved ? rosterFor(b.kind).indexOf(b.resolved) : 999;
    return ra - rb || a.entry.localeCompare(b.entry);
  });
}

/** Parse the "combinations" array from a JSON block; null when
 *  missing or unparseable (no salvage pass — combination entries are
 *  short, so truncation rarely lands inside them). */
function parseCombinations(jsonText: string): RawCombo[] | null {
  try {
    const obj = JSON.parse(jsonText);
    if (Array.isArray(obj?.combinations) && obj.combinations.length) {
      return obj.combinations;
    }
    return null;
  } catch {
    return null;
  }
}

/** Parse a proposals JSON string; on failure, salvage every complete
 *  card object from a truncated array. */
function parseProposals(jsonText: string): RawProposal[] | null {
  try {
    const obj = JSON.parse(jsonText);
    if (Array.isArray(obj?.proposals)) return obj.proposals;
    return null;
  } catch { /* fall through to salvage */ }

  const keyIdx = jsonText.indexOf('"proposals"');
  if (keyIdx === -1) return null;
  const arrStart = jsonText.indexOf('[', keyIdx);
  if (arrStart === -1) return null;

  // Walk the array tracking strings/escapes/nesting; remember where
  // each complete top-level object ends, then rebuild a closed array.
  let depth = 0;
  let inString = false;
  let escaped = false;
  let lastComplete = -1;
  for (let i = arrStart; i < jsonText.length; i++) {
    const ch = jsonText[i];
    if (escaped) { escaped = false; continue; }
    if (inString) {
      if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') inString = true;
    else if (ch === '{' || ch === '[') depth++;
    else if (ch === '}' || ch === ']') {
      depth--;
      if (depth === 1) lastComplete = i; // back at array level: object done
      if (depth === 0) break;            // array itself closed
    }
  }
  if (lastComplete === -1) return null;
  try {
    const arr = JSON.parse(jsonText.slice(arrStart, lastComplete + 1) + ']');
    return Array.isArray(arr) && arr.length ? arr : null;
  } catch {
    return null;
  }
}

/** Merge a JSON block's cards into the running proposal list.
 *
 *  Keyed by card name (case-insensitive): a re-sent card updates its
 *  existing row field-by-field and keeps its checkbox state; a new
 *  card is appended. Nothing is ever dropped — the model only sends
 *  additions and changes, never the full set.
 *
 *  preferLonger is used during extraction, where overlapping parts can
 *  finish in any order: a complete version of a boundary-straddling
 *  card must not be clobbered by the cut-off version arriving later.
 *  Refinement merges leave it off so "shorten this field" works. */
function mergeProposals(
  previous: Proposal[],
  incoming: RawProposal[],
  archetypes: Archetype[],
  deckCards: Card[],
  preferLonger = false,
): Proposal[] {
  const archByName = new Map(archetypes.map(a => [a.name.toLowerCase(), a.id]));
  const result = [...previous];
  const indexByKey = new Map(result.map((p, i) => [p.card.toLowerCase(), i] as const));

  for (const raw of incoming) {
    if (!raw || typeof raw.card !== 'string' || !raw.fields || typeof raw.fields !== 'object') continue;
    const key = raw.card.toLowerCase();
    const archetypeId = archByName.get(key);
    const card = deckCards.find(c =>
      (c.archetype || '').toLowerCase() === key || c.name.toLowerCase() === key);
    const fields = Object.fromEntries(
      Object.entries(raw.fields).filter(([, v]) => typeof v === 'string')) as Record<string, string>;
    const flags = Array.isArray(raw.flags) ? raw.flags.filter(f => typeof f === 'string') : undefined;

    const existingIdx = indexByKey.get(key);
    if (existingIdx != null) {
      const existing = result[existingIdx];
      const mergedFields = { ...existing.fields };
      let accepted = 0;
      for (const [k, v] of Object.entries(fields)) {
        const current = mergedFields[k];
        if (preferLonger && typeof current === 'string' && current.length > v.length) continue;
        mergedFields[k] = v;
        accepted++;
      }
      // Flags follow the content decision. When this round's version
      // of the card won (or it's a refinement), its flags replace the
      // old ones — including replacing them with nothing, so a card
      // completed by a later part sheds its stale "cut off" flag. A
      // losing fragment's flags never overwrite the winner's.
      const nextFlags = (!preferLonger || accepted > 0) ? flags : existing.flags;
      result[existingIdx] = {
        ...existing,
        fields: mergedFields,
        flags: nextFlags?.length ? nextFlags : undefined,
        archetypeId: existing.archetypeId ?? archetypeId,
        cardId: existing.cardId ?? card?.id,
      };
    } else {
      result.push({
        card: raw.card,
        fields,
        flags,
        archetypeId,
        cardId: card?.id,
        checked: archetypeId != null || card != null,
      });
      indexByKey.set(key, result.length - 1);
    }
  }
  return result;
}

/** Merge a JSON block's combinations into the running list. Keyed by
 *  the card names + reversal pattern + meaning text (case-insensitive)
 *  so overlapping parts don't duplicate entries; a re-sent identical
 *  combination keeps its checkbox state. */
function mergeCombos(
  previous: ComboProposal[],
  incoming: RawCombo[],
  archetypes: Archetype[],
): ComboProposal[] {
  const archByName = new Map(archetypes.map(a => [a.name.toLowerCase(), a.id]));
  const result = [...previous];
  const keyOf = (c: { cards: string[]; reversed?: boolean[]; meaning: string }) =>
    `${c.cards.map(n => n.toLowerCase()).join('+')}|${(c.reversed || []).map(r => r ? 'r' : 'u').join('')}|${c.meaning.trim().toLowerCase()}`;
  const seen = new Set(result.map(keyOf));

  for (const raw of incoming) {
    if (!raw || !Array.isArray(raw.cards) || typeof raw.meaning !== 'string') continue;
    const cards = raw.cards.filter((n): n is string => typeof n === 'string' && !!n.trim());
    const meaning = raw.meaning.trim();
    if (cards.length < 2 || cards.length > 3 || !meaning) continue;
    const reversed = Array.isArray(raw.reversed)
      ? cards.map((_, i) => Boolean((raw.reversed as unknown[])[i]))
      : undefined;
    const flags = Array.isArray(raw.flags)
      ? (raw.flags as unknown[]).filter((f): f is string => typeof f === 'string')
      : undefined;
    const entry = { cards, reversed, meaning };
    if (seen.has(keyOf(entry))) continue;
    seen.add(keyOf(entry));
    const archetypeIds = cards.map(n => archByName.get(n.toLowerCase()));
    result.push({
      cards,
      meaning,
      reversed,
      flags: flags?.length ? flags : undefined,
      archetypeIds,
      checked: archetypeIds.every(id => id != null),
    });
  }
  return result;
}

// buildUnits / splitUnit / image reading moved to scribeShared.
