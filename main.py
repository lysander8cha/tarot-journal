#!/usr/bin/env python3
"""
Tarot Journal - A journaling app for cartomancy
wxPython GUI version
"""

import wx
import wx.lib.agw.flatnotebook as fnb
from database import Database, create_default_spreads, create_default_decks
from thumbnail_cache import get_cache
from import_presets import get_presets
from ui_helpers import logger, _cfg, VERSION, get_wx_color
from mixin_profiles import ProfilesMixin
from mixin_tags import TagsMixin
from mixin_settings import SettingsMixin
from mixin_spreads import SpreadsMixin
from ui_journal import JournalMixin
from ui_library import LibraryMixin


class TarotJournalApp(wx.App):
    def OnInit(self):
        frame = MainFrame()
        frame.Show()
        return True


class MainFrame(ProfilesMixin, TagsMixin, SettingsMixin, SpreadsMixin, JournalMixin, LibraryMixin, wx.Frame):
    def __init__(self):
        # Get screen size and set window to configured % of it, with max bounds
        display = wx.Display()
        screen_rect = display.GetClientArea()
        screen_pct = _cfg.get('window', 'screen_percent', 0.85)
        width = min(_cfg.get('window', 'max_width', 1200), int(screen_rect.width * screen_pct))
        height = min(_cfg.get('window', 'max_height', 800), int(screen_rect.height * screen_pct))
        
        super().__init__(None, title="Tarot Journal", size=(width, height))
        
        # Initialize systems
        self.db = Database()
        create_default_spreads(self.db)
        create_default_decks(self.db)
        self.thumb_cache = get_cache()
        self.presets = get_presets()
        logger.info("Database and systems initialized")
        
        # State
        self.current_entry_id = None
        self.selected_deck_id = None
        self.selected_card_ids = set()  # Multi-select support
        self.editing_spread_id = None
        self.designer_positions = []
        self.drag_data = {'idx': None, 'offset_x': 0, 'offset_y': 0, 'resize': None}  # resize: 'nw', 'ne', 'sw', 'se', or None
        self._current_deck_id_for_cards = None
        self._current_cards_sorted = []
        self._current_cards_categorized = {}
        self._current_suit_names = {}
        self._current_deck_type = 'Tarot'
        self._card_widgets = {}  # Track card widgets by card_id

        # Bitmap cache
        self.bitmap_cache = {}
        
        # Set up UI
        self.SetBackgroundColour(get_wx_color('bg_primary'))
        self._create_ui()
        self._refresh_all()
        
        # Center on screen
        self.Centre()
        
        # Force refresh of all colors after everything is built
        wx.CallAfter(self._refresh_all_colors)
    
    def _refresh_all_colors(self):
        """Refresh all widget colors - needed after initial render"""
        self._update_widget_colors(self)
        self._refresh_notebook_colors()
    
    def _refresh_notebook_colors(self):
        """Refresh notebook tab colors - needed after initial render"""
        # Main notebook
        self.notebook.SetTabAreaColour(get_wx_color('bg_primary'))
        self.notebook.SetActiveTabColour(get_wx_color('bg_tertiary'))
        self.notebook.SetNonActiveTabTextColour(get_wx_color('text_primary'))
        self.notebook.SetActiveTabTextColour(get_wx_color('text_primary'))
        self.notebook.SetGradientColourTo(get_wx_color('bg_tertiary'))
        self.notebook.SetGradientColourFrom(get_wx_color('bg_secondary'))
        self.notebook.Refresh()
        self.notebook.Update()
    
    def _create_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Header
        header = wx.Panel(self)
        header.SetBackgroundColour(get_wx_color('bg_primary'))
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header, label="Tarot Journal")
        title.SetForegroundColour(get_wx_color('text_primary'))
        title.SetFont(wx.Font(22, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        header_sizer.AddStretchSpacer()
        
        stats_btn = wx.Button(header, label="Stats")
        stats_btn.Bind(wx.EVT_BUTTON, self._on_stats)
        header_sizer.Add(stats_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        header.SetSizer(header_sizer)
        main_sizer.Add(header, 0, wx.EXPAND)
        
        # FlatNotebook with full color control
        style = (fnb.FNB_NO_X_BUTTON | fnb.FNB_NO_NAV_BUTTONS | 
                fnb.FNB_NODRAG | fnb.FNB_VC8)
        self.notebook = fnb.FlatNotebook(self, agwStyle=style)
        
        # Apply theme colors to notebook - dark tabs with light text
        self.notebook.SetTabAreaColour(get_wx_color('bg_primary'))
        self.notebook.SetActiveTabColour(get_wx_color('bg_tertiary'))
        self.notebook.SetNonActiveTabTextColour(get_wx_color('text_primary'))
        self.notebook.SetActiveTabTextColour(get_wx_color('text_primary'))
        self.notebook.SetGradientColourTo(get_wx_color('bg_tertiary'))
        self.notebook.SetGradientColourFrom(get_wx_color('bg_secondary'))
        
        self.journal_panel = self._create_journal_panel()
        self.library_panel = self._create_library_panel()
        self.spreads_panel = self._create_spreads_panel()
        self.profiles_panel = self._create_profiles_panel()
        self.tags_panel = self._create_tags_panel()
        self.settings_panel = self._create_settings_panel()

        self.notebook.AddPage(self.journal_panel, "Journal")
        self.notebook.AddPage(self.library_panel, "Card Library")
        self.notebook.AddPage(self.spreads_panel, "Spreads")
        self.notebook.AddPage(self.profiles_panel, "Profiles")
        self.notebook.AddPage(self.tags_panel, "Tags")
        self.notebook.AddPage(self.settings_panel, "Settings")
        
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
    

    # ═══════════════════════════════════════════
    # REFRESH METHODS
    # ═══════════════════════════════════════════
    def _refresh_all(self):
        self._refresh_entries_list()
        self._refresh_decks_list()
        self._refresh_spreads_list()
        self._refresh_tags_list()
        self._update_deck_choice()
        self._update_spread_choice()
    

def main():
    logger.info("Tarot Journal v%s starting", VERSION)
    app = TarotJournalApp()
    app.MainLoop()
    logger.info("Tarot Journal shutting down")


if __name__ == '__main__':
    main()
