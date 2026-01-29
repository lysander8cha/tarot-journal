"""Entry viewer and follow-up notes for the journal panel."""

import json
from datetime import datetime

import wx

from ui_helpers import logger, get_wx_color
from rich_text_panel import RichTextPanel, RichTextViewer
from image_utils import load_and_scale_image, load_for_spread_display


class EntryViewerMixin:
    """Mixin providing entry viewer and follow-up notes functionality."""

    def _display_entry_in_viewer(self, entry_id):
        """Display an entry in the right panel viewer"""
        # Clear existing content
        self.viewer_sizer.Clear(True)

        entry = self.db.get_entry(entry_id)
        if not entry:
            placeholder = wx.StaticText(self.viewer_panel, label="Entry not found")
            placeholder.SetForegroundColour(get_wx_color('text_secondary'))
            self.viewer_sizer.Add(placeholder, 0, wx.ALL, 20)
            self.viewer_panel.Layout()
            return

        # Title
        title = wx.StaticText(self.viewer_panel, label=entry['title'] or "Untitled")
        title.SetForegroundColour(get_wx_color('text_primary'))
        title.SetFont(wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.viewer_sizer.Add(title, 0, wx.ALL, 15)

        # Date/Time and Location
        reading_dt = entry['reading_datetime'] if 'reading_datetime' in entry.keys() else None
        if reading_dt:
            try:
                dt = datetime.fromisoformat(reading_dt)
                date_str = dt.strftime('%B %d, %Y at %I:%M %p')
            except (ValueError, TypeError) as e:
                logger.debug("Could not parse reading datetime: %s", e)
                date_str = reading_dt[:16] if reading_dt else ''
        elif entry['created_at']:
            try:
                dt = datetime.fromisoformat(entry['created_at'])
                date_str = dt.strftime('%B %d, %Y at %I:%M %p')
            except (ValueError, TypeError) as e:
                logger.debug("Could not parse entry created_at: %s", e)
                date_str = entry['created_at'][:16]
        else:
            date_str = None

        if date_str:
            date_label = wx.StaticText(self.viewer_panel, label=date_str)
            date_label.SetForegroundColour(get_wx_color('text_secondary'))
            self.viewer_sizer.Add(date_label, 0, wx.LEFT | wx.BOTTOM, 5)

        # Location
        location_name = entry['location_name'] if 'location_name' in entry.keys() else None
        if location_name:
            location_label = wx.StaticText(self.viewer_panel, label=f"Location: {location_name}")
            location_label.SetForegroundColour(get_wx_color('text_secondary'))
            self.viewer_sizer.Add(location_label, 0, wx.LEFT | wx.BOTTOM, 5)

        # Querent and Reader
        querent_id = entry['querent_id'] if 'querent_id' in entry.keys() else None
        reader_id = entry['reader_id'] if 'reader_id' in entry.keys() else None

        people_parts = []
        if querent_id:
            querent = self.db.get_profile(querent_id)
            if querent:
                people_parts.append(f"Querent: {querent['name']}")
        if reader_id:
            reader = self.db.get_profile(reader_id)
            if reader:
                if reader_id == querent_id:
                    people_parts.append("(also Reader)")
                else:
                    people_parts.append(f"Reader: {reader['name']}")

        if people_parts:
            people_label = wx.StaticText(self.viewer_panel, label=" ".join(people_parts))
            people_label.SetForegroundColour(get_wx_color('text_secondary'))
            self.viewer_sizer.Add(people_label, 0, wx.LEFT | wx.BOTTOM, 15)
        elif location_name:
            # Add extra spacing after location if no people info
            self.viewer_sizer.AddSpacer(10)
        else:
            # Add spacing if no location and no people
            self.viewer_sizer.AddSpacer(10)

        # Reading info - display all readings
        readings = self.db.get_entry_readings(entry_id)
        for reading_idx, reading in enumerate(readings):
            # Add separator between multiple readings
            if reading_idx > 0:
                sep = wx.StaticLine(self.viewer_panel)
                self.viewer_sizer.Add(sep, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 15)
                reading_label = wx.StaticText(self.viewer_panel, label=f"Reading {reading_idx + 1}")
                reading_label.SetForegroundColour(get_wx_color('accent'))
                reading_label.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                self.viewer_sizer.Add(reading_label, 0, wx.LEFT | wx.BOTTOM, 15)

            # Spread and deck info
            info_parts = []
            if reading['spread_name']:
                info_parts.append(f"Spread: {reading['spread_name']}")
            if reading['deck_name']:
                info_parts.append(f"Deck: {reading['deck_name']}")

            if info_parts:
                info_label = wx.StaticText(self.viewer_panel, label=" • ".join(info_parts))
                info_label.SetForegroundColour(get_wx_color('text_secondary'))
                self.viewer_sizer.Add(info_label, 0, wx.LEFT | wx.BOTTOM, 15)

            # Cards in spread layout
            if reading['cards_used']:
                cards_used = json.loads(reading['cards_used'])

                # Build lookup for all decks (multi-deck support)
                # deck_id -> {card_name -> {image_path, card_id}}
                all_deck_cards = {}
                for name, did in self._deck_map.items():
                    all_deck_cards[did] = {}
                    for card in self.db.get_cards(did):
                        all_deck_cards[did][card['name']] = {
                            'image_path': card['image_path'],
                            'card_id': card['id']
                        }

                # Also build legacy lookup for backwards compatibility
                deck_cards = {}  # card_name -> image_path
                deck_card_ids = {}  # card_name -> card_id
                default_deck_id = None
                if reading['deck_name']:
                    for name, did in self._deck_map.items():
                        if reading['deck_name'] in name:
                            default_deck_id = did
                            for card in self.db.get_cards(did):
                                deck_cards[card['name']] = card['image_path']
                                deck_card_ids[card['name']] = card['id']
                            break

                def get_card_info(card_data, card_name):
                    """Get image_path and card_id for a card, handling multi-deck format"""
                    # Check if card has deck_id (multi-deck format)
                    if isinstance(card_data, dict) and card_data.get('deck_id'):
                        card_deck_id = card_data['deck_id']
                        if card_deck_id in all_deck_cards:
                            info = all_deck_cards[card_deck_id].get(card_name, {})
                            return info.get('image_path'), info.get('card_id')
                    # Fall back to legacy lookup
                    return deck_cards.get(card_name), deck_card_ids.get(card_name)

                # Get spread positions
                spread_positions = []
                if reading['spread_name'] and reading['spread_name'] in self._spread_map:
                    spread = self.db.get_spread(self._spread_map[reading['spread_name']])
                    if spread:
                        spread_positions = json.loads(spread['positions'])

                # Create spread display
                if spread_positions:
                    self._display_spread_layout(
                        spread_positions, cards_used, get_card_info
                    )
                else:
                    # No spread - show cards in a row
                    self._display_cards_row(cards_used, get_card_info)

        # Add Reading button
        add_reading_btn = wx.Button(self.viewer_panel, label="+ Add Another Reading")
        add_reading_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_add_reading(entry_id))
        self.viewer_sizer.Add(add_reading_btn, 0, wx.LEFT | wx.BOTTOM, 15)

        # Notes
        if entry['content']:
            notes_label = wx.StaticText(self.viewer_panel, label="Notes:")
            notes_label.SetForegroundColour(get_wx_color('accent'))
            notes_label.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            self.viewer_sizer.Add(notes_label, 0, wx.LEFT, 15)

            notes_viewer = RichTextViewer(self.viewer_panel, value=entry['content'], min_height=60)
            self.viewer_sizer.Add(notes_viewer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Follow-up Notes
        follow_up_notes = self.db.get_follow_up_notes(entry_id)

        follow_up_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        follow_up_label = wx.StaticText(self.viewer_panel, label="Follow-up Notes:")
        follow_up_label.SetForegroundColour(get_wx_color('accent'))
        follow_up_label.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        follow_up_header_sizer.Add(follow_up_label, 0, wx.ALIGN_CENTER_VERTICAL)

        add_follow_up_btn = wx.Button(self.viewer_panel, label="+ Add Note", size=(80, -1))
        add_follow_up_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_add_follow_up_note(entry_id))
        follow_up_header_sizer.Add(add_follow_up_btn, 0, wx.LEFT, 15)

        self.viewer_sizer.Add(follow_up_header_sizer, 0, wx.LEFT | wx.TOP, 15)

        if follow_up_notes:
            for note in follow_up_notes:
                note_panel = wx.Panel(self.viewer_panel)
                note_panel.SetBackgroundColour(get_wx_color('bg_tertiary'))
                note_sizer = wx.BoxSizer(wx.VERTICAL)

                # Date header
                try:
                    dt = datetime.fromisoformat(note['created_at'])
                    date_str = dt.strftime('%B %d, %Y at %I:%M %p')
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse note date: %s", e)
                    date_str = note['created_at'][:16] if note['created_at'] else 'Unknown date'

                date_label = wx.StaticText(note_panel, label=date_str)
                date_label.SetForegroundColour(get_wx_color('text_dim'))
                date_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
                note_sizer.Add(date_label, 0, wx.ALL, 8)

                # Note content
                note_viewer = RichTextViewer(note_panel, value=note['content'], min_height=40)
                note_sizer.Add(note_viewer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

                # Edit/Delete buttons
                btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
                edit_btn = wx.Button(note_panel, label="Edit", size=(50, -1))
                edit_btn.Bind(wx.EVT_BUTTON, lambda e, nid=note['id'], eid=entry_id: self._on_edit_follow_up_note(nid, eid))
                delete_btn = wx.Button(note_panel, label="Delete", size=(50, -1))
                delete_btn.Bind(wx.EVT_BUTTON, lambda e, nid=note['id'], eid=entry_id: self._on_delete_follow_up_note(nid, eid))
                btn_sizer.Add(edit_btn, 0, wx.RIGHT, 5)
                btn_sizer.Add(delete_btn, 0)
                note_sizer.Add(btn_sizer, 0, wx.LEFT | wx.BOTTOM, 8)

                note_panel.SetSizer(note_sizer)
                self.viewer_sizer.Add(note_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)
        else:
            no_notes_label = wx.StaticText(self.viewer_panel, label="No follow-up notes yet")
            no_notes_label.SetForegroundColour(get_wx_color('text_dim'))
            self.viewer_sizer.Add(no_notes_label, 0, wx.LEFT | wx.TOP, 15)

        self.viewer_sizer.AddSpacer(15)

        # Tags
        entry_tags = self.db.get_entry_tags(entry_id)
        if entry_tags:
            tags_label = wx.StaticText(self.viewer_panel, label="Tags:")
            tags_label.SetForegroundColour(get_wx_color('accent'))
            tags_label.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            self.viewer_sizer.Add(tags_label, 0, wx.LEFT, 15)

            tag_names = [t['name'] for t in entry_tags]
            tags_text = wx.StaticText(self.viewer_panel, label=", ".join(tag_names))
            tags_text.SetForegroundColour(get_wx_color('text_secondary'))
            self.viewer_sizer.Add(tags_text, 0, wx.LEFT | wx.BOTTOM, 15)

        self.viewer_panel.Layout()
        self.viewer_panel.SetupScrolling()

    def _display_spread_layout(self, spread_positions, cards_used, get_card_info):
        """Display cards in a spread layout"""
        # Calculate bounding box of the spread
        min_x = min(p.get('x', 0) for p in spread_positions)
        min_y = min(p.get('y', 0) for p in spread_positions)
        max_x = max(p.get('x', 0) + p.get('width', 80) for p in spread_positions)
        max_y = max(p.get('y', 0) + p.get('height', 120) for p in spread_positions)
        spread_width = max_x - min_x
        spread_height = max_y - min_y

        # Panel size with padding, offset to center
        panel_padding = 20
        panel_width = spread_width + panel_padding * 2
        panel_height = spread_height + panel_padding * 2
        offset_x = panel_padding - min_x
        offset_y = panel_padding - min_y

        # Create container for spread and legend
        spread_container = wx.Panel(self.viewer_panel)
        spread_container.SetBackgroundColour(get_wx_color('bg_primary'))
        spread_container_sizer = wx.BoxSizer(wx.VERTICAL)

        # Legend toggle button with label
        toggle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        legend_toggle = wx.CheckBox(spread_container, label="")
        toggle_sizer.Add(legend_toggle, 0, wx.RIGHT, 5)

        legend_label = wx.StaticText(spread_container, label="Show Position Legend")
        legend_label.SetForegroundColour(get_wx_color('text_primary'))
        toggle_sizer.Add(legend_label, 0, wx.ALIGN_CENTER_VERTICAL)

        legend_toggle.SetValue(False)
        spread_container_sizer.Add(toggle_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 5)

        # Horizontal layout for spread and legend
        spread_legend_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Spread panel
        spread_panel = wx.Panel(spread_container, size=(panel_width, panel_height))
        spread_panel.SetBackgroundColour(get_wx_color('card_slot'))

        # Store references for legend toggle
        spread_panel._position_labels = []
        spread_panel._position_numbers = []

        for i, pos in enumerate(spread_positions):
            x, y = pos.get('x', 0) + offset_x, pos.get('y', 0) + offset_y
            w, h = pos.get('width', 80), pos.get('height', 120)
            label = pos.get('label', f'Position {i+1}')
            is_position_rotated = pos.get('rotated', False)

            # Find card for this position - check position_index first, fall back to array index
            card_data = None
            for cd in cards_used:
                if isinstance(cd, dict) and cd.get('position_index') == i:
                    card_data = cd
                    break
            # Fall back to array index for old entries without position_index
            if card_data is None and i < len(cards_used):
                cd = cards_used[i]
                # Only use array index if no position_index fields exist in any card
                if not any(isinstance(c, dict) and 'position_index' in c for c in cards_used):
                    card_data = cd

            if card_data is not None:
                # Handle both old format (string) and new format (dict)
                if isinstance(card_data, str):
                    card_name = card_data
                    is_reversed = False
                else:
                    card_name = card_data.get('name', '')
                    is_reversed = card_data.get('reversed', False)

                # Get image path and card ID using multi-deck aware function
                image_path, card_id = get_card_info(card_data, card_name)
                image_placed = False

                wx_img = load_for_spread_display(
                    image_path, (w, h),
                    is_reversed=is_reversed,
                    is_position_rotated=is_position_rotated
                )
                if wx_img:
                    target_w, target_h = wx_img.GetWidth(), wx_img.GetHeight()
                    bmp = wx.StaticBitmap(spread_panel, bitmap=wx.Bitmap(wx_img))
                    img_x = x + (w - target_w) // 2
                    img_y = y + (h - target_h) // 2
                    bmp.SetPosition((img_x, img_y))

                    # Add tooltip with card name and position
                    tooltip_text = f"{card_name} - {label}"
                    if is_reversed:
                        tooltip_text += " (Reversed)"
                    bmp.SetToolTip(tooltip_text)

                    # Add double-click to open card info
                    if card_id:
                        bmp.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))

                    # Add (R) indicator for reversed cards
                    if is_reversed:
                        r_label = wx.StaticText(spread_panel, label="(R)")
                        r_label.SetForegroundColour(get_wx_color('accent'))
                        r_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                        r_label.SetPosition((img_x + 2, y + 4))
                        if card_id:
                            r_label.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))

                    image_placed = True

                if not image_placed:
                    slot = wx.Panel(spread_panel, size=(w, h))
                    slot.SetPosition((x, y))
                    slot.SetBackgroundColour(get_wx_color('accent_dim'))
                    slot_label = wx.StaticText(slot, label=card_name[:12])
                    slot_label.SetForegroundColour(get_wx_color('text_primary'))
                    slot_label.SetPosition((5, h//2 - 8))

                    # Add tooltip with card name and position
                    tooltip_text = f"{card_name} - {label}"
                    if is_reversed:
                        tooltip_text += " (Reversed)"
                    slot.SetToolTip(tooltip_text)

                    # Add double-click to open card info
                    if card_id:
                        slot.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))
                        slot_label.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))

                # Add position number (hidden by default)
                pos_num = wx.StaticText(spread_panel, label=str(i + 1))
                pos_num.SetForegroundColour(get_wx_color('text_secondary'))
                pos_num.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                pos_num.SetPosition((x - 12, y - 12))
                pos_num.Hide()
                spread_panel._position_numbers.append(pos_num)
            else:
                slot = wx.Panel(spread_panel, size=(w, h))
                slot.SetPosition((x, y))
                slot.SetBackgroundColour(get_wx_color('bg_tertiary'))
                slot_label = wx.StaticText(slot, label=label)
                slot_label.SetForegroundColour(get_wx_color('text_secondary'))
                slot_label.SetPosition((5, h//2 - 8))

                # Add position number for empty slots too
                pos_num = wx.StaticText(spread_panel, label=str(i + 1))
                pos_num.SetForegroundColour(get_wx_color('text_secondary'))
                pos_num.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                pos_num.SetPosition((x - 12, y - 12))
                pos_num.Hide()
                spread_panel._position_numbers.append(pos_num)

        spread_legend_sizer.Add(spread_panel, 0, wx.ALL, 5)

        # Create legend panel (hidden by default)
        legend_panel = wx.Panel(spread_container)
        legend_panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        legend_sizer = wx.BoxSizer(wx.VERTICAL)

        legend_title = wx.StaticText(legend_panel, label="Position Legend:")
        legend_title.SetForegroundColour(get_wx_color('text_primary'))
        legend_title.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        legend_sizer.Add(legend_title, 0, wx.ALL, 5)

        for i, pos in enumerate(spread_positions):
            label = pos.get('label', f'Position {i+1}')
            legend_item = wx.StaticText(legend_panel, label=f"{i + 1}. {label}")
            legend_item.SetForegroundColour(get_wx_color('text_primary'))
            legend_item.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            legend_sizer.Add(legend_item, 0, wx.LEFT | wx.BOTTOM, 5)

        legend_panel.SetSizer(legend_sizer)
        legend_panel.Hide()
        spread_legend_sizer.Add(legend_panel, 0, wx.ALL, 5)

        spread_container_sizer.Add(spread_legend_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL, 0)

        # Toggle handler
        def on_legend_toggle(event):
            show = legend_toggle.GetValue()
            legend_panel.Show(show)
            for num in spread_panel._position_numbers:
                num.Show(show)
            spread_container.Layout()
            self.viewer_panel.Layout()
            self.viewer_panel.SetupScrolling()

        legend_toggle.Bind(wx.EVT_CHECKBOX, on_legend_toggle)

        spread_container.SetSizer(spread_container_sizer)
        self.viewer_sizer.Add(spread_container, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 15)

    def _display_cards_row(self, cards_used, get_card_info):
        """Display cards in a simple row layout"""
        cards_sizer = wx.WrapSizer(wx.HORIZONTAL)
        for card_info in cards_used:
            # Handle both old format (string) and new format (dict)
            if isinstance(card_info, str):
                card_name = card_info
                is_reversed = False
            else:
                card_name = card_info.get('name', '')
                is_reversed = card_info.get('reversed', False)

            # Get image path and card ID using multi-deck aware function
            image_path, card_id = get_card_info(card_info, card_name)

            card_panel = wx.Panel(self.viewer_panel, size=(90, 140))
            card_panel.SetBackgroundColour(get_wx_color('bg_tertiary'))
            card_sizer_inner = wx.BoxSizer(wx.VERTICAL)

            # Add tooltip with card name
            tooltip_text = card_name
            if is_reversed:
                tooltip_text += " (Reversed)"
            card_panel.SetToolTip(tooltip_text)

            # Add double-click to open card info
            if card_id:
                card_panel.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))

            wx_bitmap = load_and_scale_image(image_path, (80, 110), as_wx_bitmap=True)
            if wx_bitmap:
                bmp = wx.StaticBitmap(card_panel, bitmap=wx_bitmap)
                card_sizer_inner.Add(bmp, 0, wx.ALL | wx.ALIGN_CENTER, 2)
                # Bind double-click on image too
                if card_id:
                    bmp.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))

            name_label = wx.StaticText(card_panel, label=card_name[:15])
            name_label.SetForegroundColour(get_wx_color('text_primary'))
            name_label.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            card_sizer_inner.Add(name_label, 0, wx.ALL | wx.ALIGN_CENTER, 2)
            # Bind double-click on label too
            if card_id:
                name_label.Bind(wx.EVT_LEFT_DCLICK, lambda e, cid=card_id: self._on_view_card(None, cid))

            card_panel.SetSizer(card_sizer_inner)
            cards_sizer.Add(card_panel, 0, wx.ALL, 5)

        self.viewer_sizer.Add(cards_sizer, 0, wx.LEFT | wx.BOTTOM, 15)

    def _on_add_follow_up_note(self, entry_id):
        """Add a follow-up note to an entry"""
        dlg = wx.Dialog(self, title="Add Follow-up Note", size=(500, 300))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Instructions
        instr_label = wx.StaticText(dlg, label="Add a follow-up note to record how this reading played out:")
        instr_label.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(instr_label, 0, wx.ALL, 15)

        # Note content
        note_ctrl = RichTextPanel(dlg, value='', min_height=150)
        sizer.Add(note_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # Date note
        date_note = wx.StaticText(dlg, label=f"This note will be dated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        date_note.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(date_note, 0, wx.ALL, 15)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Add Note")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            content = note_ctrl.GetValue().strip()
            if content:
                self.db.add_follow_up_note(entry_id, content)
                self._display_entry_in_viewer(entry_id)

        dlg.Destroy()

    def _on_edit_follow_up_note(self, note_id, entry_id):
        """Edit a follow-up note"""
        # Get the current note content
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT * FROM follow_up_notes WHERE id = ?', (note_id,))
        note = cursor.fetchone()
        if not note:
            return

        dlg = wx.Dialog(self, title="Edit Follow-up Note", size=(500, 300))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Date label
        try:
            dt = datetime.fromisoformat(note['created_at'])
            date_str = dt.strftime('%B %d, %Y at %I:%M %p')
        except (ValueError, TypeError) as e:
            logger.debug("Could not parse note date: %s", e)
            date_str = note['created_at'][:16] if note['created_at'] else 'Unknown date'

        date_label = wx.StaticText(dlg, label=f"Note from: {date_str}")
        date_label.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(date_label, 0, wx.ALL, 15)

        # Note content
        note_ctrl = RichTextPanel(dlg, value=note['content'], min_height=150)
        sizer.Add(note_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Save")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            content = note_ctrl.GetValue().strip()
            if content:
                self.db.update_follow_up_note(note_id, content)
                self._display_entry_in_viewer(entry_id)

        dlg.Destroy()

    def _on_delete_follow_up_note(self, note_id, entry_id):
        """Delete a follow-up note"""
        result = wx.MessageBox(
            "Delete this follow-up note?",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_WARNING
        )
        if result == wx.YES:
            self.db.delete_follow_up_note(note_id)
            self._display_entry_in_viewer(entry_id)
