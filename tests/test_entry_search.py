"""Entry search filters: querent and date-range behavior."""


def test_search_by_querent(db):
    alice = db.add_profile("Alice")
    bob = db.add_profile("Bob")
    e1 = db.add_entry(title="Alice's reading")
    e2 = db.add_entry(title="Bob's reading")
    db.set_entry_querents(e1, [alice])
    db.set_entry_querents(e2, [bob])

    results = db.search_entries(querent_id=alice)
    titles = [r["title"] for r in results]
    assert titles == ["Alice's reading"]


def test_date_to_includes_the_end_date(db):
    """Regression: `<= date_to` string-compare excluded everything on
    the end date itself, because '2026-07-02T10:00' sorts after
    '2026-07-02'."""
    db.add_entry(title="on the end date", reading_datetime="2026-07-02T10:00:00")
    db.add_entry(title="day after", reading_datetime="2026-07-03T09:00:00")

    results = db.search_entries(date_from="2026-07-01", date_to="2026-07-02")
    titles = [r["title"] for r in results]
    assert titles == ["on the end date"]


def test_date_filter_uses_reading_datetime_not_created_at(db):
    """An entry logged today about a reading last month must match a
    search for last month's dates."""
    db.add_entry(title="backdated reading", reading_datetime="2026-06-01T20:00:00")

    results = db.search_entries(date_from="2026-05-30", date_to="2026-06-02")
    assert [r["title"] for r in results] == ["backdated reading"]
    # ...and not match a search for the (current) creation date window
    results_now = db.search_entries(date_from="2026-07-01", date_to="2026-12-31")
    assert "backdated reading" not in [r["title"] for r in results_now]


def test_entries_sort_by_reading_vs_created(db):
    """An entry logged today about an old reading sorts first by
    creation but last by reading date."""
    a = db.add_entry(title="old reading, logged now",
                     reading_datetime="2026-01-05T10:00:00")
    b = db.add_entry(title="recent reading, logged earlier",
                     reading_datetime="2026-07-01T10:00:00")
    # Make creation order unambiguous: a created after b
    db.conn.execute("UPDATE journal_entries SET created_at='2026-07-08T12:00:00' WHERE id=?", (a,))
    db.conn.execute("UPDATE journal_entries SET created_at='2026-07-02T12:00:00' WHERE id=?", (b,))
    db.conn.commit()

    by_reading = [r["title"] for r in db.get_entries(sort_by="reading")]
    by_created = [r["title"] for r in db.get_entries(sort_by="created")]
    assert by_reading == ["recent reading, logged earlier", "old reading, logged now"]
    assert by_created == ["old reading, logged now", "recent reading, logged earlier"]

    # search honors the same sort switch
    s_reading = [r["title"] for r in db.search_entries(query="reading", sort_by="reading")]
    s_created = [r["title"] for r in db.search_entries(query="reading", sort_by="created")]
    assert s_reading == by_reading
    assert s_created == by_created


def test_recent_locations_dedupe_and_order(db):
    """The entry editor's recent-location chips: distinct names,
    most recently used first, coordinates from the latest use."""
    db.add_entry(title="a", reading_datetime="2026-09-01T10:00:00",
                 location_name="Home", location_lat=1.0, location_lon=2.0)
    db.add_entry(title="b", reading_datetime="2026-09-05T10:00:00",
                 location_name="Cafe", location_lat=3.0, location_lon=4.0)
    db.add_entry(title="c", reading_datetime="2026-09-10T10:00:00",
                 location_name="Home", location_lat=5.0, location_lon=6.0)
    db.add_entry(title="no location")
    db.add_entry(title="blank location", location_name="   ")

    rows = db.get_recent_locations()
    names = [r["location_name"] for r in rows]
    assert names == ["Home", "Cafe"]
    # Coordinates come from the most recent visit to each place.
    assert rows[0]["location_lat"] == 5.0
    assert rows[0]["location_lon"] == 6.0


def test_recent_locations_respects_limit(db):
    for i in range(10):
        db.add_entry(title=f"e{i}",
                     reading_datetime=f"2026-09-{i + 1:02d}T10:00:00",
                     location_name=f"Place {i}")
    rows = db.get_recent_locations(limit=3)
    assert [r["location_name"] for r in rows] == [
        "Place 9", "Place 8", "Place 7"]
