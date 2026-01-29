"""Entry editor dialog for the journal panel."""

import json
from datetime import datetime

import wx
import wx.adv

from ui_helpers import logger, get_wx_color
from rich_text_panel import RichTextPanel
from image_utils import load_for_spread_display


class EntryEditorMixin:
    """Mixin providing entry editor functionality."""

    def _on_new_entry_dialog(self, event):
        """Open dialog to create a new entry"""
        self._open_entry_editor(None)

    def _on_edit_entry_dialog(self, event):
        """Open dialog to edit selected entry"""
        if not self.current_entry_id:
            wx.MessageBox("Select an entry to edit.", "No Entry", wx.OK | wx.ICON_INFORMATION)
            return
        self._open_entry_editor(self.current_entry_id)

    def _open_entry_editor(self, entry_id):
        """Open the entry editor dialog"""
        is_new = entry_id is None

        if is_new:
            entry_id = self.db.add_entry(title="New Entry")
            entry = self.db.get_entry(entry_id)
        else:
            entry = self.db.get_entry(entry_id)
            if not entry:
                return

        dlg = wx.Dialog(self, title="New Entry" if is_new else "Edit Entry",
                       size=(800, 700), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        # Main dialog sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Scrolled window for content
        scroll_win = wx.ScrolledWindow(dlg, style=wx.VSCROLL)
        scroll_win.SetScrollRate(0, 20)
        scroll_win.SetBackgroundColour(get_wx_color('bg_primary'))

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title_label = wx.StaticText(scroll_win, label="Title:")
        title_label.SetForegroundColour(get_wx_color('text_primary'))
        title_sizer.Add(title_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        title_ctrl = wx.TextCtrl(scroll_win)
        title_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        title_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        title_ctrl.SetValue(entry['title'] or '')
        title_sizer.Add(title_ctrl, 1, wx.EXPAND)
        sizer.Add(title_sizer, 0, wx.EXPAND | wx.ALL, 15)

        # Date/Time selection
        datetime_sizer = wx.BoxSizer(wx.HORIZONTAL)

        datetime_label = wx.StaticText(scroll_win, label="Reading Date/Time:")
        datetime_label.SetForegroundColour(get_wx_color('text_primary'))
        datetime_sizer.Add(datetime_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # Radio buttons for now vs custom (empty labels with separate StaticText for macOS)
        use_now_radio = wx.RadioButton(scroll_win, label="", style=wx.RB_GROUP)
        datetime_sizer.Add(use_now_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        now_label = wx.StaticText(scroll_win, label="Now")
        now_label.SetForegroundColour(get_wx_color('text_primary'))
        datetime_sizer.Add(now_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        use_custom_radio = wx.RadioButton(scroll_win, label="")
        datetime_sizer.Add(use_custom_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        custom_label = wx.StaticText(scroll_win, label="Custom:")
        custom_label.SetForegroundColour(get_wx_color('text_primary'))
        datetime_sizer.Add(custom_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        # Date picker
        date_picker = wx.adv.DatePickerCtrl(scroll_win, style=wx.adv.DP_DROPDOWN)
        datetime_sizer.Add(date_picker, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        # Time picker (hour:minute)
        time_ctrl = wx.TextCtrl(scroll_win, size=(60, -1))
        time_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        time_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        time_ctrl.SetValue(datetime.now().strftime("%H:%M"))
        datetime_sizer.Add(time_ctrl, 0, wx.ALIGN_CENTER_VERTICAL)

        # Initialize based on existing entry data
        existing_reading_dt = entry['reading_datetime'] if 'reading_datetime' in entry.keys() else None
        if existing_reading_dt and not is_new:
            use_custom_radio.SetValue(True)
            try:
                dt = datetime.fromisoformat(existing_reading_dt)
                wx_date = wx.DateTime()
                wx_date.Set(dt.day, dt.month - 1, dt.year)
                date_picker.SetValue(wx_date)
                time_ctrl.SetValue(dt.strftime("%H:%M"))
            except (ValueError, TypeError) as e:
                logger.debug("Could not parse existing reading datetime: %s", e)
                use_now_radio.SetValue(True)
        else:
            use_now_radio.SetValue(True)

        # Enable/disable date/time controls based on radio selection
        def on_datetime_radio_change(event):
            custom = use_custom_radio.GetValue()
            date_picker.Enable(custom)
            time_ctrl.Enable(custom)

        use_now_radio.Bind(wx.EVT_RADIOBUTTON, on_datetime_radio_change)
        use_custom_radio.Bind(wx.EVT_RADIOBUTTON, on_datetime_radio_change)
        on_datetime_radio_change(None)  # Initial state

        sizer.Add(datetime_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Location
        location_sizer = wx.BoxSizer(wx.HORIZONTAL)

        location_label = wx.StaticText(scroll_win, label="Location:")
        location_label.SetForegroundColour(get_wx_color('text_primary'))
        location_sizer.Add(location_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        location_ctrl = wx.TextCtrl(scroll_win, size=(250, -1))
        location_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        location_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        location_ctrl.SetHint("City, Country or address")
        existing_location = entry['location_name'] if 'location_name' in entry.keys() else None
        if existing_location:
            location_ctrl.SetValue(existing_location)
        location_sizer.Add(location_ctrl, 1, wx.EXPAND | wx.RIGHT, 10)

        # Store lat/lon (hidden, for future astrological data)
        dlg._location_lat = entry['location_lat'] if 'location_lat' in entry.keys() else None
        dlg._location_lon = entry['location_lon'] if 'location_lon' in entry.keys() else None

        sizer.Add(location_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Querent and Reader selection
        profiles = self.db.get_profiles()
        profile_names = ["(None)"] + [p['name'] for p in profiles]
        profile_ids = [None] + [p['id'] for p in profiles]

        people_sizer = wx.BoxSizer(wx.HORIZONTAL)

        querent_label = wx.StaticText(scroll_win, label="Querent:")
        querent_label.SetForegroundColour(get_wx_color('text_primary'))
        people_sizer.Add(querent_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        querent_choice = wx.Choice(scroll_win, choices=profile_names)
        querent_choice.SetSelection(0)
        people_sizer.Add(querent_choice, 0, wx.RIGHT, 20)

        reader_label = wx.StaticText(scroll_win, label="Reader:")
        reader_label.SetForegroundColour(get_wx_color('text_primary'))
        people_sizer.Add(reader_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        reader_choice = wx.Choice(scroll_win, choices=profile_names)
        reader_choice.SetSelection(0)
        people_sizer.Add(reader_choice, 0, wx.RIGHT, 15)

        # "Same as Querent" checkbox (empty label with separate StaticText for macOS)
        same_as_querent_cb = wx.CheckBox(scroll_win, label="")
        people_sizer.Add(same_as_querent_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        same_label = wx.StaticText(scroll_win, label="Reader same as Querent")
        same_label.SetForegroundColour(get_wx_color('text_primary'))
        people_sizer.Add(same_label, 0, wx.ALIGN_CENTER_VERTICAL)

        def on_same_as_querent(event):
            if same_as_querent_cb.GetValue():
                reader_choice.SetSelection(querent_choice.GetSelection())
                reader_choice.Enable(False)
            else:
                reader_choice.Enable(True)

        def on_querent_change(event):
            if same_as_querent_cb.GetValue():
                reader_choice.SetSelection(querent_choice.GetSelection())

        same_as_querent_cb.Bind(wx.EVT_CHECKBOX, on_same_as_querent)
        querent_choice.Bind(wx.EVT_CHOICE, on_querent_change)

        # Load existing querent/reader from entry, or apply defaults for new entries
        existing_querent_id = entry['querent_id'] if 'querent_id' in entry.keys() else None
        existing_reader_id = entry['reader_id'] if 'reader_id' in entry.keys() else None

        if existing_querent_id and existing_querent_id in profile_ids:
            querent_choice.SetSelection(profile_ids.index(existing_querent_id))
        elif is_new:
            # Apply default querent for new entries
            default_querent_id = self.db.get_default_querent()
            if default_querent_id and default_querent_id in profile_ids:
                querent_choice.SetSelection(profile_ids.index(default_querent_id))

        if existing_reader_id and existing_reader_id in profile_ids:
            reader_choice.SetSelection(profile_ids.index(existing_reader_id))
        elif is_new:
            # Apply default reader for new entries
            default_reader_id = self.db.get_default_reader()
            if default_reader_id and default_reader_id in profile_ids:
                reader_choice.SetSelection(profile_ids.index(default_reader_id))

        # Check "same as querent" checkbox
        if existing_querent_id and existing_querent_id == existing_reader_id:
            same_as_querent_cb.SetValue(True)
            on_same_as_querent(None)
        elif is_new and self.db.get_default_reader_same_as_querent():
            same_as_querent_cb.SetValue(True)
            on_same_as_querent(None)

        sizer.Add(people_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Store profile_ids for later use when saving
        dlg._profile_ids = profile_ids

        # Spread/Deck selection
        select_sizer = wx.BoxSizer(wx.HORIZONTAL)

        spread_label = wx.StaticText(scroll_win, label="Spread:")
        spread_label.SetForegroundColour(get_wx_color('text_primary'))
        select_sizer.Add(spread_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        spread_choice = wx.Choice(scroll_win, choices=list(self._spread_map.keys()))
        select_sizer.Add(spread_choice, 0, wx.RIGHT, 20)

        deck_label = wx.StaticText(scroll_win, label="Default Deck:")
        deck_label.SetForegroundColour(get_wx_color('text_primary'))
        select_sizer.Add(deck_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        deck_choice = wx.Choice(scroll_win, choices=list(self._deck_map.keys()))
        select_sizer.Add(deck_choice, 0, wx.RIGHT, 10)

        # Use Any Deck toggle (empty label + StaticText for macOS)
        use_any_sizer = wx.BoxSizer(wx.HORIZONTAL)
        use_any_deck_cb = wx.CheckBox(scroll_win, label="")
        use_any_sizer.Add(use_any_deck_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        use_any_label = wx.StaticText(scroll_win, label="Use Any Deck")
        use_any_label.SetForegroundColour(get_wx_color('text_primary'))
        use_any_sizer.Add(use_any_label, 0, wx.ALIGN_CENTER_VERTICAL)
        select_sizer.Add(use_any_sizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # Hint about multi-deck
        multi_deck_hint = wx.StaticText(scroll_win, label="(You can select different decks per position)")
        multi_deck_hint.SetForegroundColour(get_wx_color('text_dim'))
        multi_deck_hint.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        select_sizer.Add(multi_deck_hint, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(select_sizer, 0, wx.LEFT | wx.RIGHT, 15)

        # Store full deck info for filtering (deck_name -> {id, cartomancy_type})
        dlg._all_decks = {}
        for deck_name, deck_id in self._deck_map.items():
            deck = self.db.get_deck(deck_id)
            dlg._all_decks[deck_name] = {
                'id': deck_id,
                'cartomancy_type': deck['cartomancy_type_name'] if deck else None
            }

        # Spread canvas
        spread_canvas = wx.Panel(scroll_win, size=(-1, 350))
        spread_canvas.SetBackgroundColour(get_wx_color('card_slot'))
        sizer.Add(spread_canvas, 0, wx.EXPAND | wx.ALL, 15)

        # Cards label
        cards_label = wx.StaticText(scroll_win, label="Click positions above to assign cards")
        cards_label.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(cards_label, 0, wx.LEFT, 15)

        # Notes
        notes_label = wx.StaticText(scroll_win, label="Notes:")
        notes_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(notes_label, 0, wx.LEFT | wx.TOP, 15)

        content_ctrl = RichTextPanel(scroll_win, value=entry['content'] or '', min_height=120)
        sizer.Add(content_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Store state for this dialog
        dlg._spread_cards = {}
        dlg._selected_deck_id = None

        # Load existing reading data
        readings = self.db.get_entry_readings(entry_id)
        if readings:
            reading = readings[0]
            if reading['spread_name']:
                idx = spread_choice.FindString(reading['spread_name'])
                if idx != wx.NOT_FOUND:
                    spread_choice.SetSelection(idx)
            if reading['deck_name']:
                for name, did in self._deck_map.items():
                    if reading['deck_name'] in name:
                        idx = deck_choice.FindString(name)
                        if idx != wx.NOT_FOUND:
                            deck_choice.SetSelection(idx)
                            dlg._selected_deck_id = did
                        break
            if reading['cards_used']:
                cards_used = json.loads(reading['cards_used'])
                # Build deck_cards lookup for all decks that might be referenced
                all_deck_cards = {}  # deck_id -> {card_name -> {id, image_path}}
                for did in self._deck_map.values():
                    all_deck_cards[did] = {}
                    for card in self.db.get_cards(did):
                        all_deck_cards[did][card['name']] = {
                            'id': card['id'],
                            'image_path': card['image_path']
                        }

                for i, card_data in enumerate(cards_used):
                    # Handle old format (string), basic dict, and multi-deck format
                    if isinstance(card_data, str):
                        card_name = card_data
                        reversed_state = False
                        card_deck_id = dlg._selected_deck_id
                        card_deck_name = reading['deck_name'] if reading['deck_name'] else ''
                    else:
                        card_name = card_data.get('name', '')
                        reversed_state = card_data.get('reversed', False)
                        # Multi-deck format includes deck_id per card
                        card_deck_id = card_data.get('deck_id', dlg._selected_deck_id)
                        card_deck_name = card_data.get('deck_name', reading['deck_name'] if reading['deck_name'] else '')

                    # Get image path from the card's deck
                    image_path = None
                    card_id = None
                    if card_deck_id and card_deck_id in all_deck_cards:
                        card_info = all_deck_cards[card_deck_id].get(card_name, {})
                        image_path = card_info.get('image_path')
                        card_id = card_info.get('id')

                    dlg._spread_cards[i] = {
                        'id': card_id,
                        'name': card_name,
                        'image_path': image_path,
                        'reversed': reversed_state,
                        'deck_id': card_deck_id,
                        'deck_name': card_deck_name
                    }
        else:
            # For new entries, auto-select default deck if a spread is selected
            spread_name = spread_choice.GetStringSelection()
            if spread_name and spread_name in self._spread_map:
                spread = self.db.get_spread(self._spread_map[spread_name])
                if spread and 'cartomancy_type' in spread.keys() and spread['cartomancy_type']:
                    default_deck_id = self.db.get_default_deck(spread['cartomancy_type'])
                    if default_deck_id:
                        # Find and select the default deck in the deck_choice dropdown
                        for name, did in self._deck_map.items():
                            if did == default_deck_id:
                                idx = deck_choice.FindString(name)
                                if idx != wx.NOT_FOUND:
                                    deck_choice.SetSelection(idx)
                                    dlg._selected_deck_id = did
                                break

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
                # If no restrictions or "use any deck" is checked, show all
                if not allowed_types or use_any_deck_cb.GetValue():
                    deck_choice.Append(deck_name)
                # Otherwise only show decks matching allowed types
                elif deck_info['cartomancy_type'] in allowed_types:
                    deck_choice.Append(deck_name)

            # Try to restore previous selection
            if current_selection:
                idx = deck_choice.FindString(current_selection)
                if idx != wx.NOT_FOUND:
                    deck_choice.SetSelection(idx)

        def on_spread_change(event):
            dlg._spread_cards = {}
            spread_canvas.Refresh()

            spread_name = spread_choice.GetStringSelection()
            allowed_types = None

            if spread_name and spread_name in self._spread_map:
                spread = self.db.get_spread(self._spread_map[spread_name])
                if spread:
                    # Check for allowed_deck_types (new format)
                    allowed_types_json = spread['allowed_deck_types'] if 'allowed_deck_types' in spread.keys() else None
                    if allowed_types_json:
                        allowed_types = json.loads(allowed_types_json)

                    # Filter deck choices based on allowed types
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
                    # Fall back to old cartomancy_type field
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
                        # No restrictions - show all decks
                        update_deck_choices(None)

            # Store allowed types for card picker
            dlg._spread_allowed_types = allowed_types

        spread_choice.Bind(wx.EVT_CHOICE, on_spread_change)

        def on_use_any_deck_change(event):
            """Re-filter decks when 'use any deck' is toggled"""
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

            # Calculate spread bounding box for centering
            if positions:
                min_x = min(p.get('x', 0) for p in positions)
                min_y = min(p.get('y', 0) for p in positions)
                max_x = max(p.get('x', 0) + p.get('width', 80) for p in positions)
                max_y = max(p.get('y', 0) + p.get('height', 120) for p in positions)
                spread_width = max_x - min_x
                spread_height = max_y - min_y

                # Calculate offset to center the spread
                canvas_w, canvas_h = spread_canvas.GetSize()
                offset_x = (canvas_w - spread_width) // 2 - min_x
                offset_y = (canvas_h - spread_height) // 2 - min_y
            else:
                offset_x, offset_y = 0, 0

            for i, pos in enumerate(positions):
                x, y = pos.get('x', 0) + offset_x, pos.get('y', 0) + offset_y
                w, h = pos.get('width', 80), pos.get('height', 120)
                label = pos.get('label', f'Position {i+1}')
                is_position_rotated = pos.get('rotated', False)

                if i in dlg._spread_cards:
                    card_data = dlg._spread_cards[i]
                    image_path = card_data.get('image_path')
                    image_drawn = False

                    is_reversed = card_data.get('reversed', False)
                    wx_img = load_for_spread_display(
                        image_path, (w, h),
                        is_reversed=is_reversed,
                        is_position_rotated=is_position_rotated
                    )
                    if wx_img:
                        target_w, target_h = wx_img.GetWidth(), wx_img.GetHeight()
                        bmp = wx.Bitmap(wx_img)
                        img_x = x + (w - target_w) // 2
                        img_y = y + (h - target_h) // 2
                        dc.DrawBitmap(bmp, img_x, img_y)
                        dc.SetBrush(wx.TRANSPARENT_BRUSH)
                        dc.SetPen(wx.Pen(get_wx_color('accent'), 2))
                        dc.DrawRectangle(img_x - 1, img_y - 1, target_w + 2, target_h + 2)

                        # Add (R) indicator for reversed cards
                        if is_reversed:
                            dc.SetTextForeground(get_wx_color('accent'))
                            dc.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                            dc.DrawText("(R)", img_x + 2, img_y + 2)

                        image_drawn = True

                    if not image_drawn:
                        dc.SetBrush(wx.Brush(get_wx_color('accent_dim')))
                        dc.SetPen(wx.Pen(get_wx_color('border'), 2))
                        dc.DrawRectangle(x, y, w, h)
                        dc.SetTextForeground(get_wx_color('text_primary'))
                        dc.DrawText(card_data.get('name', label)[:12], x + 5, y + h//2 - 8)
                else:
                    dc.SetBrush(wx.Brush(get_wx_color('bg_tertiary')))
                    dc.SetPen(wx.Pen(get_wx_color('border'), 2))
                    dc.DrawRectangle(x, y, w, h)
                    dc.SetTextForeground(get_wx_color('text_secondary'))
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

            # Calculate offset for centered spread (same as paint function)
            if positions:
                min_x = min(p.get('x', 0) for p in positions)
                min_y = min(p.get('y', 0) for p in positions)
                max_x = max(p.get('x', 0) + p.get('width', 80) for p in positions)
                max_y = max(p.get('y', 0) + p.get('height', 120) for p in positions)
                spread_width = max_x - min_x
                spread_height = max_y - min_y
                canvas_w, canvas_h = spread_canvas.GetSize()
                offset_x = (canvas_w - spread_width) // 2 - min_x
                offset_y = (canvas_h - spread_height) // 2 - min_y
            else:
                offset_x, offset_y = 0, 0

            click_x, click_y = event.GetX(), event.GetY()

            for i, pos in enumerate(positions):
                px, py = pos.get('x', 0) + offset_x, pos.get('y', 0) + offset_y
                pw, ph = pos.get('width', 80), pos.get('height', 120)

                if px <= click_x <= px + pw and py <= click_y <= py + ph:
                    # Create a card picker dialog with deck selection
                    self._show_card_picker_dialog(
                        dlg, i, pos, spread_canvas, cards_label,
                        use_any_deck_cb, deck_choice
                    )
                    break

        def on_canvas_right_click(event):
            spread_name = spread_choice.GetStringSelection()
            if not spread_name or spread_name not in self._spread_map:
                return

            spread = self.db.get_spread(self._spread_map[spread_name])
            if not spread:
                return

            positions = json.loads(spread['positions'])
            click_x, click_y = event.GetX(), event.GetY()

            for i, pos in enumerate(positions):
                px, py = pos.get('x', 0), pos.get('y', 0)
                pw, ph = pos.get('width', 80), pos.get('height', 120)

                if px <= click_x <= px + pw and py <= click_y <= py + ph:
                    # Check if there's a card in this position
                    if i in dlg._spread_cards:
                        # Create context menu
                        menu = wx.Menu()
                        is_reversed = dlg._spread_cards[i].get('reversed', False)

                        toggle_item = menu.Append(wx.ID_ANY, "Upright" if is_reversed else "Reversed")
                        remove_item = menu.Append(wx.ID_ANY, "Remove Card")

                        def on_toggle(e):
                            dlg._spread_cards[i]['reversed'] = not dlg._spread_cards[i].get('reversed', False)
                            spread_canvas.Refresh()

                        def on_remove(e):
                            del dlg._spread_cards[i]
                            if dlg._spread_cards:
                                names = [c['name'] for c in dlg._spread_cards.values()]
                                cards_label.SetLabel(f"Cards: {', '.join(names)}")
                            else:
                                cards_label.SetLabel("Cards: None")
                            spread_canvas.Refresh()

                        spread_canvas.Bind(wx.EVT_MENU, on_toggle, toggle_item)
                        spread_canvas.Bind(wx.EVT_MENU, on_remove, remove_item)

                        spread_canvas.PopupMenu(menu)
                        menu.Destroy()
                    break

        spread_canvas.Bind(wx.EVT_LEFT_DOWN, on_canvas_click)
        spread_canvas.Bind(wx.EVT_RIGHT_DOWN, on_canvas_right_click)

        # Set the scroll window sizer
        scroll_win.SetSizer(sizer)

        # Add scroll window to main sizer
        main_sizer.Add(scroll_win, 1, wx.EXPAND)

        # Buttons (outside scroll area so always visible)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Save")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        dlg.SetSizer(main_sizer)

        if dlg.ShowModal() == wx.ID_OK:
            # Save the entry
            title = title_ctrl.GetValue()
            content = content_ctrl.GetValue()

            # Get reading datetime
            if use_now_radio.GetValue():
                reading_datetime = datetime.now().isoformat()
            else:
                wx_date = date_picker.GetValue()
                time_str = time_ctrl.GetValue().strip()
                try:
                    hour, minute = map(int, time_str.split(':'))
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse time '%s': %s", time_str, e)
                    hour, minute = 12, 0
                reading_datetime = datetime(
                    wx_date.GetYear(),
                    wx_date.GetMonth() + 1,
                    wx_date.GetDay(),
                    hour, minute
                ).isoformat()

            # Get location
            location_name = location_ctrl.GetValue().strip() or None
            location_lat = dlg._location_lat
            location_lon = dlg._location_lon

            # Get querent and reader
            querent_idx = querent_choice.GetSelection()
            reader_idx = reader_choice.GetSelection()
            querent_id = dlg._profile_ids[querent_idx] if querent_idx > 0 else None
            reader_id = dlg._profile_ids[reader_idx] if reader_idx > 0 else None
            # Use 0 as sentinel for "clear" vs None for "don't update"
            querent_id_param = querent_id if querent_id else 0
            reader_id_param = reader_id if reader_id else 0

            self.db.update_entry(
                entry_id,
                title=title,
                content=content,
                reading_datetime=reading_datetime,
                location_name=location_name,
                location_lat=location_lat,
                location_lon=location_lon,
                querent_id=querent_id_param,
                reader_id=reader_id_param
            )

            # Save reading
            self.db.delete_entry_readings(entry_id)

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

                # Save cards with reversed state, deck info, and position index
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

                self.db.add_entry_reading(
                    entry_id=entry_id,
                    spread_id=spread_id,
                    spread_name=spread_name,
                    deck_id=deck_id,
                    deck_name=deck_name_clean,
                    cartomancy_type=cartomancy_type,
                    cards_used=cards_used
                )

            self._refresh_entries_list()
            self.current_entry_id = entry_id
            self._display_entry_in_viewer(entry_id)
        else:
            # If cancelled and was new entry, delete it
            if is_new:
                self.db.delete_entry(entry_id)

        dlg.Destroy()

    def _show_card_picker_dialog(self, dlg, position_index, pos, spread_canvas, cards_label,
                                  use_any_deck_cb, deck_choice):
        """Show the card picker dialog for a spread position"""
        card_dlg = wx.Dialog(dlg, title=f"Select Card for: {pos.get('label', f'Position {position_index+1}')}",
                            size=(450, 550))
        card_dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        card_dlg_sizer = wx.BoxSizer(wx.VERTICAL)

        # Deck selector
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
        # Pre-select the default deck
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

        # Populate cards from selected deck with thumbnails
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

        # Initial populate
        current_picker_deck_id = dlg._selected_deck_id
        populate_cards(current_picker_deck_id)

        def on_picker_deck_change(e):
            nonlocal current_picker_deck_id
            name = picker_deck_choice.GetStringSelection()
            if name in dlg._all_decks:
                current_picker_deck_id = dlg._all_decks[name]['id']
                populate_cards(current_picker_deck_id)

        picker_deck_choice.Bind(wx.EVT_CHOICE, on_picker_deck_change)

        def on_picker_use_any_change(e):
            """Re-filter deck choices when 'use any deck' is toggled in picker"""
            nonlocal current_picker_deck_id
            current_selection = picker_deck_choice.GetStringSelection()
            picker_deck_choice.Clear()

            picker_use_any = picker_use_any_cb.GetValue()
            for deck_name, deck_info in dlg._all_decks.items():
                if not allowed_types or picker_use_any:
                    picker_deck_choice.Append(deck_name)
                elif deck_info['cartomancy_type'] in allowed_types:
                    picker_deck_choice.Append(deck_name)

            # Try to restore selection
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

        # Buttons
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

                # Update cards label
                if dlg._spread_cards:
                    names = [c['name'] for c in dlg._spread_cards.values()]
                    cards_label.SetLabel(f"Cards: {', '.join(names)}")

                spread_canvas.Refresh()
        card_dlg.Destroy()
