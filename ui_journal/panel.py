"""Journal panel creation for MainFrame."""

import wx
import wx.lib.scrolledpanel as scrolled

from ui_helpers import _cfg, get_wx_color


class JournalPanelMixin:
    """Mixin providing journal panel creation."""

    def _create_journal_panel(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))

        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)
        splitter.SetBackgroundColour(get_wx_color('bg_primary'))
        splitter.SetMinimumPaneSize(250)

        # Left: Entry list
        left = wx.Panel(splitter)
        left.SetBackgroundColour(get_wx_color('bg_primary'))
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Search
        self.search_ctrl = wx.SearchCtrl(left)
        self.search_ctrl.Bind(wx.EVT_SEARCH, self._on_search)
        self.search_ctrl.Bind(wx.EVT_TEXT, self._on_search)
        left_sizer.Add(self.search_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Tag filter
        self.tag_filter = wx.Choice(left)
        self.tag_filter.Bind(wx.EVT_CHOICE, self._on_tag_filter)
        left_sizer.Add(self.tag_filter, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Entry list (multi-select enabled)
        self.entry_list = wx.ListCtrl(left, style=wx.LC_REPORT)
        self.entry_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.entry_list.SetForegroundColour(get_wx_color('text_primary'))
        self.entry_list.InsertColumn(0, "Date/Time", width=120)
        self.entry_list.InsertColumn(1, "Title", width=180)
        self.entry_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_entry_select)
        left_sizer.Add(self.entry_list, 1, wx.EXPAND | wx.ALL, 5)

        # Buttons - row 1
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        new_btn = wx.Button(left, label="+ New Entry")
        new_btn.Bind(wx.EVT_BUTTON, self._on_new_entry_dialog)
        btn_sizer.Add(new_btn, 1, wx.RIGHT, 3)

        edit_btn = wx.Button(left, label="Edit")
        edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_entry_dialog)
        btn_sizer.Add(edit_btn, 1, wx.RIGHT, 3)

        del_btn = wx.Button(left, label="Delete")
        del_btn.Bind(wx.EVT_BUTTON, self._on_delete_entry)
        btn_sizer.Add(del_btn, 1)

        left_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Buttons - row 2 (import/export)
        btn_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        export_btn = wx.Button(left, label="Export...")
        export_btn.Bind(wx.EVT_BUTTON, self._on_export_entries)
        btn_sizer2.Add(export_btn, 1, wx.RIGHT, 3)

        import_btn = wx.Button(left, label="Import...")
        import_btn.Bind(wx.EVT_BUTTON, self._on_import_entries)
        btn_sizer2.Add(import_btn, 1)

        left_sizer.Add(btn_sizer2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        left.SetSizer(left_sizer)

        # Right: Entry Viewer (read-only)
        self.viewer_panel = scrolled.ScrolledPanel(splitter)
        self.viewer_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        self.viewer_panel.SetupScrolling()
        self.viewer_sizer = wx.BoxSizer(wx.VERTICAL)

        # Placeholder text
        self.viewer_placeholder = wx.StaticText(self.viewer_panel, label="Select an entry to view")
        self.viewer_placeholder.SetForegroundColour(get_wx_color('text_secondary'))
        self.viewer_placeholder.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        self.viewer_sizer.Add(self.viewer_placeholder, 0, wx.ALL, 20)

        self.viewer_panel.SetSizer(self.viewer_sizer)

        splitter.SplitVertically(left, self.viewer_panel, _cfg.get('panels', 'journal_splitter', 300))

        panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel_sizer.Add(splitter, 1, wx.EXPAND)
        panel.SetSizer(panel_sizer)

        return panel
