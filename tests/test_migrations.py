"""Startup migrations against legacy data shapes."""
import json

from conftest import make_deck_with_card

from database.correspondence_migration import run_correspondence_migration


def _clear_migration_flag(db):
    db.conn.execute(
        "UPDATE settings SET value='' WHERE key='correspondence_migration_done'")
    db.conn.commit()


def test_correspondence_migration_handles_legacy_fields(db):
    """Opening a pre-migration database (e.g. a restored old backup)
    with legacy Astrology/Element custom fields must migrate them, not
    crash at startup (regression test for the ON CONFLICT mismatch)."""
    _, card_id = make_deck_with_card(db)
    for name, value in (("Element", "Fire"), ("Astrology", "Aries")):
        db.conn.execute(
            "INSERT INTO card_custom_fields (card_id, field_name, field_value, field_type)"
            " VALUES (?, ?, ?, 'text')",
            (card_id, name, value))
    db.conn.commit()

    _clear_migration_flag(db)
    run_correspondence_migration(db)

    rows = {(r["field_name"], r["field_value"]) for r in db.conn.execute(
        "SELECT field_name, field_value FROM card_correspondence_overrides"
        " WHERE card_id=?", (card_id,)).fetchall()}
    assert ("element", "Fire") in rows
    assert ("zodiac_sign", "Aries") in rows

    # Re-running (e.g. flag lost) must not error or duplicate rows.
    count_before = len(rows)
    _clear_migration_flag(db)
    run_correspondence_migration(db)
    count_after = db.conn.execute(
        "SELECT COUNT(*) FROM card_correspondence_overrides WHERE card_id=?",
        (card_id,)).fetchone()[0]
    assert count_after == count_before


def test_lenormand_reference_repair(tmp_path):
    """The historical Lenormand → Petit Lenormand rename missed
    spreads' JSON columns and entry_readings; the repair migration
    fixes them on reopen, with exact matching (Grand Jeu untouched)."""
    from database import Database

    path = str(tmp_path / "repair.db")
    db = Database(db_path=path)
    cur = db.conn.cursor()
    # Plant stale references the way the pre-rename app wrote them
    cur.execute(
        "INSERT INTO spreads (name, positions, allowed_deck_types, deck_slots) "
        "VALUES ('ZZ Stale', '[]', "
        "'[\"Lenormand\", \"Grand Jeu Lenormand\"]', "
        "'[{\"key\": \"A\", \"cartomancy_type\": \"Lenormand\"}]')")
    entry_id = db.add_entry(title='ZZ Repair')
    cur.execute(
        "UPDATE entry_readings SET cartomancy_type = 'Lenormand' WHERE 0")
    db.add_entry_reading(entry_id, deck_id=None, cards_used=[],
                         cartomancy_type='Lenormand')
    cur.execute("INSERT INTO reference_sources (name) VALUES ('ZZ Src')")
    src_id = cur.lastrowid
    cur.execute(
        "INSERT INTO entity_source_notes "
        "(entity_kind, entity_key, source_id, content, updated_at) "
        "VALUES ('suit', 'Lenormand::Clubs', ?, 'x', '2026-01-01')",
        (src_id,))
    # Reset the flag so the repair reruns on next open
    db.set_setting('petit_lenormand_reference_repair_done', 'false')
    db.conn.commit()
    db.close()

    db2 = Database(db_path=path)
    cur = db2.conn.cursor()
    row = cur.execute(
        "SELECT allowed_deck_types, deck_slots FROM spreads "
        "WHERE name = 'ZZ Stale'").fetchone()
    assert json.loads(row['allowed_deck_types']) == [
        'Petit Lenormand', 'Grand Jeu Lenormand']
    assert json.loads(row['deck_slots'])[0]['cartomancy_type'] == 'Petit Lenormand'
    assert cur.execute(
        "SELECT COUNT(*) FROM entry_readings WHERE cartomancy_type = 'Lenormand'"
    ).fetchone()[0] == 0
    assert cur.execute(
        "SELECT COUNT(*) FROM entity_source_notes "
        "WHERE entity_key = 'Petit Lenormand::Clubs'").fetchone()[0] == 1
    db2.close()


def test_rename_cartomancy_type_covers_json_references(db):
    """Future renames rewrite spreads' JSON and entity keys too."""
    type_id = db.add_cartomancy_type('ZZ Oldname')
    cur = db.conn.cursor()
    cur.execute(
        "INSERT INTO spreads (name, positions, allowed_deck_types, deck_slots) "
        "VALUES ('ZZ Renamer', '[]', '[\"ZZ Oldname\"]', "
        "'[{\"key\": \"A\", \"cartomancy_type\": \"ZZ Oldname\"}]')")
    cur.execute("INSERT INTO reference_sources (name) VALUES ('ZZ Src2')")
    src_id = cur.lastrowid
    cur.execute(
        "INSERT INTO entity_source_notes "
        "(entity_kind, entity_key, source_id, content, updated_at) "
        "VALUES ('rank', 'ZZ Oldname::Ace', ?, 'x', '2026-01-01')",
        (src_id,))
    db.conn.commit()

    db.rename_cartomancy_type(type_id, 'ZZ Newname')

    row = cur.execute(
        "SELECT allowed_deck_types, deck_slots FROM spreads "
        "WHERE name = 'ZZ Renamer'").fetchone()
    assert json.loads(row['allowed_deck_types']) == ['ZZ Newname']
    assert json.loads(row['deck_slots'])[0]['cartomancy_type'] == 'ZZ Newname'
    assert cur.execute(
        "SELECT COUNT(*) FROM entity_source_notes "
        "WHERE entity_key = 'ZZ Newname::Ace'").fetchone()[0] == 1
