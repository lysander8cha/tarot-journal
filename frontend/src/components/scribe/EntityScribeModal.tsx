/**
 * The Scribe's reference-entries mode — imports source texts onto
 * reference ENTITIES (signs, planets, sephiroth, tree paths, chakras,
 * numbers, suits, ranks) rather than cards. Shares its machinery and
 * visual language with the card mode (ScribeModal) via scribeShared:
 * material intake (ebooks, text, page photos, scanned PDFs), unit
 * chunking, and the chat pane.
 *
 * One entity kind per import (deliberate — a chapter on the suits, a
 * chapter on the sephiroth); the card Scribe's merged imports handle
 * whole books emitting "proposals"/"combinations"/"entries" together.
 * Both render from the same user-editable Scribe prompt template.
 * Applied notes merge into each entity's one note per source (append,
 * never clobber — the backend's entity_note target).
 */
import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Modal, { ModalCancelButton } from '../common/Modal';
import { useToast } from '../../context/ToastContext';
import { getReferenceSources } from '../../api/referenceSources';
import type { EntityKind } from '../../api/reference';
import { applyScribeWrites, type ScribeWrite } from '../../api/scribe';
import { llmChat, type LlmMessage } from '../../api/llm';
import { renderScribePrompt, useActivePrompt } from '../../utils/assistantPrompts';
import {
  ENTITY_KIND_LABELS,
  TYPED_ENTITY_KINDS,
  entityTextToHtml,
  normEntity,
  resolveEntityName,
  useEntityRosters,
} from './entityRosters';
import type { ReferenceSource } from '../../types';
import {
  ScribeMaterialsField,
  buildUnits,
  makePastedMaterial,
  readScribeFiles,
  splitUnit,
  type ExtractionUnit,
  type Material,
  SCRIBE_CHAT_PLACEHOLDER,
} from './scribeShared';
import ChatPanel, { type ChatDisplayMessage } from '../common/ChatPanel';
import './ScribeModal.css';
import './EntityScribeModal.css';

interface EntityScribeModalProps {
  open: boolean;
  onClose: () => void;
  /** Preselected kind (the section the user launched from). */
  initialKind?: EntityKind;
  /** Preselected deck type, for suit/rank kinds. */
  initialType?: string | null;
}

interface EntityProposal {
  /** The name the model used (raw). */
  entry: string;
  content: string;
  flags?: string[];
  /** Resolved entity name from the roster ('' = unmatched). */
  resolved: string;
  checked: boolean;
}

const EXTRACT_SUBJECT = 'reference content';

