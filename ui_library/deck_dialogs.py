"""Deck editing dialogs for the library panel."""

import json

import wx
import wx.lib.scrolledpanel as scrolled
import wx.lib.agw.flatnotebook as fnb

from ui_helpers import logger, _cfg, get_wx_color
from rich_text_panel import RichTextPanel
from image_utils import load_and_scale_image


class DeckDialogsMixin:
    """Mixin providing deck editing dialogs."""

    def _on_add_deck(self, event):
        """Add a new deck"""
        dlg = wx.TextEntryDialog(self, "Deck name:", "Add Deck")
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetValue().strip()
            if name:
                type_dlg = wx.SingleChoiceDialog(self, "Deck type:", "Select Type", ['Tarot', 'Lenormand', 'Oracle'])
                if type_dlg.ShowModal() == wx.ID_OK:
                    type_name = type_dlg.GetStringSelection()
                    types = self.db.get_cartomancy_types()
                    type_id = None
                    for t in types:
                        if t['name'] == type_name:
                            type_id = t['id']
                            break
                    if type_id:
                        self.db.add_deck(name, type_id)
                        self._refresh_decks_list()
                type_dlg.Destroy()
        dlg.Destroy()

    def _on_edit_deck(self, event):
        """Edit deck name, suit names, and custom fields"""
        # Get deck_id based on current view mode
        deck_id = None
        if self._deck_view_mode == 'image':
            # In image view, use _selected_deck_id
            deck_id = self._selected_deck_id
        else:
            # In list view, use list selection
            idx = self.deck_list.GetFirstSelected()
            if idx != -1:
                deck_id = self.deck_list.GetItemData(idx)

        if not deck_id:
            wx.MessageBox("Select a deck to edit.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        deck = self.db.get_deck(deck_id)
        if not deck:
            return

        suit_names = self.db.get_deck_suit_names(deck_id)
        custom_fields = [dict(row) for row in self.db.get_deck_custom_fields(deck_id)]

        dlg = wx.Dialog(self, title="Edit Deck", size=(650, 520), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook for tabs using FlatNotebook for better color control
        style = (fnb.FNB_NO_X_BUTTON | fnb.FNB_NO_NAV_BUTTONS | fnb.FNB_NODRAG)
        notebook = fnb.FlatNotebook(dlg, agwStyle=style)
        notebook.SetBackgroundColour(get_wx_color('bg_primary'))
        notebook.SetTabAreaColour(get_wx_color('bg_primary'))
        notebook.SetActiveTabColour(get_wx_color('bg_tertiary'))
        notebook.SetNonActiveTabTextColour(get_wx_color('text_primary'))
        notebook.SetActiveTabTextColour(get_wx_color('text_primary'))
        notebook.SetGradientColourTo(get_wx_color('bg_tertiary'))
        notebook.SetGradientColourFrom(get_wx_color('bg_secondary'))

        # === General Tab ===
        general_panel = wx.Panel(notebook)
        general_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        general_sizer = wx.BoxSizer(wx.VERTICAL)

        # Deck name
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(general_panel, label="Deck Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        name_ctrl = wx.TextCtrl(general_panel, value=deck['name'])
        name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_ctrl, 1)
        general_sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 15)

        # Suit names section - use appropriate suits based on deck type
        deck_type = deck['cartomancy_type_name']
        if deck_type in ('Lenormand', 'Playing Cards'):
            suits = [('hearts', 'Hearts'), ('diamonds', 'Diamonds'),
                     ('clubs', 'Clubs'), ('spades', 'Spades')]
            suit_box_label = "Suit Names (for Playing Card decks)"
        else:  # Tarot or Oracle
            suits = [('wands', 'Wands'), ('cups', 'Cups'),
                     ('swords', 'Swords'), ('pentacles', 'Pentacles')]
            suit_box_label = "Suit Names (for Tarot decks)"

        suit_box = wx.StaticBox(general_panel, label=suit_box_label)
        suit_box.SetForegroundColour(get_wx_color('accent'))
        suit_sizer = wx.StaticBoxSizer(suit_box, wx.VERTICAL)

        suit_note = wx.StaticText(general_panel, label="Changing suit names will update all card names in this deck.")
        suit_note.SetForegroundColour(get_wx_color('text_dim'))
        suit_sizer.Add(suit_note, 0, wx.ALL, 10)

        suit_ctrls = {}
        for suit_key, default_name in suits:
            row = wx.BoxSizer(wx.HORIZONTAL)
            label = wx.StaticText(general_panel, label=f"{default_name}:", size=(80, -1))
            label.SetForegroundColour(get_wx_color('text_primary'))
            row.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

            ctrl = wx.TextCtrl(general_panel, value=suit_names.get(suit_key, default_name))
            ctrl.SetBackgroundColour(get_wx_color('bg_input'))
            ctrl.SetForegroundColour(get_wx_color('text_primary'))
            suit_ctrls[suit_key] = ctrl
            row.Add(ctrl, 1)

            suit_sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        general_sizer.Add(suit_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # Auto-assign metadata button (for Tarot, Lenormand, Kipper, Playing Cards, Oracle)
        if deck_type in ('Tarot', 'Lenormand', 'Kipper', 'Playing Cards', 'Oracle'):
            auto_meta_sizer = wx.BoxSizer(wx.HORIZONTAL)
            auto_meta_btn = wx.Button(general_panel, label="Auto-assign Card Metadata")

            def on_auto_assign(e):
                # For Tarot decks, show preset selection for ordering
                preset_name = None
                if deck_type == 'Tarot':
                    # Build list of Tarot presets
                    tarot_presets = []
                    for name in self.presets.get_preset_names():
                        preset = self.presets.get_preset(name)
                        if preset and preset.get('type') == 'Tarot':
                            tarot_presets.append(name)

                    if tarot_presets:
                        # Show preset selection dialog
                        preset_dlg = wx.SingleChoiceDialog(
                            dlg,
                            "Select the ordering for this deck.\n"
                            "This affects the numbering of Strength/Justice:\n\n"
                            "• RWS Ordering: Strength=VIII, Justice=XI\n"
                            "• Thoth/Pre-Golden Dawn: Strength=XI, Justice=VIII",
                            "Select Deck Ordering",
                            tarot_presets
                        )
                        if preset_dlg.ShowModal() == wx.ID_OK:
                            preset_name = preset_dlg.GetStringSelection()
                        else:
                            preset_dlg.Destroy()
                            return
                        preset_dlg.Destroy()
                elif deck_type == 'Lenormand':
                    preset_name = "Lenormand (36 cards)"
                elif deck_type == 'Kipper':
                    preset_name = "Kipper (36 cards)"
                elif deck_type == 'Playing Cards':
                    preset_name = "Playing Cards with Jokers (54 cards)"
                elif deck_type == 'Oracle':
                    preset_name = "Oracle (filename only)"

                # Create a dialog with options
                overwrite_dlg = wx.Dialog(dlg, title="Auto-assign Metadata", size=(450, 280))
                overwrite_dlg.SetBackgroundColour(get_wx_color('bg_primary'))
                dlg_sizer = wx.BoxSizer(wx.VERTICAL)

                msg = wx.StaticText(overwrite_dlg,
                    label="This will automatically assign archetype, rank, and suit\n"
                          "to cards based on the selected method.")
                msg.SetForegroundColour(get_wx_color('text_primary'))
                dlg_sizer.Add(msg, 0, wx.ALL, 15)

                # Assignment method radio buttons
                # NOTE: wx.RadioButton labels don't support custom colors on macOS
                # Use empty-label radio buttons with separate StaticText labels
                method_box = wx.StaticBox(overwrite_dlg, label="Assignment Method")
                method_box.SetForegroundColour(get_wx_color('accent'))
                method_sizer = wx.StaticBoxSizer(method_box, wx.VERTICAL)

                method_name_sizer = wx.BoxSizer(wx.HORIZONTAL)
                method_name_rb = wx.RadioButton(overwrite_dlg, label="", style=wx.RB_GROUP)
                method_name_rb.SetValue(True)
                method_name_sizer.Add(method_name_rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
                method_name_label = wx.StaticText(overwrite_dlg, label="By card name (parse names for rank/suit)")
                method_name_label.SetForegroundColour(get_wx_color('text_primary'))
                method_name_sizer.Add(method_name_label, 0, wx.ALIGN_CENTER_VERTICAL)
                method_sizer.Add(method_name_sizer, 0, wx.ALL, 5)

                method_order_sizer = wx.BoxSizer(wx.HORIZONTAL)
                method_order_rb = wx.RadioButton(overwrite_dlg, label="")
                method_order_sizer.Add(method_order_rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
                method_order_label = wx.StaticText(overwrite_dlg, label="By sort order (assign sequentially 1, 2, 3...)")
                method_order_label.SetForegroundColour(get_wx_color('text_primary'))
                method_order_sizer.Add(method_order_label, 0, wx.ALIGN_CENTER_VERTICAL)
                method_sizer.Add(method_order_sizer, 0, wx.ALL, 5)

                dlg_sizer.Add(method_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

                # Overwrite checkbox - use separate checkbox and label for macOS
                overwrite_sizer = wx.BoxSizer(wx.HORIZONTAL)
                overwrite_cb = wx.CheckBox(overwrite_dlg, label="")
                overwrite_sizer.Add(overwrite_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
                overwrite_label = wx.StaticText(overwrite_dlg, label="Overwrite existing metadata")
                overwrite_label.SetForegroundColour(get_wx_color('text_primary'))
                overwrite_sizer.Add(overwrite_label, 0, wx.ALIGN_CENTER_VERTICAL)
                dlg_sizer.Add(overwrite_sizer, 0, wx.ALL, 15)

                btn_sizer = wx.StdDialogButtonSizer()
                ok_btn = wx.Button(overwrite_dlg, wx.ID_OK, "Continue")
                ok_btn.SetForegroundColour(get_wx_color('text_primary'))
                ok_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
                cancel_btn = wx.Button(overwrite_dlg, wx.ID_CANCEL, "Cancel")
                cancel_btn.SetForegroundColour(get_wx_color('text_primary'))
                cancel_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
                btn_sizer.AddButton(ok_btn)
                btn_sizer.AddButton(cancel_btn)
                btn_sizer.Realize()
                dlg_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

                overwrite_dlg.SetSizer(dlg_sizer)
                overwrite_dlg.Fit()
                overwrite_dlg.CenterOnParent()

                if overwrite_dlg.ShowModal() == wx.ID_OK:
                    overwrite = overwrite_cb.GetValue()
                    use_sort_order = method_order_rb.GetValue()
                    overwrite_dlg.Destroy()
                    updated = self.db.auto_assign_deck_metadata(deck_id, overwrite=overwrite,
                                                                 preset_name=preset_name,
                                                                 use_sort_order=use_sort_order)
                    # Refresh the cards display to update selection state
                    self._refresh_cards_display(deck_id, preserve_scroll=True)
                    wx.MessageBox(
                        f"Updated metadata for {updated} cards.",
                        "Complete",
                        wx.OK | wx.ICON_INFORMATION
                    )
                else:
                    overwrite_dlg.Destroy()

            auto_meta_btn.Bind(wx.EVT_BUTTON, on_auto_assign)
            auto_meta_sizer.Add(auto_meta_btn, 0)

            auto_meta_note = wx.StaticText(general_panel,
                label="  (Parses card names to fill in archetype/rank/suit)")
            auto_meta_note.SetForegroundColour(get_wx_color('text_dim'))
            auto_meta_sizer.Add(auto_meta_note, 0, wx.ALIGN_CENTER_VERTICAL)

            general_sizer.Add(auto_meta_sizer, 0, wx.ALL, 15)

        # Deck Types section - allow multiple types per deck
        deck_types_box = wx.StaticBox(general_panel, label="Deck Types")
        deck_types_box.SetForegroundColour(get_wx_color('accent'))
        deck_types_sizer = wx.StaticBoxSizer(deck_types_box, wx.VERTICAL)

        types_info = wx.StaticText(general_panel, label="Select one or more cartomancy types for this deck:")
        types_info.SetForegroundColour(get_wx_color('text_secondary'))
        deck_types_sizer.Add(types_info, 0, wx.ALL, 10)

        # Get all cartomancy types and current deck types
        all_cart_types = self.db.get_cartomancy_types()
        current_type_ids = {t['id'] for t in deck.get('cartomancy_types', [])}

        # Create checkboxes for each type (empty label + StaticText for macOS)
        dlg._deck_type_checks = {}
        types_grid = wx.FlexGridSizer(cols=2, hgap=20, vgap=5)
        for ct in all_cart_types:
            cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
            cb = wx.CheckBox(general_panel, label="")
            cb.SetValue(ct['id'] in current_type_ids)
            cb_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            cb_label = wx.StaticText(general_panel, label=ct['name'])
            cb_label.SetForegroundColour(get_wx_color('text_primary'))
            cb_sizer.Add(cb_label, 0, wx.ALIGN_CENTER_VERTICAL)
            types_grid.Add(cb_sizer, 0, wx.EXPAND)
            dlg._deck_type_checks[ct['id']] = cb

        deck_types_sizer.Add(types_grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        general_sizer.Add(deck_types_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        general_panel.SetSizer(general_sizer)
        notebook.AddPage(general_panel, "General")

        # === Details Tab ===
        details_panel = wx.Panel(notebook)
        details_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        details_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: Card Back Image
        card_back_panel = wx.Panel(details_panel)
        card_back_panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        card_back_sizer = wx.BoxSizer(wx.VERTICAL)

        card_back_label = wx.StaticText(card_back_panel, label="Card Back")
        card_back_label.SetForegroundColour(get_wx_color('text_primary'))
        card_back_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        card_back_sizer.Add(card_back_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

        # Image preview (150x225 - half the size of card preview)
        _back_preview_sz = _cfg.get('images', 'deck_back_preview_max', [150, 225])
        back_preview_size = tuple(_back_preview_sz)
        card_back_path = deck['card_back_image'] if 'card_back_image' in deck.keys() else None

        card_back_bitmap = load_and_scale_image(card_back_path, back_preview_size, as_wx_bitmap=True)
        if card_back_bitmap:
            card_back_display = wx.StaticBitmap(card_back_panel, bitmap=card_back_bitmap)
        else:
            card_back_display = wx.StaticText(card_back_panel, label="🂠")
            card_back_display.SetFont(wx.Font(48, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            card_back_display.SetForegroundColour(get_wx_color('text_dim'))

        card_back_sizer.Add(card_back_display, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Store the current path
        dlg._card_back_path = card_back_path

        def on_select_card_back(e):
            with wx.FileDialog(dlg, "Select Card Back Image",
                              wildcard="Image files (*.png;*.jpg;*.jpeg;*.gif;*.bmp)|*.png;*.jpg;*.jpeg;*.gif;*.bmp",
                              style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dlg:
                if file_dlg.ShowModal() == wx.ID_OK:
                    new_path = file_dlg.GetPath()
                    dlg._card_back_path = new_path
                    # Update preview
                    nonlocal card_back_display
                    new_bitmap = load_and_scale_image(new_path, back_preview_size, as_wx_bitmap=True)
                    if new_bitmap:
                        if isinstance(card_back_display, wx.StaticText):
                            card_back_display.Destroy()
                            card_back_display = wx.StaticBitmap(card_back_panel, bitmap=new_bitmap)
                            card_back_sizer.Insert(1, card_back_display, 0, wx.ALL | wx.ALIGN_CENTER, 10)
                        else:
                            card_back_display.SetBitmap(new_bitmap)
                        card_back_panel.Layout()

        def on_clear_card_back(e):
            nonlocal card_back_display
            dlg._card_back_path = ""  # Empty string to clear
            if isinstance(card_back_display, wx.StaticBitmap):
                card_back_display.Destroy()
                card_back_display = wx.StaticText(card_back_panel, label="🂠")
                card_back_display.SetFont(wx.Font(48, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                card_back_display.SetForegroundColour(get_wx_color('text_dim'))
                card_back_sizer.Insert(1, card_back_display, 0, wx.ALL | wx.ALIGN_CENTER, 10)
                card_back_panel.Layout()

        # Buttons for card back
        card_back_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        select_back_btn = wx.Button(card_back_panel, label="Select...")
        select_back_btn.Bind(wx.EVT_BUTTON, on_select_card_back)
        card_back_btn_sizer.Add(select_back_btn, 0, wx.RIGHT, 5)

        clear_back_btn = wx.Button(card_back_panel, label="Clear")
        clear_back_btn.Bind(wx.EVT_BUTTON, on_clear_card_back)
        card_back_btn_sizer.Add(clear_back_btn, 0)

        card_back_sizer.Add(card_back_btn_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        card_back_panel.SetSizer(card_back_sizer)
        details_sizer.Add(card_back_panel, 0, wx.ALL, 10)

        # Right side: Other details (in a scrolled panel)
        details_fields_scroll = scrolled.ScrolledPanel(details_panel)
        details_fields_scroll.SetBackgroundColour(get_wx_color('bg_primary'))
        details_fields_scroll.SetupScrolling(scroll_x=False)
        details_fields_sizer = wx.BoxSizer(wx.VERTICAL)

        # Date Published
        date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        date_label = wx.StaticText(details_fields_scroll, label="Date Published:")
        date_label.SetForegroundColour(get_wx_color('text_primary'))
        date_sizer.Add(date_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        date_ctrl = wx.TextCtrl(details_fields_scroll, value=deck['date_published'] or '' if 'date_published' in deck.keys() else '')
        date_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        date_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        date_sizer.Add(date_ctrl, 1)
        details_fields_sizer.Add(date_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Publisher
        pub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        pub_label = wx.StaticText(details_fields_scroll, label="Publisher:")
        pub_label.SetForegroundColour(get_wx_color('text_primary'))
        pub_sizer.Add(pub_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        pub_ctrl = wx.TextCtrl(details_fields_scroll, value=deck['publisher'] or '' if 'publisher' in deck.keys() else '')
        pub_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        pub_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        pub_sizer.Add(pub_ctrl, 1)
        details_fields_sizer.Add(pub_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Credits
        credits_label = wx.StaticText(details_fields_scroll, label="Credits:")
        credits_label.SetForegroundColour(get_wx_color('text_primary'))
        details_fields_sizer.Add(credits_label, 0, wx.LEFT | wx.RIGHT, 10)
        credits_ctrl = RichTextPanel(details_fields_scroll,
                                     value=deck['credits'] or '' if 'credits' in deck.keys() else '',
                                     min_height=100)
        details_fields_sizer.Add(credits_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Notes
        notes_label = wx.StaticText(details_fields_scroll, label="Notes:")
        notes_label.SetForegroundColour(get_wx_color('text_primary'))
        details_fields_sizer.Add(notes_label, 0, wx.LEFT | wx.RIGHT, 10)
        deck_notes_ctrl = RichTextPanel(details_fields_scroll,
                                        value=deck['notes'] or '' if 'notes' in deck.keys() else '',
                                        min_height=100)
        details_fields_sizer.Add(deck_notes_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Booklet Info
        booklet_label = wx.StaticText(details_fields_scroll, label="Booklet Info:")
        booklet_label.SetForegroundColour(get_wx_color('text_primary'))
        details_fields_sizer.Add(booklet_label, 0, wx.LEFT | wx.RIGHT, 10)
        booklet_ctrl = RichTextPanel(details_fields_scroll,
                                     value=deck['booklet_info'] or '' if 'booklet_info' in deck.keys() else '',
                                     min_height=100)
        details_fields_sizer.Add(booklet_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        details_fields_scroll.SetSizer(details_fields_sizer)
        details_sizer.Add(details_fields_scroll, 1, wx.EXPAND | wx.ALL, 5)

        details_panel.SetSizer(details_sizer)
        notebook.AddPage(details_panel, "Details")

        # === Tags Tab ===
        tags_panel = wx.Panel(notebook)
        tags_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        tags_sizer = wx.BoxSizer(wx.VERTICAL)

        tags_info = wx.StaticText(tags_panel,
            label="Assign tags to this deck. Cards in this deck will inherit these tags.")
        tags_info.SetForegroundColour(get_wx_color('text_secondary'))
        tags_sizer.Add(tags_info, 0, wx.ALL, 10)

        # Get current deck tags and all available deck tags
        current_deck_tags = {t['id'] for t in self.db.get_tags_for_deck(deck_id)}
        all_deck_tags = list(self.db.get_deck_tags())

        # CheckListBox for tag selection
        tag_choices = [tag['name'] for tag in all_deck_tags]
        deck_tag_checklist = wx.CheckListBox(tags_panel, choices=tag_choices)
        deck_tag_checklist.SetBackgroundColour(get_wx_color('bg_secondary'))
        deck_tag_checklist.SetForegroundColour(get_wx_color('text_primary'))

        # Check the tags that are already assigned
        for i, tag in enumerate(all_deck_tags):
            if tag['id'] in current_deck_tags:
                deck_tag_checklist.Check(i, True)

        tags_sizer.Add(deck_tag_checklist, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Button to add new tag
        def on_add_new_deck_tag(e):
            result = self._show_tag_dialog(dlg, "Add Deck Tag")
            if result:
                try:
                    new_id = self.db.add_deck_tag(result['name'], result['color'])
                    # Refresh the checklist
                    all_deck_tags.append({'id': new_id, 'name': result['name'], 'color': result['color']})
                    deck_tag_checklist.Append(result['name'])
                    deck_tag_checklist.Check(deck_tag_checklist.GetCount() - 1, True)
                    # Also refresh the main tags list if visible
                    self._refresh_deck_tags_list()
                except Exception as ex:
                    wx.MessageBox(f"Could not add tag: {ex}", "Error", wx.OK | wx.ICON_ERROR)

        add_tag_btn = wx.Button(tags_panel, label="+ New Tag")
        add_tag_btn.Bind(wx.EVT_BUTTON, on_add_new_deck_tag)
        tags_sizer.Add(add_tag_btn, 0, wx.ALL, 10)

        tags_panel.SetSizer(tags_sizer)
        notebook.AddPage(tags_panel, "Tags")

        # === Custom Fields Tab ===
        cf_panel = wx.Panel(notebook)
        cf_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        cf_sizer = wx.BoxSizer(wx.VERTICAL)

        cf_info = wx.StaticText(cf_panel,
            label="Define custom fields that apply to all cards in this deck.\nThese fields appear in the card edit dialog.")
        cf_info.SetForegroundColour(get_wx_color('text_secondary'))
        cf_sizer.Add(cf_info, 0, wx.ALL, 10)

        # List control for custom fields
        cf_list = wx.ListCtrl(cf_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        cf_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        cf_list.SetForegroundColour(get_wx_color('text_primary'))
        cf_list.InsertColumn(0, "Field Name", width=150)
        cf_list.InsertColumn(1, "Type", width=100)
        cf_list.InsertColumn(2, "Options", width=150)

        # Populate list
        def refresh_cf_list():
            cf_list.DeleteAllItems()
            for i, field in enumerate(custom_fields):
                idx = cf_list.InsertItem(i, field['field_name'])
                cf_list.SetItem(idx, 1, field['field_type'])
                options_str = ''
                if field['field_options']:
                    try:
                        opts = json.loads(field['field_options'])
                        options_str = ', '.join(opts[:3])
                        if len(opts) > 3:
                            options_str += '...'
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning("Failed to parse field_options in list: %s", e)
                cf_list.SetItem(idx, 2, options_str)
                cf_list.SetItemData(idx, field['id'])

        refresh_cf_list()
        cf_sizer.Add(cf_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Buttons for custom fields
        cf_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        def on_add_field(e):
            field_data = self._show_custom_field_dialog(dlg)
            if field_data:
                new_id = self.db.add_deck_custom_field(
                    deck_id,
                    field_data['name'],
                    field_data['type'],
                    field_data.get('options'),
                    len(custom_fields)
                )
                custom_fields.append({
                    'id': new_id,
                    'deck_id': deck_id,
                    'field_name': field_data['name'],
                    'field_type': field_data['type'],
                    'field_options': json.dumps(field_data.get('options')) if field_data.get('options') else None,
                    'field_order': len(custom_fields)
                })
                refresh_cf_list()

        def on_edit_field(e):
            sel = cf_list.GetFirstSelected()
            if sel == -1:
                return
            field_id = cf_list.GetItemData(sel)
            field = None
            field_idx = None
            for i, f in enumerate(custom_fields):
                if f['id'] == field_id:
                    field = f
                    field_idx = i
                    break
            if not field:
                return

            # Parse existing options
            existing_options = None
            if field['field_options']:
                try:
                    existing_options = json.loads(field['field_options'])
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse existing field_options: %s", e)

            field_data = self._show_custom_field_dialog(
                dlg,
                name=field['field_name'],
                field_type=field['field_type'],
                options=existing_options
            )
            if field_data:
                self.db.update_deck_custom_field(
                    field_id,
                    field_name=field_data['name'],
                    field_type=field_data['type'],
                    field_options=field_data.get('options')
                )
                custom_fields[field_idx] = {
                    'id': field_id,
                    'deck_id': deck_id,
                    'field_name': field_data['name'],
                    'field_type': field_data['type'],
                    'field_options': json.dumps(field_data.get('options')) if field_data.get('options') else None,
                    'field_order': field['field_order']
                }
                refresh_cf_list()

        def on_delete_field(e):
            sel = cf_list.GetFirstSelected()
            if sel == -1:
                return
            field_id = cf_list.GetItemData(sel)
            field_name = cf_list.GetItemText(sel)

            if wx.MessageBox(
                f"Delete custom field '{field_name}'?\n\nThis will remove the field from all cards.",
                "Confirm Delete",
                wx.YES_NO | wx.ICON_WARNING
            ) == wx.YES:
                self.db.delete_deck_custom_field(field_id)
                for i, f in enumerate(custom_fields):
                    if f['id'] == field_id:
                        custom_fields.pop(i)
                        break
                refresh_cf_list()

        def on_move_up(e):
            sel = cf_list.GetFirstSelected()
            if sel <= 0:
                return
            # Get the IDs before swapping
            moving_up_id = custom_fields[sel]['id']
            moving_down_id = custom_fields[sel - 1]['id']
            # Swap in local list
            custom_fields[sel], custom_fields[sel - 1] = custom_fields[sel - 1], custom_fields[sel]
            # Update field_order in database
            self.db.update_deck_custom_field(moving_up_id, field_order=sel - 1)
            self.db.update_deck_custom_field(moving_down_id, field_order=sel)
            # Update field_order in local list
            custom_fields[sel - 1]['field_order'] = sel - 1
            custom_fields[sel]['field_order'] = sel
            refresh_cf_list()
            cf_list.Select(sel - 1)

        def on_move_down(e):
            sel = cf_list.GetFirstSelected()
            if sel == -1 or sel >= len(custom_fields) - 1:
                return
            # Get the IDs before swapping
            moving_down_id = custom_fields[sel]['id']
            moving_up_id = custom_fields[sel + 1]['id']
            # Swap in local list
            custom_fields[sel], custom_fields[sel + 1] = custom_fields[sel + 1], custom_fields[sel]
            # Update field_order in database
            self.db.update_deck_custom_field(moving_down_id, field_order=sel + 1)
            self.db.update_deck_custom_field(moving_up_id, field_order=sel)
            # Update field_order in local list
            custom_fields[sel]['field_order'] = sel
            custom_fields[sel + 1]['field_order'] = sel + 1
            refresh_cf_list()
            cf_list.Select(sel + 1)

        add_cf_btn = wx.Button(cf_panel, label="+ Add Field")
        add_cf_btn.Bind(wx.EVT_BUTTON, on_add_field)
        cf_btn_sizer.Add(add_cf_btn, 0, wx.RIGHT, 5)

        edit_cf_btn = wx.Button(cf_panel, label="Edit")
        edit_cf_btn.Bind(wx.EVT_BUTTON, on_edit_field)
        cf_btn_sizer.Add(edit_cf_btn, 0, wx.RIGHT, 5)

        del_cf_btn = wx.Button(cf_panel, label="Delete")
        del_cf_btn.Bind(wx.EVT_BUTTON, on_delete_field)
        cf_btn_sizer.Add(del_cf_btn, 0, wx.RIGHT, 15)

        move_up_btn = wx.Button(cf_panel, label="Move Up")
        move_up_btn.Bind(wx.EVT_BUTTON, on_move_up)
        cf_btn_sizer.Add(move_up_btn, 0, wx.RIGHT, 5)

        move_down_btn = wx.Button(cf_panel, label="Move Down")
        move_down_btn.Bind(wx.EVT_BUTTON, on_move_down)
        cf_btn_sizer.Add(move_down_btn, 0)

        cf_sizer.Add(cf_btn_sizer, 0, wx.ALL, 10)

        cf_panel.SetSizer(cf_sizer)
        notebook.AddPage(cf_panel, "Custom Fields")

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Save")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        dlg.SetSizer(main_sizer)

        if dlg.ShowModal() == wx.ID_OK:
            new_name = name_ctrl.GetValue().strip()
            # Build new_suit_names based on deck type
            new_suit_names = {}
            for suit_key, default_name in suits:
                new_suit_names[suit_key] = suit_ctrls[suit_key].GetValue().strip() or default_name

            # Update deck name
            if new_name and new_name != deck['name']:
                self.db.update_deck(deck_id, name=new_name)

            # Update suit names (this also updates card names)
            if new_suit_names != suit_names:
                self.db.update_deck_suit_names(deck_id, new_suit_names, suit_names)

            # Update deck details
            new_date = date_ctrl.GetValue().strip()
            new_publisher = pub_ctrl.GetValue().strip()
            new_credits = credits_ctrl.GetValue().strip()
            new_notes = deck_notes_ctrl.GetValue().strip()
            new_booklet = booklet_ctrl.GetValue().strip()

            # Update card back image if changed
            new_card_back = dlg._card_back_path
            if new_card_back != card_back_path:
                self.db.update_deck(deck_id, card_back_image=new_card_back if new_card_back else None)

            self.db.update_deck(deck_id,
                                date_published=new_date,
                                publisher=new_publisher,
                                credits=new_credits,
                                notes=new_notes,
                                booklet_info=new_booklet)

            # Update deck tags
            selected_tag_ids = []
            for i in range(deck_tag_checklist.GetCount()):
                if deck_tag_checklist.IsChecked(i):
                    selected_tag_ids.append(all_deck_tags[i]['id'])
            self.db.set_deck_tags(deck_id, selected_tag_ids)

            # Update deck types (multiple types per deck)
            selected_type_ids = []
            for type_id, cb in dlg._deck_type_checks.items():
                if cb.GetValue():
                    selected_type_ids.append(type_id)
            if selected_type_ids:
                self.db.set_deck_types(deck_id, selected_type_ids)
            else:
                # At least one type must be selected - keep original
                wx.MessageBox("At least one deck type must be selected.\nTypes were not changed.",
                             "Warning", wx.OK | wx.ICON_WARNING)

            self._refresh_decks_list()
            # Re-select the deck after refresh
            self._select_deck_by_id(deck_id)
            self._refresh_cards_display(deck_id, preserve_scroll=True)
            wx.MessageBox("Deck updated!", "Success", wx.OK | wx.ICON_INFORMATION)

        dlg.Destroy()

    def _show_custom_field_dialog(self, parent, name='', field_type='text', options=None):
        """Show dialog to add/edit a custom field definition"""
        dlg = wx.Dialog(parent, title="Custom Field", size=(400, 300))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Field name
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(dlg, label="Field Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        name_ctrl = wx.TextCtrl(dlg, value=name)
        name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_ctrl, 1)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Field type
        type_sizer = wx.BoxSizer(wx.HORIZONTAL)
        type_label = wx.StaticText(dlg, label="Field Type:")
        type_label.SetForegroundColour(get_wx_color('text_primary'))
        type_sizer.Add(type_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        field_types = ['text', 'multiline', 'number', 'select', 'checkbox']
        type_ctrl = wx.Choice(dlg, choices=field_types)
        if field_type in field_types:
            type_ctrl.SetSelection(field_types.index(field_type))
        else:
            type_ctrl.SetSelection(0)
        type_sizer.Add(type_ctrl, 1)
        sizer.Add(type_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Options (for select type)
        options_label = wx.StaticText(dlg, label="Options (for 'select' type, one per line):")
        options_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(options_label, 0, wx.LEFT | wx.TOP, 10)

        options_ctrl = wx.TextCtrl(dlg, style=wx.TE_MULTILINE,
                                   value='\n'.join(options) if options else '')
        options_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        options_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(options_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Save")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        dlg.SetSizer(sizer)

        result = None
        if dlg.ShowModal() == wx.ID_OK:
            field_name = name_ctrl.GetValue().strip()
            if field_name:
                selected_type = type_ctrl.GetString(type_ctrl.GetSelection())
                opts = None
                if selected_type == 'select':
                    opts_text = options_ctrl.GetValue().strip()
                    if opts_text:
                        opts = [o.strip() for o in opts_text.split('\n') if o.strip()]
                result = {
                    'name': field_name,
                    'type': selected_type,
                    'options': opts
                }

        dlg.Destroy()
        return result

    def _on_delete_deck(self, event):
        """Delete the selected deck"""
        # Get deck_id based on current view mode
        deck_id = None
        if self._deck_view_mode == 'image':
            deck_id = self._selected_deck_id
        else:
            idx = self.deck_list.GetFirstSelected()
            if idx != -1:
                deck_id = self.deck_list.GetItemData(idx)

        if not deck_id:
            return
        deck = self.db.get_deck(deck_id)

        if wx.MessageBox(f"Delete '{deck['name']}' and all cards?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.db.delete_deck(deck_id)
            self._selected_deck_id = None
            self._refresh_decks_list()
            self._refresh_cards_display(None)
