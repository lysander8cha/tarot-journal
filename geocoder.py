"""
Local place-name geocoder backed by GeoNames cities500 (every place with
population >= 500). One-time download on first use (~7 MB zipped → ~30
MB unzipped), indexed into SQLite for instant lookups thereafter.

Architecture intentionally pluggable: `lookup()` is the public surface;
callers don't know whether a result came from the local index or a
future Nominatim fallback. To wire in a fallback later, build it as a
second Geocoder and call both in sequence (returning the local one when
non-empty).

Data licensed CC BY 4.0 by GeoNames (https://www.geonames.org/about.html).
"""

from __future__ import annotations

import io
import logging
import os
import re
import sqlite3
import threading
import zipfile
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Resolve the cache directory next to the project root so the data file
# lives alongside the app's other on-disk state. Avoids a separate
# user-config location to clean up later.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'geonames')
DB_PATH = os.path.join(DATA_DIR, 'cities500.db')
SOURCE_URL = 'https://download.geonames.org/export/dump/cities500.zip'
ADMIN1_URL = 'https://download.geonames.org/export/dump/admin1CodesASCII.txt'


@dataclass
class Match:
    name: str
    admin1: Optional[str]
    country: str
    latitude: float
    longitude: float
    population: int
    timezone: Optional[str]

    @property
    def display_name(self) -> str:
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ', '.join(parts)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'admin1': self.admin1,
            'country': self.country,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'population': self.population,
            'timezone': self.timezone,
            'display_name': self.display_name,
        }


# Single lazy build guard. The first request to lookup() triggers
# download + index build; subsequent requests hit the prebuilt DB.
_build_lock = threading.Lock()


def _normalize(s: str) -> str:
    """Lowercase + strip diacritics + collapse whitespace for matching.
    Cheap unicodedata-based fold; not Unicode-perfect but covers the
    common Latin/Latin-Extended cases that show up in city names."""
    import unicodedata
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = s.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _download_cities500() -> bytes:
    """Fetch cities500.zip from GeoNames. Returns the TSV bytes.

    Uses `requests` (bundled certifi) rather than urllib so we don't
    depend on macOS Python's flaky system CA chain.
    """
    import requests
    logger.info('Downloading GeoNames cities500.zip (~7 MB)...')
    resp = requests.get(
        SOURCE_URL,
        headers={'User-Agent': 'tarot-journal-app/1.0'},
        timeout=60,
    )
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open('cities500.txt') as fh:
            return fh.read()


def _download_admin1_names() -> dict[str, str]:
    """Fetch admin1CodesASCII.txt and parse into {<CC>.<code>: <name>}.

    Lets the picker display 'Bavaria' instead of '02', 'Wellington'
    instead of 'G2', etc. ~80 KB download.
    """
    import requests
    logger.info('Downloading GeoNames admin1CodesASCII.txt...')
    resp = requests.get(
        ADMIN1_URL,
        headers={'User-Agent': 'tarot-journal-app/1.0'},
        timeout=60,
    )
    resp.raise_for_status()
    out = {}
    for line in resp.text.splitlines():
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


