"""Deck list display and view modes for the library panel."""

import wx

from ui_helpers import _cfg, get_wx_color
from image_utils import load_and_scale_image


class DeckListMixin:
    """Mixin providing deck list display and view mode functionality."""

    def _refresh_decks_list(self):
        """Refresh the deck list display."""
        self.deck_list.DeleteAllItems()

        type_filter = self.type_filter.GetString(self.type_filter.GetSelection())

        if type_filter == 'All':
            decks = self.db.get_decks()
        else:
            types = self.db.get_cartomancy_types()
            type_id = None
            for t in types:
                if t['name'] == type_filter:
                    type_id = t['id']
                    break
            decks = self.db.get_decks(type_id) if type_id else []

        # Store deck data with card counts for sorting
        self._deck_list_data = []
        for deck in decks:
            cards = self.db.get_cards(deck['id'])
            card_back = deck['card_back_image'] if 'card_back_image' in deck.keys() else None
            self._deck_list_data.append({
                'id': deck['id'],
                'name': deck['name'],
                'type': deck.get('cartomancy_type_names', deck['cartomancy_type_name']),
                'count': len(cards),
                'card_back_image': card_back
            })

        # Apply current sort and display based on view mode
        self._sort_and_display_decks()
        self._refresh_deck_image_view()

        self._update_deck_choice()

    def _sort_and_display_decks(self):
        """Sort deck data and display in list"""
        self.deck_list.DeleteAllItems()

        # Sort the data
        if self._deck_list_sort_col == 0:
            key_func = lambda x: x['name'].lower()
        elif self._deck_list_sort_col == 1:
            key_func = lambda x: x['type'].lower()
        else:  # Column 2 - card count
            key_func = lambda x: x['count']

        sorted_data = sorted(self._deck_list_data, key=key_func, reverse=not self._deck_list_sort_asc)

        # Display sorted data
        for deck in sorted_data:
            idx = self.deck_list.InsertItem(self.deck_list.GetItemCount(), deck['name'])
            self.deck_list.SetItem(idx, 1, deck['type'])
            self.deck_list.SetItem(idx, 2, str(deck['count']))
            self.deck_list.SetItemData(idx, deck['id'])

    def _on_deck_list_col_click(self, event):
        """Handle column header click for sorting"""
        col = event.GetColumn()

        # If clicking same column, toggle direction; otherwise, sort ascending
        if col == self._deck_list_sort_col:
            self._deck_list_sort_asc = not self._deck_list_sort_asc
        else:
            self._deck_list_sort_col = col
            self._deck_list_sort_asc = True

        self._sort_and_display_decks()

    def _set_deck_view_mode(self, mode):
        """Switch between list and image view modes"""
        if mode == self._deck_view_mode:
            # Re-select the current button if clicking the already-active mode
            if mode == 'list':
                self.deck_list_view_btn.SetValue(True)
            else:
                self.deck_image_view_btn.SetValue(True)
            return

        self._deck_view_mode = mode

        # Update toggle button states
        self.deck_list_view_btn.SetValue(mode == 'list')
        self.deck_image_view_btn.SetValue(mode == 'image')

        # Show/hide views
        if mode == 'list':
            self.deck_image_scroll.Hide()
            self.deck_list.Show()
        else:
            self.deck_list.Hide()
            self.deck_image_scroll.Show()

        # Refresh layout
        self.deck_list.GetParent().Layout()

        # Restore selection in the new view
        if self._selected_deck_id:
            if mode == 'list':
                self._select_deck_by_id(self._selected_deck_id)
            else:
                self._select_deck_image_by_id(self._selected_deck_id)

    def _refresh_deck_image_view(self):
        """Refresh the deck image grid view"""
        self.deck_image_sizer.Clear(True)

        # Sort data same as list view
        if self._deck_list_sort_col == 0:
            key_func = lambda x: x['name'].lower()
        elif self._deck_list_sort_col == 1:
            key_func = lambda x: x['type'].lower()
        else:
            key_func = lambda x: x['count']

        sorted_data = sorted(self._deck_list_data, key=key_func, reverse=not self._deck_list_sort_asc)

        # Create deck widgets
        for deck in sorted_data:
            widget = self._create_deck_image_widget(deck)
            self.deck_image_sizer.Add(widget, 0, wx.ALL, 5)

        self.deck_image_scroll.Layout()
        self.deck_image_scroll.SetupScrolling(scrollToTop=False)

    def _create_deck_image_widget(self, deck):
        """Create a clickable deck thumbnail with name label"""
        panel = wx.Panel(self.deck_image_scroll)
        panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        panel.deck_id = deck['id']

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Card back image for deck thumbnails
        _deck_back_sz = _cfg.get('images', 'deck_back_max', [100, 150])
        max_width, max_height = _deck_back_sz[0], _deck_back_sz[1]
        card_back_path = deck.get('card_back_image')

        wx_bitmap = load_and_scale_image(card_back_path, (max_width, max_height), as_wx_bitmap=True)
        if wx_bitmap:
            img_ctrl = wx.StaticBitmap(panel, bitmap=wx_bitmap)
        else:
            img_ctrl = self._create_deck_placeholder(panel, max_width, max_height)

        sizer.Add(img_ctrl, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        # Deck name label (wrap to fit width)
        name_label = wx.StaticText(panel, label=deck['name'])
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_label.Wrap(max_width + 10)
        sizer.Add(name_label, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        panel.SetSizer(sizer)

        # Click handlers
        def on_click(e):
            self._on_deck_image_click(deck['id'])

        panel.Bind(wx.EVT_LEFT_DOWN, on_click)
        img_ctrl.Bind(wx.EVT_LEFT_DOWN, on_click)
        name_label.Bind(wx.EVT_LEFT_DOWN, on_click)

        # Double-click to edit
        def on_dclick(e):
            self._selected_deck_id = deck['id']
            self._on_edit_deck(None)

        panel.Bind(wx.EVT_LEFT_DCLICK, on_dclick)
        img_ctrl.Bind(wx.EVT_LEFT_DCLICK, on_dclick)
        name_label.Bind(wx.EVT_LEFT_DCLICK, on_dclick)

        return panel

    def _create_deck_placeholder(self, parent, width, height):
        """Create a placeholder for decks without card back images"""
        placeholder = wx.Panel(parent, size=(width, height))
        placeholder.SetBackgroundColour(get_wx_color('bg_tertiary'))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer()
        icon = wx.StaticText(placeholder, label="🂠")
        icon.SetFont(wx.Font(32, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        icon.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(icon, 0, wx.ALIGN_CENTER)
        sizer.AddStretchSpacer()
        placeholder.SetSizer(sizer)

        return placeholder

    def _on_deck_image_click(self, deck_id):
        """Handle click on a deck image in image view"""
        self._selected_deck_id = deck_id
        self._highlight_selected_deck_image(deck_id)
        self._refresh_cards_display(deck_id)

    def _highlight_selected_deck_image(self, deck_id):
        """Highlight the selected deck in image view"""
        for child in self.deck_image_scroll.GetChildren():
            if hasattr(child, 'deck_id'):
                if child.deck_id == deck_id:
                    child.SetBackgroundColour(get_wx_color('accent_dim'))
                else:
                    child.SetBackgroundColour(get_wx_color('bg_secondary'))
                child.Refresh()

    def _select_deck_image_by_id(self, deck_id):
        """Select a deck in the image view by its ID"""
        self._highlight_selected_deck_image(deck_id)
        # Scroll to make it visible if needed
        for child in self.deck_image_scroll.GetChildren():
            if hasattr(child, 'deck_id') and child.deck_id == deck_id:
                self.deck_image_scroll.ScrollChildIntoView(child)
                break

    def _select_deck_by_id(self, deck_id):
        """Select a deck in the list by its ID"""
        if hasattr(self, '_deck_view_mode') and self._deck_view_mode == 'image':
            # Image view mode
            if hasattr(self, '_deck_image_widgets'):
                for did, widget in self._deck_image_widgets.items():
                    if did == deck_id:
                        # Simulate click
                        self._selected_deck_id = deck_id
                        self._current_deck_id_for_cards = deck_id
                        self._refresh_cards_display(deck_id)
                        break
        else:
            # List view mode
            for i in range(self.deck_list.GetItemCount()):
                if self.deck_list.GetItemData(i) == deck_id:
                    self.deck_list.Select(i)
                    self.deck_list.EnsureVisible(i)
                    self._selected_deck_id = deck_id
                    self._current_deck_id_for_cards = deck_id
                    self._refresh_cards_display(deck_id)
                    return True
        return False

    def _on_type_filter(self, event):
        """Handle deck type filter change"""
        self._refresh_decks_list()

    def _on_deck_select(self, event):
        """Handle deck selection in list view"""
        idx = event.GetIndex()
        deck_id = self.deck_list.GetItemData(idx)
        self._selected_deck_id = deck_id
        self._refresh_cards_display(deck_id)
