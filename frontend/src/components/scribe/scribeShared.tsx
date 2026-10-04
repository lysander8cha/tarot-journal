/**
 * Shared Scribe machinery — one visual and mechanical language for
 * both Scribe modes (card meanings in ScribeModal, reference entries
 * in EntityScribeModal): source-material intake (ebooks, text, page
 * photos, scanned PDFs), chunking into extraction units, and the
 * setup/chat UI pieces both modals render.
 *
 * Door left open for a future merged mode (one extraction run
 * emitting cards + combinations + entries together): the unit builder
 * takes its "extract the X found in this part" subject as a
 * parameter, and the reply protocol keys are disjoint ("proposals" /
 * "combinations" / "entries"), so a merged prompt could combine them
 * without changing this module.
 */
import type { ReactNode } from 'react';
import { extractSourceText, convertSourceImage } from '../../api/scribe';
import type { LlmMessagePart } from '../../api/llm';
import './ScribeModal.css';

// ── Source material ──────────────────────────────────────────
export interface Material {
  id: number;
  filename: string;
  kind: 'text' | 'image';
  text?: string;       // extracted text (ebooks)
  data?: string;       // base64 (images)
  mediaType?: string;
  charCount?: number;
  warning?: string | null;
}

/** One extraction request: a chunk of book text, or a group of page
 *  photos. text/images keep the raw material so a unit whose reply
 *  overflows the output limit can be split in half and re-queued. */
export interface ExtractionUnit {
  label: string;
  parts: LlmMessagePart[];
  text?: string;
  images?: Material[];
}

// Ceiling on total source text per session (the refinement chat holds
// the whole conversation and must fit the big models' context).
export const MAX_SOURCE_CHARS = 3_000_000;
export const CHUNK_CHARS = 90_000;
export const IMAGES_PER_UNIT = 8;
export const CHUNK_OVERLAP = 8_000;
export const IMAGE_MAX_EDGE = 2000;

let materialIdCounter = 1;

/** Read a FileList into Materials: images (downscaled in-browser,
 *  HEIC via the backend), ebooks/text via the server extractor,
 *  scanned PDFs as page images. Errors surface through showToast and
 *  never abort the rest of the batch. */
export async function readScribeFiles(
  files: FileList,
  showToast: (message: string, type?: 'error' | 'success' | 'warning') => void,
): Promise<Material[]> {
  const out: Material[] = [];
  for (const file of Array.from(files)) {
    try {
      // HEIC/HEIF (iPhone photos) sometimes arrive with no MIME type
      // at all — catch them by extension so they take the image path.
      const isImage = file.type.startsWith('image/')
        || /\.(heic|heif)$/i.test(file.name);
      if (isImage) {
        let data: string, mediaType: string;
        try {
          ({ data, mediaType } = await readImageDownscaled(file));
        } catch {
          const converted = await convertSourceImage(file);
          data = converted.data;
          mediaType = converted.media_type;
        }
        out.push({
          id: materialIdCounter++, filename: file.name, kind: 'image',
          data, mediaType,
        });
      } else {
        const result = await extractSourceText(file);
        if (result.images?.length) {
          // Scanned PDF: pages rendered to images server-side.
          out.push(...result.images.map((img, i) => ({
            id: materialIdCounter++,
            filename: `${result.filename} · p${i + 1}`,
            kind: 'image' as const,
            data: img.data,
            mediaType: img.media_type,
          })));
          if (result.warning) showToast(result.warning, 'success');
        } else {
          out.push({
            id: materialIdCounter++, filename: result.filename, kind: 'text',
            text: result.text, charCount: result.char_count,
            warning: result.warning,
          });
        }
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } };
      showToast(e.response?.data?.error || `Couldn't read ${file.name}.`);
    }
  }
  return out;
}

/** Make a pasted-text material. */
export function makePastedMaterial(text: string): Material {
  return {
    id: materialIdCounter++,
    filename: `Pasted text (${Math.round(text.length / 1000)}k characters)`,
    kind: 'text',
    text,
    charCount: text.length,
  };
}

// ── Unit building (chunking) ─────────────────────────────────

function makeTextUnit(label: string, text: string, subject: string): ExtractionUnit {
  return {
    label,
    text,
    parts: [{
      type: 'text',
      text: `Source material — ${label}. Extract the ${subject} found in this part now:\n\n${text}`,
    }],
  };
}

function makeImageUnit(label: string, group: Material[], subject: string): ExtractionUnit {
  return {
    label,
    images: group,
    parts: [
      {
        type: 'text',
        text: `Source material — ${label}. Extract the ${subject} found in these page photos now:`,
      },
      ...group.map(m => ({
        type: 'image' as const,
        media_type: m.mediaType,
        data: m.data,
      })),
    ],
  };
}

export function buildUnits(
  materials: Material[],
  subject = 'card content',
): ExtractionUnit[] {
  const units: ExtractionUnit[] = [];
  let used = 0;
  for (const m of materials) {
    if (m.kind !== 'text' || !m.text) continue;
    let text = m.text;
    if (used + text.length > MAX_SOURCE_CHARS) {
      text = text.slice(0, Math.max(0, MAX_SOURCE_CHARS - used));
    }
    used += text.length;
    if (!text) continue;
    const chunks = splitIntoChunks(text);
    chunks.forEach((chunk, i) => {
      const label = chunks.length > 1
        ? `${m.filename} (part ${i + 1} of ${chunks.length})`
        : m.filename;
      units.push(makeTextUnit(label, chunk, subject));
    });
  }
  const images = materials.filter(m => m.kind === 'image' && m.data);
  for (let i = 0; i < images.length; i += IMAGES_PER_UNIT) {
    const group = images.slice(i, i + IMAGES_PER_UNIT);
    const label = images.length > IMAGES_PER_UNIT
      ? `photos ${i + 1}–${i + group.length} of ${images.length}`
      : `${group.length} photo${group.length === 1 ? '' : 's'}`;
    units.push(makeImageUnit(label, group, subject));
  }
  return units;
}