def _build_index(tsv_bytes: bytes, admin1_names: dict[str, str], db_path: str):
    """Parse the GeoNames TSV and populate the local SQLite index."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    # Build into a temp DB then atomically rename, so a failed/partial
    # build doesn't leave a half-populated file behind.
    tmp_path = db_path + '.building'
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    conn = sqlite3.connect(tmp_path)
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE places (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            admin1 TEXT,
            country TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            population INTEGER DEFAULT 0,
            timezone TEXT
        );
        CREATE INDEX idx_places_name_norm ON places(name_norm);
        CREATE INDEX idx_places_population ON places(population DESC);

        -- Alternate names live in their own table so a single place can
        -- be found by any of its localized names without bloating the
        -- main row. Localized names from cities500 only cover well-
        -- known places; this is mostly UTF-8 forms of the same name.
        CREATE TABLE alt_names (
            place_id INTEGER NOT NULL,
            name_norm TEXT NOT NULL,
            FOREIGN KEY (place_id) REFERENCES places(id)
        );
        CREATE INDEX idx_alt_names_name_norm ON alt_names(name_norm);
    ''')

    rows = []
    alt_rows = []
    text = tsv_bytes.decode('utf-8', errors='replace')
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        cols = line.split('\t')
        if len(cols) < 19:
            continue
        gid = int(cols[0])
        name = cols[1]
        ascii_name = cols[2]
        alt_names = cols[3]
        try:
            lat = float(cols[4])
            lon = float(cols[5])
        except ValueError:
            continue
        country = cols[8]
        admin1_code = cols[10] or ''
        # Prefer the human-readable admin1 name (e.g. "Bavaria") over
        # the cryptic code ("02") when we have a mapping; fall back to
        # the code so the row still carries some location context.
        admin1 = admin1_names.get(f'{country}.{admin1_code}') or (admin1_code or None)
        try:
            population = int(cols[14]) if cols[14] else 0
        except ValueError:
            population = 0
        tz = cols[17] or None

        rows.append((
            gid, name, _normalize(ascii_name or name),
            admin1, country, lat, lon, population, tz,
        ))
        # Index ASCII + every alternate name so the lookup finds e.g.
        # "Münich" via "Munich" and "Москва" via "Moscow".
        seen = {_normalize(ascii_name or name)}
        for alt in (alt_names or '').split(','):
            norm = _normalize(alt)
            if norm and norm not in seen:
                seen.add(norm)
                alt_rows.append((gid, norm))

    cur.executemany(
        'INSERT INTO places (id, name, name_norm, admin1, country, '
        '                    latitude, longitude, population, timezone) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        rows
    )
    cur.executemany(
        'INSERT INTO alt_names (place_id, name_norm) VALUES (?, ?)',
        alt_rows,
    )
    conn.commit()
    conn.close()
    os.replace(tmp_path, db_path)
    logger.info('GeoNames index built: %d places, %d alternate names.',
                len(rows), len(alt_rows))


def _ensure_index_exists():
    """Ensure the SQLite index is on disk. Builds it if not."""
    if os.path.exists(DB_PATH):
        return
    with _build_lock:
        if os.path.exists(DB_PATH):
            return
        admin1_names = _download_admin1_names()
        tsv = _download_cities500()
        _build_index(tsv, admin1_names, DB_PATH)


def _open_db() -> sqlite3.Connection:
    _ensure_index_exists()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def lookup(query: str, limit: int = 10) -> list[dict]:
    """Look up places matching `query` (case/diacritic-insensitive).

    Match strategy, in order of precedence:
      1. Exact name match (highest population first).
      2. Prefix match on name.
      3. Substring match in name or alternate names.

    Returns a deduped list (by place id), capped at `limit`. Each entry
    is the dict produced by Match.to_dict().
    """
    norm = _normalize(query)
    if not norm:
        return []

    conn = _open_db()
    cur = conn.cursor()
    seen: set[int] = set()
    matches: list[Match] = []

    def _append(row: sqlite3.Row):
        if row['id'] in seen:
            return
        seen.add(row['id'])
        matches.append(Match(
            name=row['name'],
            admin1=row['admin1'],
            country=row['country'],
            latitude=row['latitude'],
            longitude=row['longitude'],
            population=row['population'],
            timezone=row['timezone'],
        ))

    # Ranking tiers, in order: exact name -> exact alt-name -> prefix ->
    # substring. Each tier sorted by population so the most-populated
    # match comes first. Alt-name exact match has to outrank prefix
    # otherwise queries in non-English forms (e.g. "München" for Munich)
    # get drowned out by tangentially-named neighbors (Münchenstein etc.).
    for sql, params in (
        (
            'SELECT * FROM places WHERE name_norm = ? '
            'ORDER BY population DESC LIMIT ?',
            (norm, limit),
        ),
        (
            'SELECT places.* FROM places '
            'JOIN alt_names ON alt_names.place_id = places.id '
            'WHERE alt_names.name_norm = ? '
            'ORDER BY places.population DESC LIMIT ?',
            (norm, limit),
        ),
        (
            'SELECT * FROM places WHERE name_norm LIKE ? AND name_norm != ? '
            'ORDER BY population DESC LIMIT ?',
            (norm + '%', norm, limit),
        ),
        (
            'SELECT * FROM places WHERE name_norm LIKE ? '
            'AND name_norm NOT LIKE ? AND name_norm != ? '
            'ORDER BY population DESC LIMIT ?',
            ('%' + norm + '%', norm + '%', norm, limit),
        ),
    ):
        for row in cur.execute(sql, params).fetchall():
            _append(row)
            if len(matches) >= limit:
                break
        if len(matches) >= limit:
            break

    conn.close()
    return [m.to_dict() for m in matches[:limit]]
