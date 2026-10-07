/**
 * One ordering for cartomancy-type lists across the settings pages:
 * the familiar built-ins first in their traditional order, then
 * everything else — Grand Jeu Lenormand, Oracle, any custom types the
 * user creates — alphabetically. Sections must never hardcode a type
 * list (new types have to show up everywhere automatically).
 */
import type { CartomancyType } from '../types';

const PREFERRED_ORDER = [
  'Tarot', 'Petit Lenormand', 'Playing Cards', 'Kipper', 'I Ching',
  'Playing Cards (Latin-suited)', 'Playing Cards (German-suited)', 'Oracle Belline',
  'Vera Sibilla Italiana / Sibilla della Zingara',
  'Sibylle des Salons / Sibilla Indovina',
];

export function orderTypeNames(names: string[]): string[] {
  const present = new Set(names);
  const rest = names
    .filter(n => !PREFERRED_ORDER.includes(n))
    .sort((a, b) => a.localeCompare(b));
  return [...PREFERRED_ORDER.filter(n => present.has(n)), ...rest];
}

export function orderTypes(types: CartomancyType[]): CartomancyType[] {
  const byName = new Map(types.map(t => [t.name, t]));
  return orderTypeNames(types.map(t => t.name)).map(n => byName.get(n)!);
}