/** Halve a unit whose reply overflowed the output limit, so each half
 *  yields a reply that fits. Returns null when it can't be split
 *  smaller (tiny text, single photo). */
export function splitUnit(
  unit: ExtractionUnit,
  subject = 'card content',
): ExtractionUnit[] | null {
  if (unit.text && unit.text.length > 20_000) {
    const halves = splitIntoChunks(
      unit.text, Math.ceil(unit.text.length / 2) + CHUNK_OVERLAP);
    if (halves.length < 2) return null;
    return halves.map((h, i) =>
      makeTextUnit(`${unit.label} · piece ${i + 1} of ${halves.length}`, h, subject));
  }
  if (unit.images && unit.images.length > 1) {
    const mid = Math.ceil(unit.images.length / 2);
    return [unit.images.slice(0, mid), unit.images.slice(mid)].map((g, i) =>
      makeImageUnit(`${unit.label} · piece ${i + 1} of 2`, g, subject));
  }
  return null;
}

function splitIntoChunks(text: string, max = CHUNK_CHARS): string[] {
  if (text.length <= max) return [text];
  const chunks: string[] = [];
  let pos = 0;
  for (;;) {
    let end = Math.min(pos + max, text.length);
    if (end < text.length) {
      // Prefer breaking at a paragraph gap so entries aren't split
      // mid-sentence more than necessary.
      const gap = text.lastIndexOf('\n\n', end);
      if (gap > pos + max * 0.5) end = gap;
    }
    chunks.push(text.slice(pos, end));
    if (end >= text.length) break;
    // Step back so the next chunk re-covers the boundary region.
    pos = Math.max(end - CHUNK_OVERLAP, pos + 1);
  }
  return chunks;
}

// ── Image reading (downscale in-browser) ─────────────────────

async function readImageDownscaled(file: File): Promise<{ data: string; mediaType: string }> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error('unreadable image'));
      el.src = url;
    });
    const scale = Math.min(1, IMAGE_MAX_EDGE / Math.max(img.width, img.height));
    if (scale === 1 && (file.type === 'image/jpeg' || file.type === 'image/png')) {
      const data = await fileToBase64(file);
      return { data, mediaType: file.type };
    }
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext('2d')!.drawImage(img, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    return { data: dataUrl.split(',')[1], mediaType: 'image/jpeg' };
  } finally {
    URL.revokeObjectURL(url);
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(',')[1]);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

// ── Shared UI pieces ─────────────────────────────────────────

/** The "Source material" setup field: material list, add-files
 *  button, capacity hint. Same markup in both Scribe modes. */
export function ScribeMaterialsField({
  materials,
  onRemove,
  onAddFiles,
  extracting,
  children,
}: {
  materials: Material[];
  onRemove: (id: number) => void;
  onAddFiles: (files: FileList | null) => void;
  extracting: boolean;
  /** Extra intake UI (e.g. the entity mode's paste box). */
  children?: ReactNode;
}) {
  const totalChars = materials.reduce((n, m) => n + (m.charCount || 0), 0);
  return (
    <div className="scribe__field">
      <label>Source material</label>
      <div className="scribe__materials">
        {materials.map(m => (
          <div key={m.id} className="scribe__material">
            <span className="scribe__material-name">
              {m.kind === 'image' ? '🖼 ' : '📄 '}{m.filename}
            </span>
            {m.charCount != null && (
              <span className="scribe__material-meta">
                {Math.round(m.charCount / 1000)}k characters
              </span>
            )}
            <button
              className="scribe__material-remove"
              onClick={() => onRemove(m.id)}
              aria-label={`Remove ${m.filename}`}
            >×</button>
            {m.warning && <div className="scribe__warning">{m.warning}</div>}
          </div>
        ))}
      </div>
      <label className="scribe__file-btn">
        {extracting ? 'Reading…' : '+ Add files'}
        <input
          type="file"
          multiple
          accept=".epub,.pdf,.mobi,.azw,.azw3,.txt,.md,.html,.htm,.heic,.heif,image/*"
          onChange={e => { onAddFiles(e.target.files); e.target.value = ''; }}
          disabled={extracting}
          hidden
        />
      </label>
      <p className="scribe__hint">
        Books: EPUB, PDF, MOBI/AZW, or plain text. Photos of book
        pages work too (needs a vision-capable model).
        {totalChars > 0 && ` Loaded ${Math.round(totalChars / 1000)}k characters.`}
      </p>
      {children}
    </div>
  );
}

/** Chat input placeholders for the Scribe's ChatPanel. */
export const SCRIBE_CHAT_PLACEHOLDER =
  'Ask for corrections or changes… (Enter to send, Shift+Enter for a new line)';
export const SCRIBE_CHAT_BUSY_PLACEHOLDER =
  'Still working — messages sent now will guide the remaining parts…';
