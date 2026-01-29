"""Deck import and export functionality for the library panel."""

import os
from pathlib import Path

import wx

from ui_helpers import get_wx_color
from import_presets import COURT_PRESETS, ARCHETYPE_MAPPING_OPTIONS


class ImportExportMixin:
    """Mixin providing deck import and export functionality."""

    def _on_import_folder(self, event):
        """Open folder selection dialog for deck import"""
        dlg = wx.DirDialog(self, "Select folder with card images")
        if dlg.ShowModal() == wx.ID_OK:
            folder = dlg.GetPath()
            self._show_import_dialog(folder)
        dlg.Destroy()

    def _show_import_dialog(self, folder):
        """Show the deck import configuration dialog"""
        dlg = wx.Dialog(self, title="Import Deck", size=(650, 600))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Name
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(dlg, label="Deck Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        name_ctrl = wx.TextCtrl(dlg, value=Path(folder).name)
        name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_ctrl, 1)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Preset
        preset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        preset_label = wx.StaticText(dlg, label="Import Preset:")
        preset_label.SetForegroundColour(get_wx_color('text_primary'))
        preset_sizer.Add(preset_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        preset_choice = wx.Choice(dlg, choices=self.presets.get_preset_names())
        preset_choice.SetSelection(0)
        preset_sizer.Add(preset_choice, 0)
        sizer.Add(preset_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Suit names section (will be updated based on preset type)
        suit_box = wx.StaticBox(dlg, label="Suit Names")
        suit_box.SetForegroundColour(get_wx_color('accent'))
        suit_box_sizer = wx.StaticBoxSizer(suit_box, wx.HORIZONTAL)

        # Create inner panel to hold suit controls (for easy replacement)
        suit_panel = wx.Panel(dlg)
        suit_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        suit_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        suit_panel.SetSizer(suit_panel_sizer)
        suit_box_sizer.Add(suit_panel, 1, wx.EXPAND)

        suit_ctrls = {}
        suit_labels = {}

        def create_suit_controls(deck_type):
            """Create suit name controls based on deck type"""
            # Clear existing controls
            for child in suit_panel.GetChildren():
                child.Destroy()
            suit_ctrls.clear()
            suit_labels.clear()

            if deck_type in ('Lenormand', 'Playing Cards'):
                suits = [('hearts', 'Hearts'), ('diamonds', 'Diamonds'),
                         ('clubs', 'Clubs'), ('spades', 'Spades')]
            else:  # Tarot or Oracle
                suits = [('wands', 'Wands'), ('cups', 'Cups'),
                         ('swords', 'Swords'), ('pentacles', 'Pentacles')]

            new_sizer = wx.BoxSizer(wx.HORIZONTAL)
            for suit_key, default_name in suits:
                col = wx.BoxSizer(wx.VERTICAL)
                label = wx.StaticText(suit_panel, label=f"{default_name}:")
                label.SetForegroundColour(get_wx_color('text_secondary'))
                col.Add(label, 0, wx.BOTTOM, 2)
                suit_labels[suit_key] = label

                ctrl = wx.TextCtrl(suit_panel, value=default_name, size=(100, -1))
                ctrl.SetBackgroundColour(get_wx_color('bg_input'))
                ctrl.SetForegroundColour(get_wx_color('text_primary'))
                suit_ctrls[suit_key] = ctrl
                col.Add(ctrl, 0)

                new_sizer.Add(col, 0, wx.ALL, 5)

            suit_panel.SetSizer(new_sizer)
            suit_panel.Layout()
            dlg.Layout()

            # Bind text events for preview updates
            for ctrl in suit_ctrls.values():
                ctrl.Bind(wx.EVT_TEXT, update_preview)

        sizer.Add(suit_box_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Court Cards section (only shown for Tarot)
        court_box = wx.StaticBox(dlg, label="Court Cards")
        court_box.SetForegroundColour(get_wx_color('accent'))
        court_box_sizer = wx.StaticBoxSizer(court_box, wx.VERTICAL)

        # Court preset dropdown row
        court_preset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        court_preset_label = wx.StaticText(dlg, label="Court Style:")
        court_preset_label.SetForegroundColour(get_wx_color('text_secondary'))
        court_preset_sizer.Add(court_preset_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        court_preset_names = list(COURT_PRESETS.keys())
        court_preset_choice = wx.Choice(dlg, choices=court_preset_names)
        court_preset_choice.SetSelection(0)  # Default to RWS
        court_preset_sizer.Add(court_preset_choice, 0, wx.RIGHT, 20)

        # Archetype mapping dropdown
        archetype_label = wx.StaticText(dlg, label="Archetype Mapping:")
        archetype_label.SetForegroundColour(get_wx_color('text_secondary'))
        court_preset_sizer.Add(archetype_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        archetype_choice = wx.Choice(dlg, choices=ARCHETYPE_MAPPING_OPTIONS)
        archetype_choice.SetSelection(0)  # Default to RWS archetypes
        court_preset_sizer.Add(archetype_choice, 0)

        court_box_sizer.Add(court_preset_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Custom court name controls (hidden by default)
        court_custom_panel = wx.Panel(dlg)
        court_custom_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        court_custom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        court_ctrls = {}
        court_positions = [('page', 'Page'), ('knight', 'Knight'), ('queen', 'Queen'), ('king', 'King')]
        for pos_key, default_name in court_positions:
            col = wx.BoxSizer(wx.VERTICAL)
            label = wx.StaticText(court_custom_panel, label=f"{default_name}:")
            label.SetForegroundColour(get_wx_color('text_secondary'))
            col.Add(label, 0, wx.BOTTOM, 2)

            ctrl = wx.TextCtrl(court_custom_panel, value=default_name, size=(100, -1))
            ctrl.SetBackgroundColour(get_wx_color('bg_input'))
            ctrl.SetForegroundColour(get_wx_color('text_primary'))
            ctrl.Bind(wx.EVT_TEXT, lambda e: update_preview())
            court_ctrls[pos_key] = ctrl
            col.Add(ctrl, 0)

            court_custom_sizer.Add(col, 0, wx.ALL, 5)

        court_custom_panel.SetSizer(court_custom_sizer)
        court_custom_panel.Hide()  # Hidden by default
        court_box_sizer.Add(court_custom_panel, 0, wx.EXPAND)

        sizer.Add(court_box_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Track court section visibility
        court_section_visible = [True]

        def update_court_section_visibility(deck_type):
            """Show/hide court section based on deck type"""
            should_show = deck_type == 'Tarot'
            if should_show != court_section_visible[0]:
                court_section_visible[0] = should_show
                court_box.Show(should_show)
                court_box_sizer.ShowItems(should_show)
                dlg.Layout()

        def on_court_preset_change(e=None):
            """Handle court preset dropdown change"""
            preset_name = court_preset_choice.GetStringSelection()
            preset_values = COURT_PRESETS.get(preset_name)

            if preset_values is None:
                # "Custom..." selected - show text fields
                court_custom_panel.Show()
            else:
                # Preset selected - hide text fields and update values
                court_custom_panel.Hide()
                for pos_key, name in preset_values.items():
                    if pos_key in court_ctrls:
                        court_ctrls[pos_key].SetValue(name)

            dlg.Layout()
            update_preview()

        court_preset_choice.Bind(wx.EVT_CHOICE, on_court_preset_change)
        archetype_choice.Bind(wx.EVT_CHOICE, lambda e: update_preview())

        def get_court_names():
            """Get current court card names from UI"""
            preset_name = court_preset_choice.GetStringSelection()
            preset_values = COURT_PRESETS.get(preset_name)

            if preset_values is None:
                # Custom - use text field values
                return {pos: ctrl.GetValue() for pos, ctrl in court_ctrls.items()}
            else:
                return preset_values.copy()

        # Preview
        preview_label = wx.StaticText(dlg, label="Preview:")
        preview_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(preview_label, 0, wx.LEFT | wx.RIGHT, 10)
        preview_list = wx.ListCtrl(dlg, style=wx.LC_REPORT)
        preview_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        preview_list.SetForegroundColour(get_wx_color('text_primary'))
        preview_list.InsertColumn(0, "Filename", width=200)
        preview_list.InsertColumn(1, "Card Name", width=250)
        sizer.Add(preview_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        updating_preview = [False]  # Use list to allow modification in nested function
        current_deck_type = ['Tarot']  # Track current deck type

        def update_preview(e=None):
            if updating_preview[0]:
                return
            updating_preview[0] = True

            try:
                preview_list.DeleteAllItems()

                # Get custom suit names for preview (use whatever keys are currently active)
                custom_suit_names = {}
                for key, ctrl in suit_ctrls.items():
                    custom_suit_names[key] = ctrl.GetValue()

                # Get court card settings if it's a Tarot deck
                custom_court_names = None
                archetype_mapping = None
                if current_deck_type[0] == 'Tarot':
                    custom_court_names = get_court_names()
                    archetype_mapping = archetype_choice.GetStringSelection()

                preset_name = preset_choice.GetStringSelection()
                # Use the metadata-aware preview to show card names with court customization
                preview = self.presets.preview_import_with_metadata(
                    folder, preset_name, custom_suit_names, custom_court_names, archetype_mapping
                )
                for card_info in preview:
                    idx = preview_list.InsertItem(preview_list.GetItemCount(), card_info['filename'])
                    preview_list.SetItem(idx, 1, card_info['name'])
            finally:
                updating_preview[0] = False

        def on_preset_change(e=None):
            if updating_preview[0]:
                return
            updating_preview[0] = True

            try:
                # Get preset info
                preset_name = preset_choice.GetStringSelection()
                preset = self.presets.get_preset(preset_name)
                deck_type = preset.get('type', 'Oracle') if preset else 'Oracle'

                # Recreate suit controls if deck type changed
                if deck_type != current_deck_type[0]:
                    current_deck_type[0] = deck_type
                    create_suit_controls(deck_type)
                    # Update court section visibility
                    update_court_section_visibility(deck_type)

                # Update suit control values from preset
                if preset:
                    preset_suits = preset.get('suit_names', {})
                    for suit_key, ctrl in suit_ctrls.items():
                        if suit_key in preset_suits:
                            ctrl.SetValue(preset_suits[suit_key])
                        else:
                            ctrl.SetValue(suit_key.title())
            finally:
                updating_preview[0] = False

            # Now update preview with new values
            update_preview()

        preset_choice.Bind(wx.EVT_CHOICE, on_preset_change)

        # Initial setup
        create_suit_controls('Tarot')  # Start with Tarot controls
        on_preset_change()  # This will update to correct type based on selected preset

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        import_btn = wx.Button(dlg, wx.ID_OK, "Import")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(import_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            name = name_ctrl.GetValue().strip()
            if name:
                preset = self.presets.get_preset(preset_choice.GetStringSelection())
                cart_type = preset.get('type', 'Oracle') if preset else 'Oracle'

                types = self.db.get_cartomancy_types()
                type_id = types[0]['id']
                for t in types:
                    if t['name'] == cart_type:
                        type_id = t['id']
                        break

                # Get suit names (keys depend on deck type)
                suit_names = {}
                for key, ctrl in suit_ctrls.items():
                    suit_names[key] = ctrl.GetValue().strip() or key.title()

                # Get court card names (only for Tarot)
                court_names = None
                custom_court_names = None
                archetype_mapping = None
                if cart_type == 'Tarot':
                    court_names = get_court_names()
                    custom_court_names = court_names
                    archetype_mapping = archetype_choice.GetStringSelection()

                deck_id = self.db.add_deck(name, type_id, folder, suit_names, court_names)

                # Create custom fields defined by the preset
                preset_name = preset_choice.GetStringSelection()
                if preset and preset.get('custom_fields'):
                    for idx, field_def in enumerate(preset['custom_fields']):
                        self.db.add_deck_custom_field(
                            deck_id,
                            field_def['name'],
                            field_def.get('type', 'text'),
                            field_def.get('options'),
                            idx
                        )

                # Use the metadata-aware import to get archetype, rank, suit
                preview = self.presets.preview_import_with_metadata(
                    folder, preset_name, suit_names, custom_court_names, archetype_mapping
                )
                cards = []
                for card_info in preview:
                    cards.append({
                        'name': card_info['name'],
                        'image_path': os.path.join(folder, card_info['filename']),
                        'sort_order': card_info['sort_order'],
                        'archetype': card_info['archetype'],
                        'rank': card_info['rank'],
                        'suit': card_info['suit'],
                        'custom_fields': card_info.get('custom_fields'),
                    })

                # Look for card back image
                card_back_path = self.presets.find_card_back_image(folder, preset_name)
                if card_back_path:
                    self.db.update_deck(deck_id, card_back_image=card_back_path)

                if cards:
                    self.db.bulk_add_cards(deck_id, cards)
                    self.thumb_cache.pregenerate_thumbnails([c['image_path'] for c in cards])
                    card_back_msg = f"\nCard back image: Found" if card_back_path else ""
                    wx.MessageBox(f"Imported {len(cards)} cards into '{name}'{card_back_msg}", "Success", wx.OK | wx.ICON_INFORMATION)

                self._refresh_decks_list()

        dlg.Destroy()

    def _on_export_deck(self, event):
        """Export the selected deck with all metadata to a JSON file."""
        # Get deck_id based on current view mode
        deck_id = None
        if self._deck_view_mode == 'image':
            deck_id = self._selected_deck_id
        else:
            idx = self.deck_list.GetFirstSelected()
            if idx != -1:
                deck_id = self.deck_list.GetItemData(idx)

        if not deck_id:
            wx.MessageBox("Select a deck to export.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        deck = self.db.get_deck(deck_id)
        if not deck:
            return

        # File save dialog
        wildcard = "JSON files (*.json)|*.json"
        default_name = f"{deck['name'].replace(' ', '_')}_deck.json"

        file_dlg = wx.FileDialog(
            self, "Export Deck",
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        file_dlg.SetFilename(default_name)

        if file_dlg.ShowModal() == wx.ID_OK:
            filepath = file_dlg.GetPath()
            try:
                self.db.export_deck_to_file(deck_id, filepath)
                wx.MessageBox(
                    f"Deck exported successfully!\n\nSaved to: {filepath}",
                    "Export Complete",
                    wx.OK | wx.ICON_INFORMATION
                )
            except Exception as e:
                wx.MessageBox(
                    f"Export failed:\n{str(e)}",
                    "Export Error",
                    wx.OK | wx.ICON_ERROR
                )

        file_dlg.Destroy()

    def _on_import_deck(self, event):
        """Import a deck from a JSON file."""
        wildcard = "JSON files (*.json)|*.json"

        file_dlg = wx.FileDialog(
            self, "Import Deck",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if file_dlg.ShowModal() == wx.ID_OK:
            filepath = file_dlg.GetPath()
            try:
                result = self.db.import_deck_from_file(filepath)
                self._refresh_decks_list()
                wx.MessageBox(
                    f"Deck imported successfully!\n\n"
                    f"Deck: {result['deck_name']}\n"
                    f"Cards: {result['cards_imported']}\n"
                    f"Custom fields: {result['custom_fields_created']}",
                    "Import Complete",
                    wx.OK | wx.ICON_INFORMATION
                )
            except Exception as e:
                wx.MessageBox(
                    f"Import failed:\n{str(e)}",
                    "Import Error",
                    wx.OK | wx.ICON_ERROR
                )

        file_dlg.Destroy()
