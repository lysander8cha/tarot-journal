import api from './client';

// === Birth cards (Greer "Lifetime Cards") ===

export type BirthCardMethod = 'greer' | 'amberstone';
export type EightEleven = 'golden_dawn' | 'marseille';
export type CourtSystem = 'golden_dawn' | 'golden_dawn_waite' | 'bota';

/** A Major Arcana reference, hydrated by the backend. */
export interface MajorCardRef {
  /** 1–22; The Fool is 22 internally (displayed as 0 by convention). */
  number: number;
  name: string;
  archetype_id: number | null;
  /** Matching card in the default Tarot deck, for the image. */
  card_id: number | null;
}

/** A Minor Arcana reference (decan / lessons cards). */
export interface MinorCardRef {
  rank: number;
  suit: string;
  name: string;
  archetype_id: number | null;
  card_id: number | null;
}

export interface BirthCardProfile {
  method: BirthCardMethod;
  base_number: number;
  personality: number;
  soul: number;
  teacher: number | null;
  hidden_factor: number[];
  pattern: string;
  nighttime: boolean;
  fool_center: boolean;
  constellation: { root: number; majors: number[] };
  dynamic: 1 | 2 | 3 | null;
  /** Golden Dawn decan attributions for the zodiacal card. */
  zodiacal_rulers: {
    sign: string;
    planet: string;
    sign_major: number;
    planet_major: number;
  };
  /** Court card ruling the birth decan's 20°–20° span. */
  decan_court: {
    rank: string;
    suit: string;
    name: string;
    court_sign: string;
    span: string;
  };
  court_system: CourtSystem;
  /** Year Card per year, birth year through ~10 years ahead. */
  year_series: { year: number; card: number }[];
  majors_by_number: Record<string, MajorCardRef>;
  karmic_year: number;
  year_card: number;
  generic_year: number;
  personal_month: number;
  birth_date: string;
  age: number;
  eight_eleven: EightEleven;
  reference_year: number;
  reference_month: number;
  cards: {
    personality: MajorCardRef;
    soul: MajorCardRef;
    teacher: MajorCardRef | null;
    hidden_factor: MajorCardRef[];
    constellation_majors: MajorCardRef[];
    lessons_and_opportunities: MinorCardRef[];
    zodiacal: MinorCardRef;
    zodiacal_sign_ruler: MajorCardRef;
    zodiacal_planet_ruler: MajorCardRef;
    decan_court: {
      rank: string;
      suit: string;
      name: string;
      archetype_id: number | null;
      card_id: number | null;
    };
    year_card: MajorCardRef;
    generic_year: MajorCardRef;
    personal_month: MajorCardRef;
  };
}

export interface BirthCardPrefs {
  method: BirthCardMethod;
  eight_eleven: EightEleven;
  court_system: CourtSystem;
}

interface BirthCardOpts {
  method?: BirthCardMethod;
  eightEleven?: EightEleven;
  courtSystem?: CourtSystem;
  /** Reference year for the Year Card (defaults server-side to today). */
  year?: number;
}

function optsToParams(opts?: BirthCardOpts): URLSearchParams {
  const params = new URLSearchParams();
  if (opts?.method) params.set('method', opts.method);
  if (opts?.eightEleven) params.set('eight_eleven', opts.eightEleven);
  if (opts?.courtSystem) params.set('court_system', opts.courtSystem);
  if (opts?.year) params.set('year', String(opts.year));
  return params;
}

export async function getProfileBirthCards(
  profileId: number,
  opts?: BirthCardOpts,
): Promise<BirthCardProfile> {
  const qs = optsToParams(opts).toString();
  const res = await api.get(`/api/profiles/${profileId}/birth-cards${qs ? `?${qs}` : ''}`);
  return res.data;
}

export async function setBirthCardPrefs(
  prefs: Partial<BirthCardPrefs>,
): Promise<BirthCardPrefs> {
  const res = await api.put('/api/birth-cards/prefs', prefs);
  return res.data;
}