export default function EntityScribeModal({
  open,
  onClose,
  initialKind,
  initialType,
}: EntityScribeModalProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  // ── Setup ─────────────────────────────────────────────────
  const [kind, setKind] = useState<EntityKind>(initialKind ?? 'sign');
  const [deckType, setDeckType] = useState<string | null>(initialType ?? null);
  const [sourceId, setSourceId] = useState<number | ''>('');
  const [instructions, setInstructions] = useState('');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [pasteText, setPasteText] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [stage, setStage] = useState<'setup' | 'review'>('setup');

  const { data: sources = [] } = useQuery<ReferenceSource[]>({
    queryKey: ['reference-sources'],
    queryFn: () => getReferenceSources(),
    enabled: open,
  });

  // Entity roster for the chosen kind (shared with the card Scribe's
  // merged imports).
  const typed = TYPED_ENTITY_KINDS.includes(kind);
  const { rosters, suitTypes, resolvedDeckType } = useEntityRosters(
    [kind], typed ? deckType : null, open);
  const resolvedType = typed ? resolvedDeckType : null;
  const entities = rosters.get(kind) ?? [];

  const resolveEntity = (raw: string) => resolveEntityName(raw, entities);

  // Deck-type-scoped kinds (suits, ranks) only offer sources covering
  // that type — mirroring the entity-notes picker.
  const selectableSources = typed && resolvedType
    ? sources.filter(s => (s.cartomancy_types || []).includes(resolvedType))
    : sources;
  // A source chosen under one kind/type may not qualify after a switch.
  useEffect(() => {
    if (sourceId !== '' && !selectableSources.some(s => s.id === sourceId)) {
      setSourceId('');
    }
  }, [sourceId, selectableSources]);

  // ── Review state ──────────────────────────────────────────
  const [messages, setMessages] = useState<LlmMessage[]>([]);
  const [display, setDisplay] = useState<ChatDisplayMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [proposals, setProposals] = useState<EntityProposal[]>([]);
  const proposalsRef = useRef<EntityProposal[]>([]);
  const systemPromptRef = useRef('');

  const updateProposals = (fn: (cur: EntityProposal[]) => EntityProposal[]) => {
    proposalsRef.current = fn(proposalsRef.current);
    setProposals(proposalsRef.current);
  };

  // ── Materials (shared intake — ebooks, text, photos) ──────
  const addFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setExtracting(true);
    const added = await readScribeFiles(files, showToast);
    setMaterials(m => [...m, ...added]);
    setExtracting(false);
  };

  const addPaste = () => {
    if (!pasteText.trim()) return;
    setMaterials(m => [...m, makePastedMaterial(pasteText.trim())]);
    setPasteText('');
  };

  // ── Prompt + extraction ───────────────────────────────────
  // Entity-only imports render from the same user-editable Scribe
  // template as card imports; the appended entities block declares
  // the card instructions out of scope.
  const { prompt: scribeTemplate, ready: promptReady } = useActivePrompt('scribe', open);

  const buildSystemPrompt = () => {
    const sourceName = sources.find(s => s.id === sourceId)?.name ?? 'the source';
    const kindLabel = typed && resolvedType
      ? `${resolvedType} ${ENTITY_KIND_LABELS[kind].toLowerCase()}`
      : ENTITY_KIND_LABELS[kind];
    return renderScribePrompt(scribeTemplate, {
      cartomancyType: resolvedType ?? 'n/a',
      sourceName,
      archetypeNames: '(none — this import extracts reference entries only)',
      targetFields: '(none — this import extracts reference entries only)',
    }, instructions, undefined, {
      kinds: [{ kind, label: kindLabel, roster: entities }],
      entitiesOnly: true,
    });
  };

  const parseReply = (text: string) => {
    const match = text.match(/```json\s*([\s\S]*?)```/);
    if (!match) return;
    try {
      const parsed = JSON.parse(match[1]);
      // "entries" is the canonical key; "proposals" accepted defensively.
      const rows: { entry?: unknown; content?: unknown; flags?: unknown }[] =
        Array.isArray(parsed?.entries) ? parsed.entries
          : Array.isArray(parsed?.proposals) ? parsed.proposals : [];
      updateProposals(cur => {
        const next = [...cur];
        for (const row of rows) {
          const entry = String(row.entry ?? '').trim();
          const content = String(row.content ?? '').trim();
          if (!entry || !content) continue;
          const flags = Array.isArray(row.flags) ? row.flags.map(String) : [];
          const resolved = resolveEntity(entry);
          const i = next.findIndex(p => normEntity(p.entry) === normEntity(entry));
          if (i >= 0) {
            next[i] = { ...next[i], content, flags, resolved: next[i].resolved || resolved };
          } else {
            next.push({ entry, content, flags, resolved, checked: true });
          }
        }
        // Roster order first, unmatched rows at the end
        return next.sort((a, b) => {
          const ai = a.resolved ? entities.indexOf(a.resolved) : 999;
          const bi = b.resolved ? entities.indexOf(b.resolved) : 999;
          return ai - bi || a.entry.localeCompare(b.entry);
        });
      });
    } catch {
      showToast('A reply contained unparseable JSON — ask the model to re-send it.', 'error');
    }
  };

  const stripJson = (text: string) =>
    text.replace(/```json[\s\S]*?```/g, '(entries updated)').trim();

  const runUnits = async (units: ExtractionUnit[], startHistory: LlmMessage[]) => {
    // Sequential with split-on-overflow: entity sources are chapters,
    // not whole books, so the card mode's concurrency isn't needed.
    let history = [...startHistory];
    const queue = [...units];
    while (queue.length > 0) {
      const unit = queue.shift()!;
      const userMsg: LlmMessage = { role: 'user', content: unit.parts };
      setDisplay(d => [...d, { role: 'user', text: `📄 ${unit.label}` }]);
      const reply = await llmChat({
        messages: [...history, userMsg],
        system: systemPromptRef.current,
        feature: 'scribe',
        max_tokens: 64000,
      });
      if (reply.truncated) {
        const halves = splitUnit(unit, EXTRACT_SUBJECT);
        if (halves) {
          setDisplay(d => [...d, {
            role: 'assistant',
            text: `${unit.label} overflowed — splitting it in two and retrying.`,
          }]);
          queue.unshift(...halves);
          continue;
        }
      }
      parseReply(reply.text);
      setDisplay(d => [...d, { role: 'assistant', text: stripJson(reply.text) }]);
      history = [...history, userMsg, { role: 'assistant', content: reply.text }];
      setMessages(history);
    }
  };

  const startExtraction = async () => {
    systemPromptRef.current = buildSystemPrompt();
    setStage('review');
    setBusy(true);
    try {
      await runUnits(buildUnits(materials, EXTRACT_SUBJECT), []);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Extraction failed', 'error');
    } finally {
      setBusy(false);
    }
  };

  const sendChat = async (text: string) => {
    if (busy) return;
    setBusy(true);
    const userMsg: LlmMessage = { role: 'user', content: text };
    setDisplay(d => [...d, { role: 'user', text }]);
    try {
      const reply = await llmChat({
        messages: [...messages, userMsg],
        system: systemPromptRef.current,
        feature: 'scribe',
        max_tokens: 64000,
        thinking: true,
      });
      parseReply(reply.text);
      setDisplay(d => [...d, { role: 'assistant', text: stripJson(reply.text) }]);
      setMessages(m => [...m, userMsg, { role: 'assistant', content: reply.text }]);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Request failed', 'error');
    } finally {
      setBusy(false);
    }
  };

  // ── Apply ─────────────────────────────────────────────────
  const applyChecked = async () => {
    if (sourceId === '') return;
    const rows = proposalsRef.current.filter(p => p.checked && p.resolved);
    if (rows.length === 0) {
      showToast('Nothing checked (or nothing matched an entry).', 'error');
      return;
    }
    setApplying(true);
    try {
      const writes: ScribeWrite[] = rows.map(p => ({
        target: 'entity_note',
        kind,
        key: typed && resolvedType ? `${resolvedType}::${p.resolved}` : p.resolved,
        source_id: sourceId,
        content: entityTextToHtml(p.content),
      }));
      const result = await applyScribeWrites(writes);
      queryClient.invalidateQueries({
        predicate: q => q.queryKey[0] === 'entity-notes',
      });
      const bits = [`${result.applied} applied`];
      if (result.skipped) bits.push(`${result.skipped} already present`);
      if (result.errors.length) {
        bits.push(`${result.errors.length} failed (details in the chat panel)`);
        // Writes map 1:1 onto the checked rows, so errors name their entry.
        const details = result.errors.map(e =>
          `• ${rows[e.index]?.resolved ?? `write #${e.index + 1}`} — ${e.error}`);
        setDisplay(d => [...d, {
          role: 'note',
          text: `${result.errors.length} write${result.errors.length === 1 ? '' : 's'} failed:\n${details.join('\n')}`,
        }]);
      }
      showToast(`Source texts: ${bits.join(', ')}.`, result.errors.length ? 'error' : 'success');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Apply failed', 'error');
    } finally {
      setApplying(false);
    }
  };

  const canStart = sourceId !== '' && materials.length > 0 &&
    entities.length > 0 && !extracting && promptReady;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Scribe — Reference Entries"
      width={stage === 'setup' ? 620 : 1100}
    >
      {stage === 'setup' && (
        <div className="scribe__setup">
          <div className="scribe__field">
            <label>What is this source about?</label>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as EntityKind)}
            >
              {(Object.keys(ENTITY_KIND_LABELS) as EntityKind[]).map(k => (
                <option key={k} value={k}>{ENTITY_KIND_LABELS[k]}</option>
              ))}
            </select>
          </div>
          {typed && (
            <div className="scribe__field">
              <label>Deck type</label>
              <select
                value={resolvedType ?? ''}
                onChange={(e) => setDeckType(e.target.value)}
              >
                {suitTypes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          )}
          <div className="scribe__field">
            <label>Reference source these texts belong to</label>
            <select
              value={sourceId === '' ? '' : String(sourceId)}
              onChange={(e) => setSourceId(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">Choose a source…</option>
              {selectableSources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            {typed && resolvedType && selectableSources.length === 0 && (
              <p className="scribe__hint">
                No {resolvedType} sources yet — cover the type on a source
                in Settings → Reference Sources first.
              </p>
            )}
          </div>

          <ScribeMaterialsField
            materials={materials}
            onRemove={(id) => setMaterials(list => list.filter(x => x.id !== id))}
            onAddFiles={addFiles}
            extracting={extracting}
          >
            <textarea
              className="entity-scribe__paste"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="…or paste text here"
              rows={3}
            />
            {pasteText.trim() && (
              <button type="button" onClick={addPaste}>Add pasted text</button>
            )}
          </ScribeMaterialsField>

          <div className="scribe__field">
            <label>Instructions for this import (optional)</label>
            <textarea
              className="scribe__instructions"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. only chapters 3–4 are about the suits; keep the author's headings"
              rows={2}
            />
          </div>

          <div className="scribe__actions">
            <button
              type="button"
              className="primary"
              disabled={!canStart}
              onClick={startExtraction}
            >
              {extracting ? 'Reading files…' : 'Start extraction'}
            </button>
            <ModalCancelButton>Cancel</ModalCancelButton>
          </div>
        </div>
      )}

      {stage === 'review' && (
        <div className="entity-scribe__review">
          <ChatPanel
            messages={display}
            busy={busy}
            onSend={sendChat}
            placeholder={SCRIBE_CHAT_PLACEHOLDER}
          />

          <div className="entity-scribe__panel">
            <div className="entity-scribe__panel-head">
              <strong>{proposals.length}</strong>&nbsp;entries proposed ·{' '}
              {entities.length - new Set(proposals.map(p => p.resolved).filter(Boolean)).size}{' '}
              uncovered
            </div>
            <div className="entity-scribe__rows">
              {proposals.map((p, i) => (
                <div key={`${p.entry}-${i}`} className="entity-scribe__row">
                  <div className="entity-scribe__row-head">
                    <input
                      type="checkbox"
                      checked={p.checked}
                      onChange={(e) => updateProposals(cur =>
                        cur.map((x, j) => (j === i ? { ...x, checked: e.target.checked } : x)))}
                    />
                    <select
                      value={p.resolved}
                      onChange={(e) => updateProposals(cur =>
                        cur.map((x, j) => (j === i ? { ...x, resolved: e.target.value } : x)))}
                    >
                      <option value="">— pick an entry —</option>
                      {entities.map(name => (
                        <option key={name} value={name}>{name}</option>
                      ))}
                    </select>
                    {p.resolved === '' && (
                      <span className="entity-scribe__unmatched">“{p.entry}”</span>
                    )}
                  </div>
                  {p.flags && p.flags.length > 0 && (
                    <div className="entity-scribe__flags">⚑ {p.flags.join(' · ')}</div>
                  )}
                  <textarea
                    value={p.content}
                    rows={Math.min(10, Math.max(3, Math.ceil(p.content.length / 90)))}
                    onChange={(e) => updateProposals(cur =>
                      cur.map((x, j) => (j === i ? { ...x, content: e.target.value } : x)))}
                  />
                </div>
              ))}
              {proposals.length === 0 && !busy && (
                <p className="entity-scribe__empty">No entries proposed yet.</p>
              )}
            </div>
            <div className="entity-scribe__actions">
              <ModalCancelButton>Close</ModalCancelButton>
              <button
                type="button"
                className="primary"
                disabled={applying || busy || proposals.every(p => !p.checked || !p.resolved)}
                onClick={applyChecked}
              >
                {applying ? 'Applying…' : 'Apply checked'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
