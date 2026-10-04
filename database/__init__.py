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
from .correspondences import CorrespondencesMixin
from .reference_sources import ReferenceSourcesMixin
from .combinations import CombinationsMixin
from .archetype_languages import ArchetypeLanguagesMixin
from .archetype_source_entries import ArchetypeSourceEntriesMixin
from .entity_notes import EntityNotesMixin
from .charts import ChartsMixin
from .prompt_presets import PromptPresetsMixin


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
    CorrespondencesMixin,
    ReferenceSourcesMixin,
    CombinationsMixin,
    ArchetypeLanguagesMixin,
    ArchetypeSourceEntriesMixin,
    EntityNotesMixin,
    ChartsMixin,
    PromptPresetsMixin,
):
    """Main database class: one mixin per domain (decks, cards, entries, ...)."""

