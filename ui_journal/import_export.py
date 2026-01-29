"""Import/export functionality for journal entries."""

import wx

from ui_helpers import get_wx_color


class ImportExportMixin:
    """Mixin providing import/export functionality for journal entries."""

    def _on_export_entries(self, event):
        """Show export dialog for journal entries"""
        # Get all selected entry IDs
        selected_entry_ids = []
        idx = self.entry_list.GetFirstSelected()
        while idx != -1:
            selected_entry_ids.append(self.entry_list.GetItemData(idx))
            idx = self.entry_list.GetNextSelected(idx)

        # Create dialog to choose export options
        dlg = wx.Dialog(self, title="Export Entries", size=(400, 250))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Export scope
        scope_label = wx.StaticText(dlg, label="What to export:")
        scope_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(scope_label, 0, wx.ALL, 10)

        # Radio buttons with separate labels (for proper text color on macOS)
        all_sizer = wx.BoxSizer(wx.HORIZONTAL)
        export_all_radio = wx.RadioButton(dlg, label="", style=wx.RB_GROUP)
        all_sizer.Add(export_all_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        all_label = wx.StaticText(dlg, label="All entries")
        all_label.SetForegroundColour(get_wx_color('text_primary'))
        all_sizer.Add(all_label, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(all_sizer, 0, wx.LEFT, 20)

        selected_sizer = wx.BoxSizer(wx.HORIZONTAL)
        export_selected_radio = wx.RadioButton(dlg, label="")
        selected_sizer.Add(export_selected_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        # Update label based on selection count
        selection_count = len(selected_entry_ids)
        if selection_count == 1:
            selected_text = "Selected entry (1)"
        else:
            selected_text = f"Selected entries ({selection_count})"
        selected_label = wx.StaticText(dlg, label=selected_text)
        selected_label.SetForegroundColour(get_wx_color('text_primary'))
        selected_sizer.Add(selected_label, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(selected_sizer, 0, wx.LEFT | wx.TOP, 20)

        # Disable selected option if no entries selected
        if selection_count == 0:
            export_selected_radio.Enable(False)
            selected_label.SetForegroundColour(get_wx_color('text_dim'))

        sizer.AddSpacer(15)

        # Format selection
        format_label = wx.StaticText(dlg, label="Export format:")
        format_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(format_label, 0, wx.LEFT, 10)

        json_sizer = wx.BoxSizer(wx.HORIZONTAL)
        json_radio = wx.RadioButton(dlg, label="", style=wx.RB_GROUP)
        json_sizer.Add(json_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        json_label = wx.StaticText(dlg, label="JSON (data only)")
        json_label.SetForegroundColour(get_wx_color('text_primary'))
        json_sizer.Add(json_label, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(json_sizer, 0, wx.LEFT | wx.TOP, 20)

        zip_sizer = wx.BoxSizer(wx.HORIZONTAL)
        zip_radio = wx.RadioButton(dlg, label="")
        zip_sizer.Add(zip_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        zip_label = wx.StaticText(dlg, label="ZIP (data + card images)")
        zip_label.SetForegroundColour(get_wx_color('text_primary'))
        zip_sizer.Add(zip_label, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(zip_sizer, 0, wx.LEFT | wx.TOP, 20)

        sizer.AddStretchSpacer()

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        export_btn = wx.Button(dlg, wx.ID_OK, "Export")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(export_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            # Get selected options
            export_all = export_all_radio.GetValue()
            use_zip = zip_radio.GetValue()

            entry_ids = None if export_all else selected_entry_ids

            # Choose file extension
            if use_zip:
                wildcard = "ZIP files (*.zip)|*.zip"
                default_ext = ".zip"
            else:
                wildcard = "JSON files (*.json)|*.json"
                default_ext = ".json"

            # Show file save dialog
            file_dlg = wx.FileDialog(
                self, "Save Export",
                wildcard=wildcard,
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
            )
            file_dlg.SetFilename(f"tarot_journal_export{default_ext}")

            if file_dlg.ShowModal() == wx.ID_OK:
                filepath = file_dlg.GetPath()

                try:
                    if use_zip:
                        self.db.export_entries_to_zip(filepath, entry_ids)
                    else:
                        self.db.export_entries_to_file(filepath, entry_ids)

                    wx.MessageBox(
                        f"Export complete!\n\nSaved to: {filepath}",
                        "Export Successful",
                        wx.OK | wx.ICON_INFORMATION
                    )
                except Exception as e:
                    wx.MessageBox(
                        f"Export failed:\n{str(e)}",
                        "Export Error",
                        wx.OK | wx.ICON_ERROR
                    )

            file_dlg.Destroy()

        dlg.Destroy()

    def _on_import_entries(self, event):
        """Show import dialog for journal entries"""
        wildcard = "Journal exports (*.json;*.zip)|*.json;*.zip|JSON files (*.json)|*.json|ZIP files (*.zip)|*.zip"

        file_dlg = wx.FileDialog(
            self, "Import Entries",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if file_dlg.ShowModal() == wx.ID_OK:
            filepath = file_dlg.GetPath()

            try:
                if filepath.lower().endswith('.zip'):
                    result = self.db.import_entries_from_zip(filepath)
                else:
                    result = self.db.import_entries_from_file(filepath)

                wx.MessageBox(
                    f"Import complete!\n\n"
                    f"Entries imported: {result['imported']}\n"
                    f"New tags created: {result['tags_created']}",
                    "Import Successful",
                    wx.OK | wx.ICON_INFORMATION
                )

                self._refresh_entries_list()
                self._refresh_tags_list()

            except Exception as e:
                wx.MessageBox(
                    f"Import failed:\n{str(e)}",
                    "Import Error",
                    wx.OK | wx.ICON_ERROR
                )

        file_dlg.Destroy()
