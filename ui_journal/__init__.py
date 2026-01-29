"""Journal panel UI components for the tarot journal application.

This package contains the journal panel functionality, split into focused modules:
- panel.py: Main panel creation
- entry_list.py: Entry list management and refresh
- entry_viewer.py: Entry viewer and follow-up notes display
- entry_editor.py: Entry creation/editing dialog
- reading_dialog.py: Add reading dialog
- import_export.py: Import/export functionality
"""

from .panel import JournalPanelMixin
from .entry_list import EntryListMixin
from .entry_viewer import EntryViewerMixin
from .entry_editor import EntryEditorMixin
from .reading_dialog import ReadingDialogMixin
from .import_export import ImportExportMixin


class JournalMixin(
    JournalPanelMixin,
    EntryListMixin,
    EntryViewerMixin,
    EntryEditorMixin,
    ReadingDialogMixin,
    ImportExportMixin,
):
    """Combined mixin providing all journal panel functionality.

    This class combines all journal-related mixins into a single class
    that can be used with multiple inheritance in the main application frame.
    """
    pass
