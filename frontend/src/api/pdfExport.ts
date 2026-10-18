import api from './client';

export interface PdfExportOptions {
  readings?: number[];
  include_correspondences?: boolean;
  /** Row keys to include in the breakdown — same vocabulary as the
   *  Reading Breakdown's filter checklist (suit, rank, element, …). */
  correspondence_types?: string[];
  include_custom_fields?: boolean;
  /** Field names to keep in the Card Detail Section (case-insensitive
   *  match on the server). Omit to include every field present. */
  custom_fields?: string[];
  include_archetype_fields?: boolean;
  /** source_fields.id values to keep, taken from the export-options
   *  archetype_fields list. Omit to include every authored entry. */
  archetype_fields?: number[];
  /** Reserved for phase 4. */
  include_chart?: boolean;
  /** Render each reading's spread description under its layout. */
  include_spread_instructions?: boolean;
  /** Suit row display in the breakdown: each tradition's names, or
   *  Latin/French equivalents merged ("Cups / Hearts"). */
  suit_view?: 'separate' | 'paired';
  /** Tarot cards to mark as the querents' birth/name cards: lowercase
   *  canonical archetype name → role label + frame colors. */
  card_marks?: Record<string, { label: string; colors: string[] }>;
}

export interface ArchetypeFieldOption {
  field_id: number;
  source_id: number;
  source_name: string;
  field_name: string;
}

/** Lists the custom fields + archetype reference fields available on
 *  the selected readings, so the modal can show only the relevant
 *  checkboxes. `chart_available` is true when the entry has the
 *  reading_datetime + lat/lon needed to generate an event chart. */
export interface PdfExportOptionsDiscovery {
  custom_fields: string[];
  archetype_fields: ArchetypeFieldOption[];
  chart_available: boolean;
}

/**
 * Fetch which custom/archetype fields exist on the entry (filtered
 * to the selected readings), used by the modal to populate its
 * sub-checklists.
 */
export async function getExportOptions(
  entryId: number,
  readings?: number[],
): Promise<PdfExportOptionsDiscovery> {
  const params = new URLSearchParams();
  for (const id of readings || []) params.append('readings', String(id));
  const res = await api.get(
    `/api/entries/${entryId}/export-options${params.toString() ? `?${params}` : ''}`,
  );
  return res.data;
}

/**
 * Trigger a PDF download for the given entry. The browser handles
 * the actual save via a temporary `<a download>` link; the server
 * sends a Content-Disposition with the suggested filename, but
 * since axios+blob downloads strip headers we surface the filename
 * inline from the JSON response if the request fails, or extract
 * it from Content-Disposition when the response is binary.
 */
export async function exportEntryPdf(
  entryId: number,
  options: PdfExportOptions = {},
): Promise<void> {
  const res = await api.post(`/api/entries/${entryId}/export-pdf`, options, {
    responseType: 'blob',
  });

  // Extract filename from Content-Disposition if present.
  let filename = `journal_entry_${entryId}.pdf`;
  const cd =
    res.headers['content-disposition'] ||
    (res.headers as Record<string, string>)['Content-Disposition'];
  if (cd) {
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
    if (match && match[1]) filename = decodeURIComponent(match[1]);
  }

  // Trigger a download.
  const blob = new Blob([res.data], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// === Profile PDF export ===

export interface ProfilePdfOptions {
  include_chart?: boolean;
  include_birth_cards?: boolean;
  /** Which addition methods to include: greer, amberstone, or both. */
  birth_card_methods?: ('greer' | 'amberstone')[];
  include_name_cards?: boolean;
}

/** Same blob-download flow as entry PDFs. */
export async function exportProfilePdf(
  profileId: number,
  options: ProfilePdfOptions,
): Promise<void> {
  const res = await api.post(`/api/profiles/${profileId}/export-pdf`, options, {
    responseType: 'blob',
  });

  let filename = `profile_${profileId}.pdf`;
  const cd =
    res.headers['content-disposition'] ||
    (res.headers as Record<string, string>)['Content-Disposition'];
  if (cd) {
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
    if (match && match[1]) filename = decodeURIComponent(match[1]);
  }

  const blob = new Blob([res.data], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
