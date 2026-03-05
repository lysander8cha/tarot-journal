"""
Database package for Tarot Journal App.

Combines all database mixins into the main Database class.
"""

from .core import CoreMixin
from .decks import DecksMixin
from .cards import CardsMixin
from .card_groups import CardGroupsMixin
from .tags import TagsMixin
from .entries import EntriesMixin
from .profiles import ProfilesMixin
from .settings import SettingsMixin
from .import_export import ImportExportMixin


class Database(
    CoreMixin,
    DecksMixin,
    CardsMixin,
    CardGroupsMixin,
    TagsMixin,
    EntriesMixin,
    ProfilesMixin,
    SettingsMixin,
    ImportExportMixin,
):
    """
    Main database class combining all functionality.

    This class inherits from multiple mixins, each handling a specific
    domain of database operations:

    - CoreMixin: Initialization, table creation, transactions
    - DecksMixin: Deck and cartomancy type operations
    - CardsMixin: Card CRUD, archetypes, metadata
    - CardGroupsMixin: Card grouping operations
    - TagsMixin: Tags for entries, decks, and cards
    - EntriesMixin: Journal entries, spreads, readings
    - ProfilesMixin: Querent/reader profiles
    - SettingsMixin: Application settings and statistics
    - ImportExportMixin: Import/export and backup/restore
    """
    pass


def create_default_spreads(db: Database):
    """Create some common tarot and lenormand spreads"""
    spreads = db.get_spreads()
    if len(spreads) == 0:
        # Card dimensions matching the spread designer defaults,
        # snapped to the 20px grid
        cw, ch = 80, 120

        # === TAROT SPREADS ===

        # Single card
        db.add_spread(
            "Daily Draw",
            [
                {"x": 200, "y": 80, "label": "Card of the Day", "width": cw, "height": ch}
            ],
            "A single card for daily reflection",
            "Tarot"
        )

        # Three card spread (line) — 20px gaps between cards
        db.add_spread(
            "Three Card Line",
            [
                {"x": 60, "y": 80, "label": "Past", "width": cw, "height": ch},
                {"x": 160, "y": 80, "label": "Present", "width": cw, "height": ch},
                {"x": 260, "y": 80, "label": "Future", "width": cw, "height": ch}
            ],
            "A simple past-present-future reading",
            "Tarot"
        )

        # Five card spread (line) — 20px gaps between cards
        db.add_spread(
            "Five Card Line",
            [
                {"x": 20, "y": 80, "label": "1", "width": cw, "height": ch},
                {"x": 120, "y": 80, "label": "2", "width": cw, "height": ch},
                {"x": 220, "y": 80, "label": "3", "width": cw, "height": ch},
                {"x": 320, "y": 80, "label": "4", "width": cw, "height": ch},
                {"x": 420, "y": 80, "label": "5", "width": cw, "height": ch}
            ],
            "A five card layout",
            "Tarot"
        )

        # Celtic Cross (10 card)
        db.add_spread(
            "Celtic Cross",
            [
                {"x": 160, "y": 180, "label": "1. Present", "width": cw, "height": ch},
                {"x": 160, "y": 180, "label": "2. Challenge", "width": cw, "height": ch, "rotation": 90},
                {"x": 160, "y": 40, "label": "3. Above", "width": cw, "height": ch},
                {"x": 160, "y": 320, "label": "4. Below", "width": cw, "height": ch},
                {"x": 60, "y": 180, "label": "5. Past", "width": cw, "height": ch},
                {"x": 260, "y": 180, "label": "6. Future", "width": cw, "height": ch},
                {"x": 380, "y": 360, "label": "7. Self", "width": cw, "height": ch},
                {"x": 380, "y": 240, "label": "8. Environment", "width": cw, "height": ch},
                {"x": 380, "y": 120, "label": "9. Hopes/Fears", "width": cw, "height": ch},
                {"x": 380, "y": 0, "label": "10. Outcome", "width": cw, "height": ch}
            ],
            "The classic 10-card Celtic Cross spread",
            "Tarot"
        )

        # === LENORMAND SPREADS ===

        # Lenormand 3-card — 20px gaps
        db.add_spread(
            "Lenormand Line of 3",
            [
                {"x": 60, "y": 80, "label": "1", "width": cw, "height": ch},
                {"x": 160, "y": 80, "label": "2", "width": cw, "height": ch},
                {"x": 260, "y": 80, "label": "3", "width": cw, "height": ch}
            ],
            "A simple Lenormand three-card line",
            "Lenormand"
        )

        # Lenormand 5-card — 20px gaps
        db.add_spread(
            "Lenormand Line of 5",
            [
                {"x": 20, "y": 80, "label": "1", "width": cw, "height": ch},
                {"x": 120, "y": 80, "label": "2", "width": cw, "height": ch},
                {"x": 220, "y": 80, "label": "3", "width": cw, "height": ch},
                {"x": 320, "y": 80, "label": "4", "width": cw, "height": ch},
                {"x": 420, "y": 80, "label": "5", "width": cw, "height": ch}
            ],
            "A five-card Lenormand line",
            "Lenormand"
        )

        # Lenormand 9-card (3x3) — 20px gaps
        db.add_spread(
            "Lenormand Box of 9",
            [
                {"x": 60, "y": 20, "label": "1", "width": cw, "height": ch},
                {"x": 160, "y": 20, "label": "2", "width": cw, "height": ch},
                {"x": 260, "y": 20, "label": "3", "width": cw, "height": ch},
                {"x": 60, "y": 160, "label": "4", "width": cw, "height": ch},
                {"x": 160, "y": 160, "label": "5", "width": cw, "height": ch},
                {"x": 260, "y": 160, "label": "6", "width": cw, "height": ch},
                {"x": 60, "y": 300, "label": "7", "width": cw, "height": ch},
                {"x": 160, "y": 300, "label": "8", "width": cw, "height": ch},
                {"x": 260, "y": 300, "label": "9", "width": cw, "height": ch}
            ],
            "A 3x3 Lenormand grid with card 5 as significator",
            "Lenormand"
        )


def create_default_decks(db: Database):
    """Placeholder for creating default decks (not currently implemented)."""
    pass
