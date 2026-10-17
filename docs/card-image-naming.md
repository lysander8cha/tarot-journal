# Card image filenames for Tarot Journal import presets

How to name card image files so a deck folder imports cleanly. Each
built-in import preset (`import_presets.py`) recognises the names below.
Pick the preset that matches the deck, then rename the files to its scheme.

## How matching works
- The importer takes the filename without its extension, lowercases it,
  and removes spaces, underscores, hyphens and dots, then looks it up in
  the preset. If that fails it tries, in order: the name with leading
  digits removed (`22_ace_of_wands` → `aceofwands`), then the last
  number in the name (`PLen-A-01` → `01`).
- Zero-padding is optional: `w01` and `w1` both work.
- Every preset also accepts the full card name without spaces
  (`aceofwands`, `sotadeoros`). The short schemes below are preferred.
- Back images: name them `back`, `cardback`, `card_back`, `cover`,
  `reverse`, `verso` or `00_back`; they become the deck's back, not a card.
- The import dialog's preview shows each file's card name and archetype.
  A file that didn't match keeps its cleaned-up filename and has no
  archetype, so check the preview for those.

## Tarot
**Tarot (RWS Ordering)**
- Majors: `00` The Fool … `21` The World (08 Strength, 11 Justice).
- Minors: suit letter + rank `01`–`14` — `w` Wands, `c` Cups,
  `s` Swords, `p` Pentacles; 01 Ace … 10, 11 Page, 12 Knight,
  13 Queen, 14 King. Example: `c11` = Page of Cups.

**Tarot (Pre-Golden Dawn Ordering)** — as RWS, but 08 Justice, 11 Strength.

**Tarot (Thoth)** — same numbers with Thoth titles (08 Adjustment,
11 Lust, 14 Art, 20 The Aeon, 21 The Universe). `p` = Disks. Courts:
11 Princess, 12 Prince, 13 Queen, 14 Knight.

**Tarot (Gnostic/Eternal)** — `01`–`78` in the deck's own order
(01 The Magician … 78 Renaissance). No 00.

**Grand Etteilla Tarot** — `00`–`21` for its first 22 cards
(00 Chaos, 01 Hiram's Freemasonry…); the rest match by card name only.

## Lenormand family
**Lenormand (36 cards)** — `01` Rider … `36` Cross.

**Grand Lenormand (54 cards)** — playing-card cards by suit letter +
rank `01`–`13` (`h` Hearts, `d` Diamonds, `c` Clubs, `s` Spades;
11 Jack, 12 Queen, 13 King), e.g. `h13` = King of Hearts. Consultants:
`53` Man, `54` Woman (or `man` / `woman`).

**Kipper (36 cards)** — `01` Main Male … `36` Hope, Great Water.

## Oracles
**Oracle Belline** — `01` Destiny … `53` Blue Card.

**I Ching (64 Hexagrams)** — `01`–`64` hexagrams (King Wen order);
`t1`–`t8` trigrams (Heaven, Earth, Thunder, Water, Mountain, Wind,
Fire, Lake).

**Oracle (filename only)** — no mapping: the cleaned-up filename becomes
the card name, so name files after the cards (use the number printed on
the card if there is one).

## Sibilla family (52 cards, playing-card based)
**Vera Sibilla Italiana / Sibilla della Zingara** — suit letter + rank
`01`–`13` (`h`, `c`, `d`, `s`; 01 Ace … 13 King), e.g. `h13` =
Gentleman. A running number `01`–`52` also works, ordered Hearts,
Clubs, Diamonds, Spades, each Ace → King.

**Sibylle des Salons / Sibilla Indovina** — suit letter + rank as above,
e.g. `c13` = Protector. Its running number `01`–`52` is ordered
differently: Clubs, Diamonds, Hearts, Spades, each **King → Ace**.

## French-suited playing cards
**Playing Cards (52 cards)** — suit letter + rank `01`–`13`: `h`
Hearts, `d` Diamonds, `c` Clubs, `s` Spades; 11 Jack, 12 Queen,
13 King. Example: `s13` = King of Spades. Two-letter forms also work
(`ah`, `ks`, `jd`). There is no running-number scheme.

**Playing Cards with Jokers (54 cards)** — as above, plus jokers:
`j1` Red Joker, `j2` Black Joker (also `jr`/`jb`, `joker1`/`joker2`).

## Regional playing cards
Card names come out in the deck's own language; the number is the one
**printed on the card**. Each also accepts a running number `01`, `02`…
in suit order, and the native suit word as prefix (`oros10`, `schilten12`).

| Preset | Suit letters | Ranks (printed number) | Example |
|---|---|---|---|
| Spanish (50 cards) | `o` Oros, `c` Copas, `e` Espadas, `b` Bastos | 1–9, 10 Sota, 11 Caballo, 12 Rey; jokers `j1`/`j2` (Comodín) | `o10` = Sota de Oros |
| Spanish (40 cards) | same | 1–7, 10 Sota, 11 Caballo, 12 Rey | `c12` = Rey de Copas |
| Italian (40 cards) | `d` Denari, `c` Coppe, `s` Spade, `b` Bastoni | 1–7, **8 Fante, 9 Cavallo, 10 Re** | `d08` = Fante di Denari |
| German (32 cards) | `h` Herz, `b` Schellen, `l` Laub, `a` Eichel (also `s`, `g`, `e`) | 7–10, 11 Unter, 12 Ober, 13 König, Ass `01` or `14`; Weli `w` | `a12` = Eichel Ober |
| German (36 cards) | same | 6–10, rest as German 32 | `b06` = Schellen Sechs |
| German (52 cards, 2–Ace) | same | 2–10, rest as German 32 | `b02` = Schellen Zwei |
| Swiss (36 cards) | `r` Rosen, `b` Schellen, `s` Schilten, `a` Eicheln | 6–9, 10 Banner, 11 Under, 12 Ober, 13 König, Ass `01` or `14` | `s10` = Schilten Banner |

Watch out for: Italian courts are 8–10, not 10–12 as in Spanish packs.
A 24-card German pack imports fine with the 32-card preset (missing
cards are simply absent). German-suited cards already named after the
English archetype (`Two of Bells`) also link, whatever the preset.
