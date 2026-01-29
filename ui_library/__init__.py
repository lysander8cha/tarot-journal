"""
UI Library package for the Tarot Journal App.

Combines all library panel mixins into the main LibraryMixin class.
This handles the deck list, card display, search, and CRUD operations.
"""

from .panel import LibraryPanelMixin
from .deck_list import DeckListMixin
from .card_display import CardDisplayMixin
from .card_sorting import CardSortingMixin
from .card_search import CardSearchMixin
from .card_groups import CardGroupsMixin
from .deck_dialogs import DeckDialogsMixin
from .import_export import ImportExportMixin
from .card_crud import CardCrudMixin


class LibraryMixin(
    LibraryPanelMixin,
    DeckListMixin,
    CardDisplayMixin,
    CardSortingMixin,
    CardSearchMixin,
    CardGroupsMixin,
    DeckDialogsMixin,
    ImportExportMixin,
    CardCrudMixin,
):
    """
    Main library mixin combining all functionality.

    This class inherits from multiple mixins, each handling a specific
    domain of library operations:

    - LibraryPanelMixin: Main panel creation and layout
    - DeckListMixin: Deck list display, view modes, selection
    - CardDisplayMixin: Card grid display, filtering, widget creation
    - CardSortingMixin: Type-specific card sorting (Tarot, Lenormand, etc.)
    - CardSearchMixin: Search functionality (simple and advanced)
    - CardGroupsMixin: Card group management
    - DeckDialogsMixin: Deck editing dialog with tabs
    - ImportExportMixin: Deck import/export operations
    - CardCrudMixin: Card add, edit, view, delete operations
    """
    pass
