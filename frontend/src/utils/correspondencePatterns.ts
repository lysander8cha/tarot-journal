import type { CorrespondenceAssignment } from '../types';
import { CORRESPONDENCE_FIELDS, CORRESPONDENCE_FIELD_LABELS } from '../types';
import { getBulkCategories, type BulkGroup } from './bulkGroups';

export interface GroupPattern {
  groupLabel: string;
  fieldName: string;
  fieldLabel: string;
  value: string;
}

/** Detect group-level patterns from source_group-tagged assignments.
 *
 * Any source_group that has entries with consistent values across all its
 * members produces a pattern. Works for any custom group the user creates.
 */
export function detectGroupPatterns(
  assignments: CorrespondenceAssignment[],
): GroupPattern[] {
  // group -> field -> Map<archetype_id, value>
  const groupFieldValues = new Map<string, Map<string, Map<number, string>>>();

  for (const a of assignments) {
    if (!a.source_group) continue;
    if (!groupFieldValues.has(a.source_group)) {
      groupFieldValues.set(a.source_group, new Map());
    }
    const fieldMap = groupFieldValues.get(a.source_group)!;
    if (!fieldMap.has(a.field_name)) fieldMap.set(a.field_name, new Map());
    fieldMap.get(a.field_name)!.set(a.archetype_id, a.field_value);
  }

  const patterns: GroupPattern[] = [];

  for (const [groupLabel, fieldMap] of groupFieldValues) {
    for (const field of CORRESPONDENCE_FIELDS) {
      const entries = fieldMap.get(field);
      if (!entries || entries.size === 0) continue;
      const uniqueValues = new Set(entries.values());
      if (uniqueValues.size === 1) {
        patterns.push({
          groupLabel,
          fieldName: field,
          fieldLabel: CORRESPONDENCE_FIELD_LABELS[field],
          value: [...uniqueValues][0],
        });
      }
    }
  }

  return patterns;
}

/** Build a display structure grouped by category, then by group label. */
export interface PatternCategorySection {
  category: string;
  groups: { groupLabel: string; patterns: GroupPattern[] }[];
}

/** Section patterns by the deck type's own bulk groups (getBulkGroups),
 *  so every type's suits and ranks land in its Suits/Ranks sections in
 *  their usual order. Labels the type doesn't know (custom groups the
 *  user created) go under "Other". */
export function patternsByCategory(
  patterns: GroupPattern[],
  groups: BulkGroup[],
): PatternCategorySection[] {
  const byLabel = new Map<string, GroupPattern[]>();
  for (const p of patterns) {
    if (!byLabel.has(p.groupLabel)) byLabel.set(p.groupLabel, []);
    byLabel.get(p.groupLabel)!.push(p);
  }

  const sections: PatternCategorySection[] = [];
  for (const category of getBulkCategories(groups)) {
    const found = groups
      .filter(g => g.category === category && byLabel.has(g.label))
      .map(g => ({ groupLabel: g.label, patterns: byLabel.get(g.label)! }));
    if (found.length > 0) sections.push({ category, groups: found });
  }

  const known = new Set(groups.map(g => g.label));
  const other = [...byLabel.keys()]
    .filter(label => !known.has(label))
    .sort()
    .map(label => ({ groupLabel: label, patterns: byLabel.get(label)! }));
  if (other.length > 0) sections.push({ category: 'Other', groups: other });

  return sections;
}
