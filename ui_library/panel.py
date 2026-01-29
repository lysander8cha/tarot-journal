"""Main library panel creation for the library mixin."""

import wx
import wx.lib.scrolledpanel as scrolled

from ui_helpers import _cfg, get_wx_color


class LibraryPanelMixin:
    """Mixin providing the main library panel creation."""

    def _create_library_panel(self):
        """Create the library panel with deck list and card grid."""
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))

        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)
        splitter.SetBackgroundColour(get_wx_color('bg_primary'))
        splitter.SetMinimumPaneSize(250)

        # Left: Deck list
        left = wx.Panel(splitter)
        left.SetBackgroundColour(get_wx_color('bg_primary'))
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        decks_label = wx.StaticText(left, label="Decks")
        decks_label.SetForegroundColour(get_wx_color('text_primary'))
        left_sizer.Add(decks_label, 0, wx.ALL, 5)

        # View toggle buttons (List / Images)
        view_toggle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.deck_list_view_btn = wx.ToggleButton(left, label="List")
        self.deck_list_view_btn.SetValue(True)  # Default to list view
        self.deck_list_view_btn.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._set_deck_view_mode('list'))
        view_toggle_sizer.Add(self.deck_list_view_btn, 0, wx.RIGHT, 5)

        self.deck_image_view_btn = wx.ToggleButton(left, label="Images")
        self.deck_image_view_btn.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._set_deck_view_mode('image'))
        view_toggle_sizer.Add(self.deck_image_view_btn, 0)

        left_sizer.Add(view_toggle_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Track deck view mode
        self._deck_view_mode = 'list'
        self._selected_deck_id = None  # Track selected deck across view switches

        # Type filter
        self.type_filter = wx.Choice(left, choices=['All', 'Tarot', 'Lenormand', 'I Ching', 'Kipper', 'Playing Cards', 'Oracle'])
        self.type_filter.SetSelection(0)
        self.type_filter.Bind(wx.EVT_CHOICE, self._on_type_filter)
        left_sizer.Add(self.type_filter, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Deck list
        self.deck_list = wx.ListCtrl(left, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.deck_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.deck_list.SetForegroundColour(get_wx_color('text_primary'))
        self.deck_list.InsertColumn(0, "Name", width=140)
        self.deck_list.InsertColumn(1, "Type", width=80)
        self.deck_list.InsertColumn(2, "#", width=40)
        self.deck_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_deck_select)
        self.deck_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit_deck)
        self.deck_list.Bind(wx.EVT_LIST_COL_CLICK, self._on_deck_list_col_click)
        left_sizer.Add(self.deck_list, 1, wx.EXPAND | wx.ALL, 5)

        # Deck image view (scrolled panel with card back thumbnails)
        self.deck_image_scroll = scrolled.ScrolledPanel(left)
        self.deck_image_scroll.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.deck_image_scroll.SetupScrolling()
        self.deck_image_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.deck_image_scroll.SetSizer(self.deck_image_sizer)
        self.deck_image_scroll.Hide()  # Hidden by default, list view shown
        left_sizer.Add(self.deck_image_scroll, 1, wx.EXPAND | wx.ALL, 5)

        # Track deck list sorting state
        self._deck_list_sort_col = 0  # Default sort by name
        self._deck_list_sort_asc = True  # Ascending by default
        self._deck_list_data = []  # Store deck data for sorting

        # Buttons - vertical stack for cleaner look
        btn_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add and Import on first row
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(left, label="+ Add")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add_deck)
        row1.Add(add_btn, 1, wx.RIGHT, 5)

        import_btn = wx.Button(left, label="Import Folder")
        import_btn.Bind(wx.EVT_BUTTON, self._on_import_folder)
        row1.Add(import_btn, 1)
        btn_sizer.Add(row1, 0, wx.EXPAND | wx.BOTTOM, 5)

        # Edit and Delete on second row
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        edit_deck_btn = wx.Button(left, label="Edit Deck")
        edit_deck_btn.Bind(wx.EVT_BUTTON, self._on_edit_deck)
        row2.Add(edit_deck_btn, 1, wx.RIGHT, 5)

        del_btn = wx.Button(left, label="Delete")
        del_btn.Bind(wx.EVT_BUTTON, self._on_delete_deck)
        row2.Add(del_btn, 1)
        btn_sizer.Add(row2, 0, wx.EXPAND | wx.BOTTOM, 5)

        # Export and Import deck on third row
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        export_deck_btn = wx.Button(left, label="Export Deck")
        export_deck_btn.Bind(wx.EVT_BUTTON, self._on_export_deck)
        row3.Add(export_deck_btn, 1, wx.RIGHT, 5)

        import_deck_btn = wx.Button(left, label="Import Deck")
        import_deck_btn.Bind(wx.EVT_BUTTON, self._on_import_deck)
        row3.Add(import_deck_btn, 1)
        btn_sizer.Add(row3, 0, wx.EXPAND)

        left_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)
        left.SetSizer(left_sizer)

        # Right: Cards grid with filter
        right = wx.Panel(splitter)
        right.SetBackgroundColour(get_wx_color('bg_primary'))
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Search row
        search_row = wx.BoxSizer(wx.HORIZONTAL)

        # Search control
        self.card_search_ctrl = wx.SearchCtrl(right, size=(200, -1))
        self.card_search_ctrl.SetDescriptiveText("Search cards...")
        self.card_search_ctrl.ShowCancelButton(True)
        self.card_search_ctrl.Bind(wx.EVT_TEXT, self._on_card_search)
        self.card_search_ctrl.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self._on_card_search_clear)
        search_row.Add(self.card_search_ctrl, 1, wx.EXPAND | wx.RIGHT, 10)

        # Scope toggle (Current Deck / All Decks) - empty labels per CLAUDE.md
        self.search_scope_current = wx.RadioButton(right, label="", style=wx.RB_GROUP)
        search_row.Add(self.search_scope_current, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        current_label = wx.StaticText(right, label="Current Deck")
        current_label.SetForegroundColour(get_wx_color('text_primary'))
        search_row.Add(current_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        self.search_scope_all = wx.RadioButton(right, label="")
        search_row.Add(self.search_scope_all, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        all_label = wx.StaticText(right, label="All Decks")
        all_label.SetForegroundColour(get_wx_color('text_primary'))
        search_row.Add(all_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.search_scope_current.SetValue(True)
        self.search_scope_current.Bind(wx.EVT_RADIOBUTTON, self._on_search_scope_change)
        self.search_scope_all.Bind(wx.EVT_RADIOBUTTON, self._on_search_scope_change)

        # Advanced search toggle button
        self.advanced_search_btn = wx.Button(right, label="Advanced")
        self.advanced_search_btn.Bind(wx.EVT_BUTTON, self._on_toggle_advanced_search)
        search_row.Add(self.advanced_search_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        right_sizer.Add(search_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Advanced search panel (initially hidden)
        self.advanced_search_panel = wx.Panel(right)
        self.advanced_search_panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        adv_sizer = wx.BoxSizer(wx.VERTICAL)

        # Row 1: Field-specific searches
        adv_row1 = wx.BoxSizer(wx.HORIZONTAL)

        name_label = wx.StaticText(self.advanced_search_panel, label="Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row1.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.adv_name_ctrl = wx.TextCtrl(self.advanced_search_panel, size=(100, -1))
        adv_row1.Add(self.adv_name_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        arch_label = wx.StaticText(self.advanced_search_panel, label="Archetype:")
        arch_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row1.Add(arch_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.adv_archetype_ctrl = wx.TextCtrl(self.advanced_search_panel, size=(100, -1))
        adv_row1.Add(self.adv_archetype_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        notes_label = wx.StaticText(self.advanced_search_panel, label="Notes contain:")
        notes_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row1.Add(notes_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.adv_notes_ctrl = wx.TextCtrl(self.advanced_search_panel, size=(100, -1))
        adv_row1.Add(self.adv_notes_ctrl, 0, wx.ALIGN_CENTER_VERTICAL)

        adv_sizer.Add(adv_row1, 0, wx.EXPAND | wx.ALL, 8)

        # Row 2: Filter dropdowns
        adv_row2 = wx.BoxSizer(wx.HORIZONTAL)

        deck_type_label = wx.StaticText(self.advanced_search_panel, label="Deck Type:")
        deck_type_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row2.Add(deck_type_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        deck_types = ['Any', 'Tarot', 'Lenormand', 'I Ching', 'Kipper', 'Playing Cards', 'Oracle']
        self.adv_deck_type = wx.Choice(self.advanced_search_panel, choices=deck_types)
        self.adv_deck_type.SetSelection(0)
        adv_row2.Add(self.adv_deck_type, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        cat_label = wx.StaticText(self.advanced_search_panel, label="Category:")
        cat_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row2.Add(cat_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        categories = ['Any', 'Major Arcana', 'Minor Arcana', 'Court Cards']
        self.adv_category = wx.Choice(self.advanced_search_panel, choices=categories)
        self.adv_category.SetSelection(0)
        adv_row2.Add(self.adv_category, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        suit_label = wx.StaticText(self.advanced_search_panel, label="Suit:")
        suit_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row2.Add(suit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        suits = ['Any', 'Wands', 'Cups', 'Swords', 'Pentacles', 'Hearts', 'Diamonds', 'Clubs', 'Spades']
        self.adv_suit = wx.Choice(self.advanced_search_panel, choices=suits)
        self.adv_suit.SetSelection(0)
        adv_row2.Add(self.adv_suit, 0, wx.ALIGN_CENTER_VERTICAL)

        adv_sizer.Add(adv_row2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # Row 3: Boolean filters and buttons
        adv_row3 = wx.BoxSizer(wx.HORIZONTAL)

        # Has notes checkbox (empty label + StaticText per CLAUDE.md)
        self.adv_has_notes_cb = wx.CheckBox(self.advanced_search_panel, label="")
        adv_row3.Add(self.adv_has_notes_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        has_notes_label = wx.StaticText(self.advanced_search_panel, label="Has notes")
        has_notes_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row3.Add(has_notes_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        # Has image checkbox
        self.adv_has_image_cb = wx.CheckBox(self.advanced_search_panel, label="")
        adv_row3.Add(self.adv_has_image_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        has_image_label = wx.StaticText(self.advanced_search_panel, label="Has image")
        has_image_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row3.Add(has_image_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 25)

        # Sort by
        sort_label = wx.StaticText(self.advanced_search_panel, label="Sort by:")
        sort_label.SetForegroundColour(get_wx_color('text_primary'))
        adv_row3.Add(sort_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sort_options = ['Name', 'Deck', 'Card Order']
        self.adv_sort_by = wx.Choice(self.advanced_search_panel, choices=sort_options)
        self.adv_sort_by.SetSelection(0)
        adv_row3.Add(self.adv_sort_by, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        # Search and Clear buttons
        adv_search_btn = wx.Button(self.advanced_search_panel, label="Search")
        adv_search_btn.Bind(wx.EVT_BUTTON, self._on_advanced_search)
        adv_row3.Add(adv_search_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        adv_clear_btn = wx.Button(self.advanced_search_panel, label="Clear")
        adv_clear_btn.Bind(wx.EVT_BUTTON, self._on_advanced_search_clear)
        adv_row3.Add(adv_clear_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        adv_sizer.Add(adv_row3, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.advanced_search_panel.SetSizer(adv_sizer)
        self.advanced_search_panel.Hide()
        right_sizer.Add(self.advanced_search_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Header row with title and filter
        header_row = wx.BoxSizer(wx.HORIZONTAL)

        self.deck_title = wx.StaticText(right, label="Select a deck")
        self.deck_title.SetForegroundColour(get_wx_color('text_primary'))
        self.deck_title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_row.Add(self.deck_title, 0, wx.ALIGN_CENTER_VERTICAL)

        header_row.AddStretchSpacer()

        # Card filter dropdown
        filter_label = wx.StaticText(right, label="Filter:")
        filter_label.SetForegroundColour(get_wx_color('text_primary'))
        header_row.Add(filter_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.card_filter_names = ['All', 'Major Arcana', 'Wands', 'Cups', 'Swords', 'Pentacles']
        self._filter_group_map = {}  # Map filter index -> group_id
        self.card_filter_choice = wx.Choice(right, choices=self.card_filter_names)
        self.card_filter_choice.SetSelection(0)
        self.card_filter_choice.Bind(wx.EVT_CHOICE, self._on_card_filter_change)
        header_row.Add(self.card_filter_choice, 0, wx.ALIGN_CENTER_VERTICAL)

        self.groups_btn = wx.Button(right, label="Groups...")
        self.groups_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.groups_btn.SetForegroundColour(get_wx_color('text_primary'))
        self.groups_btn.Bind(wx.EVT_BUTTON, self._on_manage_groups)
        header_row.Add(self.groups_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        right_sizer.Add(header_row, 0, wx.EXPAND | wx.ALL, 10)

        # Single scrolled panel for cards (filtered dynamically)
        self.cards_scroll = scrolled.ScrolledPanel(right)
        self.cards_scroll.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.cards_scroll.SetupScrolling()
        self.cards_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.cards_scroll.SetSizer(self.cards_sizer)

        right_sizer.Add(self.cards_scroll, 1, wx.EXPAND | wx.ALL, 5)

        # Card buttons
        card_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_card_btn = wx.Button(right, label="+ Add Card")
        add_card_btn.Bind(wx.EVT_BUTTON, self._on_add_card)
        card_btn_sizer.Add(add_card_btn, 0, wx.RIGHT, 5)

        import_cards_btn = wx.Button(right, label="Import Images")
        import_cards_btn.Bind(wx.EVT_BUTTON, self._on_import_cards)
        card_btn_sizer.Add(import_cards_btn, 0, wx.RIGHT, 5)

        edit_card_btn = wx.Button(right, label="Edit Selected")
        edit_card_btn.Bind(wx.EVT_BUTTON, self._on_edit_card)
        card_btn_sizer.Add(edit_card_btn, 0, wx.RIGHT, 5)

        del_card_btn = wx.Button(right, label="Delete Selected")
        del_card_btn.Bind(wx.EVT_BUTTON, self._on_delete_card)
        card_btn_sizer.Add(del_card_btn, 0)

        right_sizer.Add(card_btn_sizer, 0, wx.ALL, 10)
        right.SetSizer(right_sizer)

        splitter.SplitVertically(left, right, _cfg.get('panels', 'cards_splitter', 280))

        panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel_sizer.Add(splitter, 1, wx.EXPAND)
        panel.SetSizer(panel_sizer)

        return panel
