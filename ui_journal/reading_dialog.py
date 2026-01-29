"""Add reading dialog for journal entries."""

import json

import wx

from ui_helpers import logger, get_wx_color


class ReadingDialogMixin:
    """Mixin providing add reading dialog functionality."""

    def _on_add_reading(self, entry_id):
        """Add another reading to an existing entry"""
        dlg = wx.Dialog(self, title="Add Reading", size=(700, 500))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Spread/Deck selection
        select_sizer = wx.BoxSizer(wx.HORIZONTAL)

        spread_label = wx.StaticText(dlg, label="Spread:")
        spread_label.SetForegroundColour(get_wx_color('text_primary'))
        select_sizer.Add(spread_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        spread_choice = wx.Choice(dlg, choices=list(self._spread_map.keys()))
        select_sizer.Add(spread_choice, 0, wx.RIGHT, 20)

        deck_label = wx.StaticText(dlg, label="Default Deck:")
        deck_label.SetForegroundColour(get_wx_color('text_primary'))
        select_sizer.Add(deck_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        deck_choice = wx.Choice(dlg, choices=list(self._deck_map.keys()))
        select_sizer.Add(deck_choice, 0, wx.RIGHT, 10)

        # Use Any Deck toggle (empty label + StaticText for macOS)
        use_any_sizer = wx.BoxSizer(wx.HORIZONTAL)
        use_any_deck_cb = wx.CheckBox(dlg, label="")
        use_any_sizer.Add(use_any_deck_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        use_any_label = wx.StaticText(dlg, label="Use Any Deck")
        use_any_label.SetForegroundColour(get_wx_color('text_primary'))
        use_any_sizer.Add(use_any_label, 0, wx.ALIGN_CENTER_VERTICAL)
        select_sizer.Add(use_any_sizer, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(select_sizer, 0, wx.ALL, 15)

        # Store full deck info for filtering
        dlg._all_decks = {}
        for deck_name, deck_id in self._deck_map.items():
            deck = self.db.get_deck(deck_id)
            dlg._all_decks[deck_name] = {
                'id': deck_id,
                'cartomancy_type': deck['cartomancy_type_name'] if deck else None
            }

        # Spread canvas
        spread_canvas = wx.Panel(dlg, size=(-1, 300))
        spread_canvas.SetBackgroundColour(get_wx_color('card_slot'))
        sizer.Add(spread_canvas, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # Cards label
        cards_label = wx.StaticText(dlg, label="Click positions above to assign cards")
        cards_label.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(cards_label, 0, wx.LEFT | wx.TOP, 15)

        # Dialog state
        dlg._spread_cards = {}
        dlg._selected_deck_id = None

        def on_deck_change(event):
            name = deck_choice.GetStringSelection()
            if name in dlg._all_decks:
                dlg._selected_deck_id = dlg._all_decks[name]['id']

        deck_choice.Bind(wx.EVT_CHOICE, on_deck_change)

        def update_deck_choices(allowed_types=None):
            """Update deck choices based on allowed cartomancy types"""
            current_selection = deck_choice.GetStringSelection()
            deck_choice.Clear()

            for deck_name, deck_info in dlg._all_decks.items():
                if not allowed_types or use_any_deck_cb.GetValue():
                    deck_choice.Append(deck_name)
                elif deck_info['cartomancy_type'] in allowed_types:
                    deck_choice.Append(deck_name)

            if current_selection:
                idx = deck_choice.FindString(current_selection)
                if idx != wx.NOT_FOUND:
                    deck_choice.SetSelection(idx)
                    # SetSelection doesn't trigger EVT_CHOICE, so update manually
                    if current_selection in dlg._all_decks:
                        dlg._selected_deck_id = dlg._all_decks[current_selection]['id']

            # If nothing selected but decks are available, select the first one
            if deck_choice.GetSelection() == wx.NOT_FOUND and deck_choice.GetCount() > 0:
                deck_choice.SetSelection(0)
                name = deck_choice.GetStringSelection()
                if name in dlg._all_decks:
                    dlg._selected_deck_id = dlg._all_decks[name]['id']

        def on_spread_change(event):
            dlg._spread_cards = {}
            spread_canvas.Refresh()

            spread_name = spread_choice.GetStringSelection()
            allowed_types = None

            if spread_name and spread_name in self._spread_map:
                spread = self.db.get_spread(self._spread_map[spread_name])
                if spread:
                    allowed_types_json = spread['allowed_deck_types'] if 'allowed_deck_types' in spread.keys() else None
                    if allowed_types_json:
                        allowed_types = json.loads(allowed_types_json)

                    update_deck_choices(allowed_types)

                    # First, check for spread-specific default deck
                    spread_default_deck_id = spread['default_deck_id'] if 'default_deck_id' in spread.keys() else None
                    if spread_default_deck_id:
                        for name, info in dlg._all_decks.items():
                            if info['id'] == spread_default_deck_id:
                                idx = deck_choice.FindString(name)
                                if idx != wx.NOT_FOUND:
                                    deck_choice.SetSelection(idx)
                                    dlg._selected_deck_id = spread_default_deck_id
                                break
                    # Fall back to global default based on first allowed type
                    elif allowed_types:
                        default_deck_id = self.db.get_default_deck(allowed_types[0])
                        if default_deck_id:
                            for name, info in dlg._all_decks.items():
                                if info['id'] == default_deck_id:
                                    idx = deck_choice.FindString(name)
                                    if idx != wx.NOT_FOUND:
                                        deck_choice.SetSelection(idx)
                                        dlg._selected_deck_id = default_deck_id
                                    break
                    elif 'cartomancy_type' in spread.keys() and spread['cartomancy_type']:
                        default_deck_id = self.db.get_default_deck(spread['cartomancy_type'])
                        if default_deck_id:
                            for name, info in dlg._all_decks.items():
                                if info['id'] == default_deck_id:
                                    idx = deck_choice.FindString(name)
                                    if idx != wx.NOT_FOUND:
                                        deck_choice.SetSelection(idx)
                                        dlg._selected_deck_id = default_deck_id
                                    break
                    else:
                        update_deck_choices(None)

            dlg._spread_allowed_types = allowed_types

        spread_choice.Bind(wx.EVT_CHOICE, on_spread_change)

        def on_use_any_deck_change(event):
            spread_name = spread_choice.GetStringSelection()
            if spread_name and spread_name in self._spread_map:
                spread = self.db.get_spread(self._spread_map[spread_name])
                if spread:
                    allowed_types_json = spread['allowed_deck_types'] if 'allowed_deck_types' in spread.keys() else None
                    if allowed_types_json:
                        allowed_types = json.loads(allowed_types_json)
                        update_deck_choices(allowed_types)
                    else:
                        update_deck_choices(None)
            else:
                update_deck_choices(None)

        use_any_deck_cb.Bind(wx.EVT_CHECKBOX, on_use_any_deck_change)

        def on_canvas_paint(event):
            dc = wx.PaintDC(spread_canvas)
            dc.SetBackground(wx.Brush(get_wx_color('card_slot')))
            dc.Clear()

            spread_name = spread_choice.GetStringSelection()
            if not spread_name or spread_name not in self._spread_map:
                return

            spread = self.db.get_spread(self._spread_map[spread_name])
            if not spread:
                return

            positions = json.loads(spread['positions'])
            if not positions:
                return

            # Calculate centering offset
            min_x = min(p.get('x', 0) for p in positions)
            min_y = min(p.get('y', 0) for p in positions)
            max_x = max(p.get('x', 0) + p.get('width', 80) for p in positions)
            max_y = max(p.get('y', 0) + p.get('height', 120) for p in positions)
            spread_width = max_x - min_x
            spread_height = max_y - min_y
            canvas_w, canvas_h = spread_canvas.GetSize()
            offset_x = (canvas_w - spread_width) // 2 - min_x
            offset_y = (canvas_h - spread_height) // 2 - min_y

            dc.SetPen(wx.Pen(get_wx_color('border'), 1))
            dc.SetBrush(wx.Brush(get_wx_color('bg_tertiary')))
            dc.SetTextForeground(get_wx_color('text_dim'))

            for i, pos in enumerate(positions):
                x, y = pos.get('x', 0) + offset_x, pos.get('y', 0) + offset_y
                w, h = pos.get('width', 80), pos.get('height', 120)
                label = pos.get('label', f'Position {i+1}')

                if i in dlg._spread_cards:
                    dc.SetBrush(wx.Brush(get_wx_color('accent_dim')))
                    dc.DrawRectangle(x, y, w, h)
                    dc.SetTextForeground(get_wx_color('text_primary'))
                    dc.DrawText(dlg._spread_cards[i]['name'][:12], x + 5, y + h//2 - 8)
                    dc.SetTextForeground(get_wx_color('text_dim'))
                else:
                    dc.SetBrush(wx.Brush(get_wx_color('bg_tertiary')))
                    dc.DrawRectangle(x, y, w, h)
                    dc.DrawText(label, x + 5, y + h//2 - 8)

        spread_canvas.Bind(wx.EVT_PAINT, on_canvas_paint)

        def on_canvas_click(event):
            spread_name = spread_choice.GetStringSelection()
            if not spread_name or spread_name not in self._spread_map:
                return

            if not dlg._selected_deck_id:
                wx.MessageBox("Please select a deck first.", "Select Deck", wx.OK | wx.ICON_INFORMATION)
                return

            spread = self.db.get_spread(self._spread_map[spread_name])
            if not spread:
                return

            positions = json.loads(spread['positions'])
            if not positions:
                return

            # Calculate offset
            min_x = min(p.get('x', 0) for p in positions)
            min_y = min(p.get('y', 0) for p in positions)
            max_x = max(p.get('x', 0) + p.get('width', 80) for p in positions)
            max_y = max(p.get('y', 0) + p.get('height', 120) for p in positions)
            spread_width = max_x - min_x
            spread_height = max_y - min_y
            canvas_w, canvas_h = spread_canvas.GetSize()
            offset_x = (canvas_w - spread_width) // 2 - min_x
            offset_y = (canvas_h - spread_height) // 2 - min_y

            click_x, click_y = event.GetX(), event.GetY()

            for i, pos in enumerate(positions):
                px, py = pos.get('x', 0) + offset_x, pos.get('y', 0) + offset_y
                pw, ph = pos.get('width', 80), pos.get('height', 120)

                if px <= click_x <= px + pw and py <= click_y <= py + ph:
                    # Card picker with deck selection
                    self._show_reading_card_picker(
                        dlg, i, pos, spread_canvas, cards_label,
                        use_any_deck_cb, deck_choice
                    )
                    break

        spread_canvas.Bind(wx.EVT_LEFT_DOWN, on_canvas_click)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Add Reading")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            spread_name = spread_choice.GetStringSelection()
            deck_name = deck_choice.GetStringSelection()

            if spread_name or deck_name or dlg._spread_cards:
                spread_id = self._spread_map.get(spread_name)
                deck_id = self._deck_map.get(deck_name)

                cartomancy_type = None
                if deck_id:
                    deck = self.db.get_deck(deck_id)
                    if deck:
                        cartomancy_type = deck['cartomancy_type_name']

                cards_used = [
                    {
                        'name': c['name'],
                        'reversed': c.get('reversed', False),
                        'deck_id': c.get('deck_id'),
                        'deck_name': c.get('deck_name'),
                        'position_index': pos_idx
                    }
                    for pos_idx, c in dlg._spread_cards.items()
                ]
                deck_name_clean = deck_name.split(' (')[0] if deck_name else None

                # Get next position_order
                existing_readings = self.db.get_entry_readings(entry_id)
                next_order = len(existing_readings)

                self.db.add_entry_reading(
                    entry_id=entry_id,
                    spread_id=spread_id,
                    spread_name=spread_name,
                    deck_id=deck_id,
                    deck_name=deck_name_clean,
                    cartomancy_type=cartomancy_type,
                    cards_used=cards_used,
                    position_order=next_order
                )

                self._display_entry_in_viewer(entry_id)

        dlg.Destroy()

    def _show_reading_card_picker(self, dlg, position_index, pos, spread_canvas, cards_label,
                                   use_any_deck_cb, deck_choice):
        """Show card picker dialog for reading dialog"""
        card_dlg = wx.Dialog(dlg, title=f"Select Card for: {pos.get('label', f'Position {position_index+1}')}",
                            size=(450, 550))
        card_dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        card_dlg_sizer = wx.BoxSizer(wx.VERTICAL)

        deck_select_sizer = wx.BoxSizer(wx.HORIZONTAL)
        deck_select_label = wx.StaticText(card_dlg, label="Deck:")
        deck_select_label.SetForegroundColour(get_wx_color('text_primary'))
        deck_select_sizer.Add(deck_select_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # Build filtered deck list based on spread's allowed types
        allowed_types = getattr(dlg, '_spread_allowed_types', None)
        use_any = use_any_deck_cb.GetValue()
        picker_deck_names = []
        for deck_name, deck_info in dlg._all_decks.items():
            if not allowed_types or use_any:
                picker_deck_names.append(deck_name)
            elif deck_info['cartomancy_type'] in allowed_types:
                picker_deck_names.append(deck_name)

        picker_deck_choice = wx.Choice(card_dlg, choices=picker_deck_names)
        if dlg._selected_deck_id:
            for name, info in dlg._all_decks.items():
                if info['id'] == dlg._selected_deck_id:
                    idx = picker_deck_choice.FindString(name)
                    if idx != wx.NOT_FOUND:
                        picker_deck_choice.SetSelection(idx)
                    break
        deck_select_sizer.Add(picker_deck_choice, 1, wx.EXPAND)
        card_dlg_sizer.Add(deck_select_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Use any deck checkbox in card picker (empty label + StaticText for macOS)
        picker_use_any_sizer = wx.BoxSizer(wx.HORIZONTAL)
        picker_use_any_cb = wx.CheckBox(card_dlg, label="")
        picker_use_any_cb.SetValue(use_any)
        picker_use_any_sizer.Add(picker_use_any_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        picker_use_any_label = wx.StaticText(card_dlg, label="Use Any Deck (override restriction)")
        picker_use_any_label.SetForegroundColour(get_wx_color('text_dim'))
        picker_use_any_sizer.Add(picker_use_any_label, 0, wx.ALIGN_CENTER_VERTICAL)
        card_dlg_sizer.Add(picker_use_any_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Card list with thumbnails
        thumb_size = 48
        card_listctrl = wx.ListCtrl(card_dlg, style=wx.LC_LIST | wx.LC_SINGLE_SEL)
        card_listctrl.SetBackgroundColour(get_wx_color('bg_input'))
        card_listctrl.SetForegroundColour(get_wx_color('text_primary'))
        card_dlg_sizer.Add(card_listctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Store card data and image list (must keep reference to prevent GC)
        card_dlg._card_data = []
        card_dlg._image_list = wx.ImageList(thumb_size, thumb_size)
        card_listctrl.SetImageList(card_dlg._image_list, wx.IMAGE_LIST_SMALL)

        current_picker_deck_id = dlg._selected_deck_id

        def populate_cards(deck_id):
            card_listctrl.DeleteAllItems()
            card_dlg._card_data = []
            # Clear and recreate image list
            card_dlg._image_list.RemoveAll()

            if deck_id:
                cards = self.db.get_cards(deck_id)
                for card in cards:
                    card_dlg._card_data.append(card)
                    # Get thumbnail
                    img_idx = -1
                    if card['image_path']:
                        thumb_path = self.thumb_cache.get_thumbnail_path(card['image_path'])
                        if thumb_path:
                            try:
                                img = wx.Image(thumb_path, wx.BITMAP_TYPE_ANY)
                                if img.IsOk():
                                    # Scale to fit the thumbnail size
                                    w, h = img.GetWidth(), img.GetHeight()
                                    if w > 0 and h > 0:
                                        scale = min(thumb_size / w, thumb_size / h)
                                        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
                                        img = img.Scale(new_w, new_h, wx.IMAGE_QUALITY_HIGH)
                                        # Resize canvas to exact thumb_size with dark background
                                        img.Resize((thumb_size, thumb_size),
                                                  ((thumb_size - new_w) // 2, (thumb_size - new_h) // 2),
                                                  40, 40, 40)
                                        img_idx = card_dlg._image_list.Add(wx.Bitmap(img))
                            except Exception as e:
                                logger.debug("Failed to load card thumbnail: %s", e)
                    idx = card_listctrl.InsertItem(card_listctrl.GetItemCount(), card['name'], img_idx)
                    card_listctrl.SetItemData(idx, len(card_dlg._card_data) - 1)

        populate_cards(current_picker_deck_id)

        def on_picker_deck_change(e):
            nonlocal current_picker_deck_id
            name = picker_deck_choice.GetStringSelection()
            if name in dlg._all_decks:
                current_picker_deck_id = dlg._all_decks[name]['id']
                populate_cards(current_picker_deck_id)

        picker_deck_choice.Bind(wx.EVT_CHOICE, on_picker_deck_change)

        def on_picker_use_any_change(e):
            nonlocal current_picker_deck_id
            current_selection = picker_deck_choice.GetStringSelection()
            picker_deck_choice.Clear()

            picker_use_any = picker_use_any_cb.GetValue()
            for deck_name, deck_info in dlg._all_decks.items():
                if not allowed_types or picker_use_any:
                    picker_deck_choice.Append(deck_name)
                elif deck_info['cartomancy_type'] in allowed_types:
                    picker_deck_choice.Append(deck_name)

            if current_selection:
                idx = picker_deck_choice.FindString(current_selection)
                if idx != wx.NOT_FOUND:
                    picker_deck_choice.SetSelection(idx)
                elif picker_deck_choice.GetCount() > 0:
                    picker_deck_choice.SetSelection(0)
                    name = picker_deck_choice.GetStringSelection()
                    if name in dlg._all_decks:
                        current_picker_deck_id = dlg._all_decks[name]['id']
                        populate_cards(current_picker_deck_id)

        picker_use_any_cb.Bind(wx.EVT_CHECKBOX, on_picker_use_any_change)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(card_dlg, wx.ID_CANCEL, "Cancel")
        select_btn = wx.Button(card_dlg, wx.ID_OK, "Select")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(select_btn, 0)
        card_dlg_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        card_dlg.SetSizer(card_dlg_sizer)

        if card_dlg.ShowModal() == wx.ID_OK:
            sel_idx = card_listctrl.GetFirstSelected()
            if sel_idx != -1:
                data_idx = card_listctrl.GetItemData(sel_idx)
                card = card_dlg._card_data[data_idx]
                deck_name_full = picker_deck_choice.GetStringSelection()
                deck_name_clean = deck_name_full.split(' (')[0] if deck_name_full else None

                dlg._spread_cards[position_index] = {
                    'id': card['id'],
                    'name': card['name'],
                    'image_path': card['image_path'],
                    'reversed': False,
                    'deck_id': current_picker_deck_id,
                    'deck_name': deck_name_clean
                }

                if dlg._spread_cards:
                    names = [c['name'] for c in dlg._spread_cards.values()]
                    cards_label.SetLabel(f"Cards: {', '.join(names)}")

                spread_canvas.Refresh()
        card_dlg.Destroy()
