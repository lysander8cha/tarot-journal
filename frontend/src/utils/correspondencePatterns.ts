import type { CorrespondenceAssignment } from '../types';
import { CORRESPONDENCE_FIELDS, CORRESPONDENCE_FIELD_LABELS } from '../types';

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

// Canonical categories and their group labels — must match BULK_GROUPS in
// CorrespondencesSection for consistent display ordering.
export const GROUP_CATEGORIES: { name: string; labels: string[] }[] = [
  { name: 'Card Type', labels: ['Major Arcana', 'Minor Arcana'] },
  { name: 'Suits', labels: ['Wands', 'Cups', 'Swords', 'Pentacles'] },
  {
    name: 'Court Ranks',
    labels: ['Pages', 'Knights', 'Queens', 'Kings', 'Court Cards'],
  },
  {
    name: 'Pip Numbers',
    labels: [
      'Aces', 'Twos', 'Threes', 'Fours', 'Fives',
      'Sixes', 'Sevens', 'Eights', 'Nines', 'Tens',
      'Pips (Ace-10)',
    ],
  },
];

/** Group patterns by card-group label for display, sorted by canonical order. */
export function groupPatternsByGroup(patterns: GroupPattern[]): Map<string, GroupPattern[]> {
  const unordered = new Map<string, GroupPattern[]>();
  for (const p of patterns) {
    if (!unordered.has(p.groupLabel)) unordered.set(p.groupLabel, []);
    unordered.get(p.groupLabel)!.push(p);
  }

  const ordered = new Map<string, GroupPattern[]>();
  for (const cat of GROUP_CATEGORIES) {
    for (const label of cat.labels) {
      if (unordered.has(label)) {
        ordered.set(label, unordered.get(label)!);
        unordered.delete(label);
      }
    }
  }
  // Remaining custom labels — sort alphabetically
  const remaining = [...unordered.keys()].sort();
  for (const label of remaining) {
    ordered.set(label, unordered.get(label)!);
  }
  return ordered;
}

/** Build a display structure grouped by category, then by group label. */
export interface PatternCategorySection {
  category: string;
  groups: { groupLabel: string; patterns: GroupPattern[] }[];
}

export function patternsByCategory(patterns: GroupPattern[]): PatternCategorySection[] {
  const byGroup = groupPatternsByGroup(patterns);
  const sections: PatternCategorySection[] = [];

  // Map each label to its category
  const labelToCategory = new Map<string, string>();
  for (const cat of GROUP_CATEGORIES) {
    for (const label of cat.labels) labelToCategory.set(label, cat.name);
  }

  // Build each known category section
  for (const cat of GROUP_CATEGORIES) {
    const groups: { groupLabel: string; patterns: GroupPattern[] }[] = [];
    for (const label of cat.labels) {
      if (byGroup.has(label)) {
        groups.push({ groupLabel: label, patterns: byGroup.get(label)! });
      }
    }
    if (groups.length > 0) {
      sections.push({ category: cat.name, groups });
    }
  }

  // Any labels not in known categories → "Other"
  const otherGroups: { groupLabel: string; patterns: GroupPattern[] }[] = [];
  for (const [label, pats] of byGroup) {
    if (!labelToCategory.has(label)) {
      otherGroups.push({ groupLabel: label, patterns: pats });
    }
  }
  if (otherGroups.length > 0) {
    sections.push({ category: 'Other', groups: otherGroups });
  }

  return sections;
}
