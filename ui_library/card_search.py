"""Card search functionality for the library panel."""

import wx

from ui_helpers import get_wx_color


class CardSearchMixin:
    """Mixin providing card search functionality."""

    def _on_card_search(self, event):
        """Handle card search input - real-time filtering"""
        query = self.card_search_ctrl.GetValue().strip()

        if not query:
            # Empty search - restore normal view
            if self.search_scope_current.GetValue():
                if hasattr(self, '_current_deck_id_for_cards') and self._current_deck_id_for_cards:
                    self._refresh_cards_display(self._current_deck_id_for_cards)
            else:
                self._clear_search_results()
            return

        if self.search_scope_all.GetValue():
            self._perform_all_decks_search(query)
        else:
            self._perform_current_deck_search(query)

    def _on_card_search_clear(self, event):
        """Handle clearing the search"""
        self.card_search_ctrl.SetValue("")
        if self.search_scope_current.GetValue():
            if hasattr(self, '_current_deck_id_for_cards') and self._current_deck_id_for_cards:
                self._refresh_cards_display(self._current_deck_id_for_cards)
        else:
            self._clear_search_results()

    def _on_search_scope_change(self, event):
        """Handle scope toggle change"""
        query = self.card_search_ctrl.GetValue().strip()
        if query:
            self._on_card_search(None)
        else:
            if self.search_scope_current.GetValue():
                if hasattr(self, '_current_deck_id_for_cards') and self._current_deck_id_for_cards:
                    self._refresh_cards_display(self._current_deck_id_for_cards)

    def _on_toggle_advanced_search(self, event):
        """Toggle advanced search panel visibility"""
        if self.advanced_search_panel.IsShown():
            self.advanced_search_panel.Hide()
            self.advanced_search_btn.SetLabel("Advanced")
        else:
            self.advanced_search_panel.Show()
            self.advanced_search_btn.SetLabel("Simple")

        # Refresh layout
        self.advanced_search_panel.GetParent().Layout()

    def _on_advanced_search(self, event):
        """Perform advanced search with all filters"""
        # Get simple search query if present
        query = self.card_search_ctrl.GetValue().strip() or None

        # Also check advanced text fields
        name_query = self.adv_name_ctrl.GetValue().strip()
        archetype_query = self.adv_archetype_ctrl.GetValue().strip() or None
        notes_query = self.adv_notes_ctrl.GetValue().strip()

        # Combine simple search with name field
        if name_query:
            query = name_query

        # If notes query provided, add to general query
        if notes_query and query:
            query = query  # Notes are searched via general query
        elif notes_query:
            query = notes_query

        # Deck ID (None for all decks when scope is "All")
        deck_id = None
        if self.search_scope_current.GetValue() and hasattr(self, '_current_deck_id_for_cards'):
            deck_id = self._current_deck_id_for_cards

        # Deck type
        deck_type_idx = self.adv_deck_type.GetSelection()
        deck_type = None if deck_type_idx == 0 else self.adv_deck_type.GetString(deck_type_idx)

        # Category
        cat_idx = self.adv_category.GetSelection()
        category = None if cat_idx == 0 else self.adv_category.GetString(cat_idx)

        # Suit
        suit_idx = self.adv_suit.GetSelection()
        suit = None if suit_idx == 0 else self.adv_suit.GetString(suit_idx)

        # Boolean filters
        has_notes = True if self.adv_has_notes_cb.GetValue() else None
        has_image = True if self.adv_has_image_cb.GetValue() else None

        # Sort
        sort_options = ['name', 'deck', 'card_order']
        sort_by = sort_options[self.adv_sort_by.GetSelection()]

        # Perform search
        cards = self.db.search_cards(
            query=query,
            deck_id=deck_id,
            deck_type=deck_type,
            card_category=category,
            archetype=archetype_query,
            suit=suit,
            has_notes=has_notes,
            has_image=has_image,
            sort_by=sort_by
        )

        # Display results
        show_deck_name = self.search_scope_all.GetValue() or deck_id is None
        self._display_search_results(cards, show_deck_name=show_deck_name)

    def _on_advanced_search_clear(self, event):
        """Clear all advanced search fields"""
        self.adv_name_ctrl.SetValue("")
        self.adv_archetype_ctrl.SetValue("")
        self.adv_notes_ctrl.SetValue("")
        self.adv_deck_type.SetSelection(0)
        self.adv_category.SetSelection(0)
        self.adv_suit.SetSelection(0)
        self.adv_has_notes_cb.SetValue(False)
        self.adv_has_image_cb.SetValue(False)
        self.adv_sort_by.SetSelection(0)

        # Clear simple search too
        self.card_search_ctrl.SetValue("")

        # Refresh display
        if hasattr(self, '_current_deck_id_for_cards') and self._current_deck_id_for_cards:
            self._refresh_cards_display(self._current_deck_id_for_cards)

    def _perform_current_deck_search(self, query):
        """Search within current deck"""
        if not hasattr(self, '_current_deck_id_for_cards') or not self._current_deck_id_for_cards:
            return

        cards = self.db.search_cards(
            query=query,
            deck_id=self._current_deck_id_for_cards
        )

        self._display_search_results(cards, show_deck_name=False)

    def _perform_all_decks_search(self, query):
        """Search across all decks"""
        cards = self.db.search_cards(query=query)
        self._display_search_results(cards, show_deck_name=True)

    def _clear_search_results(self):
        """Clear search results and show default message"""
        self.cards_scroll.DestroyChildren()
        self.cards_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.cards_scroll.SetSizer(self.cards_sizer)
        self._card_widgets = {}

        self.deck_title.SetLabel("Select a deck or search all decks")
        self.cards_scroll.Layout()

    def _display_search_results(self, cards, show_deck_name=False):
        """Display search results with optional deck name labels"""
        self.cards_scroll.DestroyChildren()
        self.cards_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.cards_scroll.SetSizer(self.cards_sizer)
        self._card_widgets = {}
        self.selected_card_ids = set()

        result_count = len(cards)
        self.deck_title.SetLabel(f"Search Results ({result_count} card{'s' if result_count != 1 else ''})")

        if not cards:
            no_results = wx.StaticText(self.cards_scroll, label="No cards found matching your search.")
            no_results.SetForegroundColour(get_wx_color('text_secondary'))
            self.cards_sizer.Add(no_results, 0, wx.ALL, 20)
            self.cards_scroll.Layout()
            return

        for card in cards:
            self._create_search_result_widget(card, show_deck_name)

        self.cards_scroll.Layout()
        self.cards_scroll.FitInside()
        self.cards_scroll.SetupScrolling(scrollToTop=True)

    def _create_search_result_widget(self, card, show_deck_name=False):
        """Create a card widget for search results"""
        panel_height = 195 if show_deck_name else 175
        card_panel = wx.Panel(self.cards_scroll)
        card_panel.SetMinSize((130, panel_height))
        card_panel.SetBackgroundColour(get_wx_color('bg_tertiary'))
        card_panel.card_id = card['id']
        card_panel.deck_id = card['deck_id']

        card_sizer = wx.BoxSizer(wx.VERTICAL)

        # Thumbnail
        if card['image_path']:
            thumb_path = self.thumb_cache.get_thumbnail_path(card['image_path'])
            if thumb_path:
                try:
                    img = wx.Image(thumb_path, wx.BITMAP_TYPE_ANY)
                    if img.IsOk():
                        orig_width, orig_height = img.GetWidth(), img.GetHeight()
                        max_width, max_height = 120, 140
                        scale = min(max_width / orig_width, max_height / orig_height)
                        new_width = int(orig_width * scale)
                        new_height = int(orig_height * scale)
                        img = img.Scale(new_width, new_height, wx.IMAGE_QUALITY_HIGH)
                        bmp = wx.StaticBitmap(card_panel, bitmap=wx.Bitmap(img))
                        card_sizer.Add(bmp, 0, wx.ALL | wx.ALIGN_CENTER, 4)
                        bmp.Bind(wx.EVT_LEFT_DOWN, lambda e, c=card: self._on_search_result_click(e, c))
                        bmp.Bind(wx.EVT_LEFT_DCLICK, lambda e, c=card: self._on_search_result_dblclick(e, c))
                    else:
                        self._add_search_placeholder(card_panel, card_sizer, card)
                except Exception:
                    self._add_search_placeholder(card_panel, card_sizer, card)
            else:
                self._add_search_placeholder(card_panel, card_sizer, card)
        else:
            self._add_search_placeholder(card_panel, card_sizer, card)

        # Deck name label (for all-decks search)
        if show_deck_name:
            deck_label = wx.StaticText(card_panel, label=card['deck_name'][:20])
            deck_label.SetForegroundColour(get_wx_color('text_secondary'))
            font = deck_label.GetFont()
            font.SetPointSize(9)
            deck_label.SetFont(font)
            card_sizer.Add(deck_label, 0, wx.ALIGN_CENTER | wx.TOP, 2)
            deck_label.Bind(wx.EVT_LEFT_DOWN, lambda e, c=card: self._on_search_result_click(e, c))
            deck_label.Bind(wx.EVT_LEFT_DCLICK, lambda e, c=card: self._on_search_result_dblclick(e, c))

        # Card name tooltip
        card_panel.SetToolTip(card['name'])

        card_panel.SetSizer(card_sizer)
        card_panel.Bind(wx.EVT_LEFT_DOWN, lambda e, c=card: self._on_search_result_click(e, c))
        card_panel.Bind(wx.EVT_LEFT_DCLICK, lambda e, c=card: self._on_search_result_dblclick(e, c))

        self._card_widgets[card['id']] = card_panel
        self.cards_sizer.Add(card_panel, 0, wx.ALL, 6)

    def _add_search_placeholder(self, parent, sizer, card):
        """Add placeholder for card without image in search results"""
        placeholder = wx.StaticText(parent, label="🂠", size=(100, 120))
        placeholder.SetFont(wx.Font(48, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        placeholder.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(placeholder, 0, wx.ALL | wx.ALIGN_CENTER, 4)
        placeholder.Bind(wx.EVT_LEFT_DOWN, lambda e, c=card: self._on_search_result_click(e, c))
        placeholder.Bind(wx.EVT_LEFT_DCLICK, lambda e, c=card: self._on_search_result_dblclick(e, c))

    def _on_search_result_click(self, event, card):
        """Handle click on search result - select card"""
        card_id = card['id']

        # Clear previous selection
        for cid, widget in self._card_widgets.items():
            widget.SetBackgroundColour(get_wx_color('bg_tertiary'))
            widget.Refresh()

        # Highlight selected
        self.selected_card_ids = {card_id}
        if card_id in self._card_widgets:
            self._card_widgets[card_id].SetBackgroundColour(get_wx_color('accent_dim'))
            self._card_widgets[card_id].Refresh()

    def _on_search_result_dblclick(self, event, card):
        """Handle double-click on search result - navigate to card's deck and view"""
        deck_id = card['deck_id']
        card_id = card['id']

        # Clear search
        self.card_search_ctrl.SetValue("")
        self.search_scope_current.SetValue(True)

        # Select deck in list
        self._select_deck_by_id(deck_id)

        # View the card
        self._on_view_card(None, card_id)
