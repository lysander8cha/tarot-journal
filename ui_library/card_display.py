"""Card display and grid functionality for the library panel."""

import os

import wx

from ui_helpers import logger, _cfg, get_wx_color
from image_utils import load_and_scale_image


class CardDisplayMixin:
    """Mixin providing card display and grid functionality."""

    def _refresh_cards_display(self, deck_id, preserve_scroll=False):
        """Refresh the card grid display for the given deck."""
        # Save scroll position if requested
        scroll_pos = None
        if preserve_scroll:
            scroll_pos = self.cards_scroll.GetViewStart()

        self.cards_sizer.Clear(True)
        self.bitmap_cache.clear()
        self.selected_card_ids = set()
        self._card_widgets = {}
        self._current_deck_id_for_cards = deck_id
        self._current_cards_sorted = []
        self._current_cards_categorized = {}
        self._current_suit_names = {}
        self._pending_scroll_pos = scroll_pos  # Store for later restoration

        if not deck_id:
            self.cards_scroll.Layout()
            return

        cards = list(self.db.get_cards(deck_id))  # Convert to list immediately to avoid iterator exhaustion
        deck = self.db.get_deck(deck_id)
        suit_names = self.db.get_deck_suit_names(deck_id)
        self._current_suit_names = suit_names
        self._current_deck_type = deck['cartomancy_type_name'] if deck else 'Tarot'

        if deck:
            self.deck_title.SetLabel(deck['name'])

        # Update filter dropdown based on deck type
        if self._current_deck_type == 'Kipper':
            # Kipper cards have no suits, just show All
            new_choices = ['All']
        elif self._current_deck_type in ('Lenormand', 'Playing Cards'):
            # Lenormand and Playing Cards use playing card suits
            new_choices = ['All',
                          suit_names.get('hearts', 'Hearts'),
                          suit_names.get('diamonds', 'Diamonds'),
                          suit_names.get('clubs', 'Clubs'),
                          suit_names.get('spades', 'Spades')]
        else:
            # Check if this is a Gnostic/Eternal Tarot deck (cards have "Minor Arcana" as suit)
            is_gnostic = any(card['suit'] == 'Minor Arcana' for card in cards)
            if is_gnostic:
                # Gnostic/Eternal Tarot uses Major Arcana + Minor Arcana
                new_choices = ['All', 'Major Arcana', 'Minor Arcana']
            else:
                # Standard Tarot uses Major Arcana + tarot suits
                new_choices = ['All', 'Major Arcana',
                              suit_names.get('wands', 'Wands'),
                              suit_names.get('cups', 'Cups'),
                              suit_names.get('swords', 'Swords'),
                              suit_names.get('pentacles', 'Pentacles')]

        # Append custom groups for this deck
        self._filter_group_map = {}
        groups = self.db.get_card_groups(deck_id)
        if groups:
            new_choices.append("───────────")
            for group in groups:
                self._filter_group_map[len(new_choices)] = group['id']
                new_choices.append(group['name'])

        # Update dropdown if choices changed
        current_choices = [self.card_filter_choice.GetString(i) for i in range(self.card_filter_choice.GetCount())]
        if current_choices != new_choices:
            self.card_filter_choice.Clear()
            for choice in new_choices:
                self.card_filter_choice.Append(choice)
            self.card_filter_choice.SetSelection(0)

        self.card_filter_names = new_choices

        # Sort and categorize cards
        if self._current_deck_type == 'Playing Cards':
            self._current_cards_sorted = self._sort_playing_cards(cards, suit_names)
            self._current_cards_categorized = self._categorize_playing_cards(self._current_cards_sorted, suit_names)
        elif self._current_deck_type == 'Lenormand':
            self._current_cards_sorted = self._sort_lenormand_cards(cards)
            self._current_cards_categorized = self._categorize_lenormand_cards(self._current_cards_sorted)
        elif self._current_deck_type == 'Kipper':
            self._current_cards_sorted = self._sort_kipper_cards(cards)
            self._current_cards_categorized = {'All': self._current_cards_sorted}
        else:
            self._current_cards_sorted = self._sort_cards(cards, suit_names)
            self._current_cards_categorized = self._categorize_cards(self._current_cards_sorted, suit_names)

        # Display cards based on current filter
        self._display_filtered_cards()

    def _display_filtered_cards(self):
        """Display cards based on current filter selection"""
        # Clear existing widgets
        self.cards_scroll.DestroyChildren()
        self.cards_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.cards_scroll.SetSizer(self.cards_sizer)
        self._card_widgets = {}

        filter_idx = self.card_filter_choice.GetSelection()
        filter_name = self.card_filter_names[filter_idx] if filter_idx >= 0 and filter_idx < len(self.card_filter_names) else 'All'

        if filter_name == 'All':
            cards_to_show = self._current_cards_sorted
        elif filter_name == "───────────":
            # Separator line — treat as "All"
            cards_to_show = self._current_cards_sorted
        elif hasattr(self, '_filter_group_map') and filter_idx in self._filter_group_map:
            # Custom group filter
            group_id = self._filter_group_map[filter_idx]
            group_card_ids = set(self.db.get_cards_in_group(group_id))
            cards_to_show = [c for c in self._current_cards_sorted if c['id'] in group_card_ids]
        elif self._current_deck_type in ('Lenormand', 'Playing Cards'):
            # Lenormand and Playing Cards filtering by playing card suit
            # Map custom suit names back to standard suit keys
            suit_map = {
                self._current_suit_names.get('hearts', 'Hearts'): 'Hearts',
                self._current_suit_names.get('diamonds', 'Diamonds'): 'Diamonds',
                self._current_suit_names.get('clubs', 'Clubs'): 'Clubs',
                self._current_suit_names.get('spades', 'Spades'): 'Spades',
                'Hearts': 'Hearts', 'Diamonds': 'Diamonds',
                'Clubs': 'Clubs', 'Spades': 'Spades',
            }
            standard_suit = suit_map.get(filter_name, filter_name)
            cards_to_show = self._current_cards_categorized.get(standard_suit, [])
        else:
            # Tarot filtering
            if filter_name == 'Major Arcana':
                cards_to_show = self._current_cards_categorized.get('Major Arcana', [])
            elif filter_name == 'Minor Arcana':
                # Gnostic/Eternal Tarot uses Minor Arcana as a category
                cards_to_show = self._current_cards_categorized.get('Minor Arcana', [])
            elif filter_name in ['Wands', self._current_suit_names.get('wands', 'Wands')]:
                cards_to_show = self._current_cards_categorized.get('Wands', [])
            elif filter_name in ['Cups', self._current_suit_names.get('cups', 'Cups')]:
                cards_to_show = self._current_cards_categorized.get('Cups', [])
            elif filter_name in ['Swords', self._current_suit_names.get('swords', 'Swords')]:
                cards_to_show = self._current_cards_categorized.get('Swords', [])
            elif filter_name in ['Pentacles', self._current_suit_names.get('pentacles', 'Pentacles')]:
                cards_to_show = self._current_cards_categorized.get('Pentacles', [])
            else:
                cards_to_show = self._current_cards_sorted

        for card in cards_to_show:
            self._create_card_widget(self.cards_scroll, self.cards_sizer, card)

        self.cards_sizer.Layout()
        self.cards_scroll.FitInside()
        self.cards_scroll.Layout()
        self.cards_scroll.SetupScrolling()
        self.cards_scroll.Refresh()
        self.cards_scroll.Update()

        # Restore scroll position if one was saved
        if hasattr(self, '_pending_scroll_pos') and self._pending_scroll_pos is not None:
            wx.CallAfter(self.cards_scroll.Scroll, self._pending_scroll_pos[0], self._pending_scroll_pos[1])
            self._pending_scroll_pos = None

    def _create_card_widget(self, parent, sizer, card):
        """Create a card widget and add to sizer"""
        # Panel height: thumbnail (120x180 cached) + padding + text
        panel_height = 175
        card_panel = wx.Panel(parent)
        card_panel.SetMinSize((130, panel_height))
        card_panel.SetBackgroundColour(get_wx_color('bg_tertiary'))
        card_panel.card_id = card['id']

        # Add tooltip with card name (uses system default delay, typically ~500ms)
        card_name = card['name'] if 'name' in card.keys() else ''
        card_panel.SetToolTip(card_name)

        # Register widget for later access
        self._card_widgets[card['id']] = card_panel

        card_sizer = wx.BoxSizer(wx.VERTICAL)

        # Thumbnail
        if card['image_path']:
            # Get cached thumbnail path (thumbnail will be generated if needed)
            thumb_path = self.thumb_cache.get_thumbnail_path(card['image_path'])
            if not thumb_path:
                logger.warning(
                    f"Failed to generate thumbnail for: {card.get('name', 'unknown')} "
                    f"(path: {card['image_path']}, exists: {os.path.exists(card['image_path'])})"
                )

            # Scale thumbnail to gallery size
            _gallery_sz = _cfg.get('images', 'card_gallery_max', [200, 300])
            wx_bitmap = load_and_scale_image(thumb_path, tuple(_gallery_sz), as_wx_bitmap=True) if thumb_path else None

            if wx_bitmap:
                bmp = wx.StaticBitmap(card_panel, bitmap=wx_bitmap)
                card_sizer.Add(bmp, 0, wx.ALL | wx.ALIGN_CENTER, 4)
                bmp.Bind(wx.EVT_LEFT_DOWN, lambda e, cid=card['id']: self._on_card_click(e, cid))
                bmp.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card['id']: self._on_view_card(None, cid))
            else:
                self._add_placeholder(card_panel, card_sizer, card['id'])
        else:
            self._add_placeholder(card_panel, card_sizer, card['id'])

        card_panel.SetSizer(card_sizer)

        card_panel.Bind(wx.EVT_LEFT_DOWN, lambda e, cid=card['id']: self._on_card_click(e, cid))
        card_panel.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card['id']: self._on_view_card(None, cid))

        sizer.Add(card_panel, 0, wx.ALL, 6)

    def _on_card_filter_change(self, event):
        """Handle card filter dropdown change"""
        if hasattr(self, '_current_cards_sorted') and self._current_cards_sorted:
            # Skip separator selection — reset to "All"
            filter_idx = self.card_filter_choice.GetSelection()
            if 0 <= filter_idx < len(self.card_filter_names):
                if self.card_filter_names[filter_idx] == "───────────":
                    self.card_filter_choice.SetSelection(0)
            self._display_filtered_cards()
        event.Skip()

    def _add_placeholder(self, parent, sizer, card_id):
        """Add placeholder for card without image"""
        placeholder = wx.StaticText(parent, label="🂠", size=(100, 120))
        placeholder.SetFont(wx.Font(48, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        placeholder.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(placeholder, 0, wx.ALL | wx.ALIGN_CENTER, 4)
        placeholder.Bind(wx.EVT_LEFT_DOWN, lambda e, cid=card_id: self._on_card_click(e, cid))
        placeholder.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))

    def _on_card_click(self, event, card_id):
        """Handle card click with multi-select support (Shift+click)"""
        # Check for shift key
        if event.ShiftDown():
            # Toggle selection
            if card_id in self.selected_card_ids:
                self.selected_card_ids.discard(card_id)
            else:
                self.selected_card_ids.add(card_id)
        else:
            # Single select - clear others
            self.selected_card_ids = {card_id}

        self._update_card_selection_display()

    def _update_card_selection_display(self):
        """Update visual highlighting of selected cards"""
        for cid, widget in self._card_widgets.items():
            if cid in self.selected_card_ids:
                widget.SetBackgroundColour(get_wx_color('accent_dim'))
            else:
                widget.SetBackgroundColour(get_wx_color('bg_tertiary'))
            widget.Refresh()

        self.cards_scroll.Refresh()
