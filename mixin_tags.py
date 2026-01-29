"""DEPRECATED: Legacy wxPython UI - see frontend/ for active Electron/React code.

Tags panel mixin for MainFrame."""

import wx
from ui_helpers import logger, get_wx_color


class TagsMixin:
    def _create_tags_panel(self):
        """Create the Tags management panel with Deck Tags and Card Tags sections"""
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # === Left side: Deck Tags ===
        deck_tags_box = wx.StaticBox(panel, label="Deck Tags")
        deck_tags_box.SetForegroundColour(get_wx_color('accent'))
        deck_tags_sizer = wx.StaticBoxSizer(deck_tags_box, wx.VERTICAL)

        deck_tags_info = wx.StaticText(panel, label="Tags that can be applied to decks.\nCards inherit their deck's tags.")
        deck_tags_info.SetForegroundColour(get_wx_color('text_secondary'))
        deck_tags_sizer.Add(deck_tags_info, 0, wx.ALL, 10)

        self.deck_tags_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.deck_tags_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.deck_tags_list.SetForegroundColour(get_wx_color('text_primary'))
        self.deck_tags_list.InsertColumn(0, "Name", width=150)
        self.deck_tags_list.InsertColumn(1, "Color", width=80)
        self.deck_tags_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit_deck_tag)
        deck_tags_sizer.Add(self.deck_tags_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        deck_tags_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_deck_tag_btn = wx.Button(panel, label="+ Add Tag")
        add_deck_tag_btn.Bind(wx.EVT_BUTTON, self._on_add_deck_tag)
        deck_tags_btn_sizer.Add(add_deck_tag_btn, 0, wx.RIGHT, 5)

        edit_deck_tag_btn = wx.Button(panel, label="Edit")
        edit_deck_tag_btn.Bind(wx.EVT_BUTTON, self._on_edit_deck_tag)
        deck_tags_btn_sizer.Add(edit_deck_tag_btn, 0, wx.RIGHT, 5)

        del_deck_tag_btn = wx.Button(panel, label="Delete")
        del_deck_tag_btn.Bind(wx.EVT_BUTTON, self._on_delete_deck_tag)
        deck_tags_btn_sizer.Add(del_deck_tag_btn, 0)

        deck_tags_sizer.Add(deck_tags_btn_sizer, 0, wx.ALL, 10)

        main_sizer.Add(deck_tags_sizer, 1, wx.EXPAND | wx.ALL, 10)

        # === Right side: Card Tags ===
        card_tags_box = wx.StaticBox(panel, label="Card Tags")
        card_tags_box.SetForegroundColour(get_wx_color('accent'))
        card_tags_sizer = wx.StaticBoxSizer(card_tags_box, wx.VERTICAL)

        card_tags_info = wx.StaticText(panel, label="Tags that can be applied to individual cards.\nThese are separate from deck tags.")
        card_tags_info.SetForegroundColour(get_wx_color('text_secondary'))
        card_tags_sizer.Add(card_tags_info, 0, wx.ALL, 10)

        self.card_tags_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.card_tags_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.card_tags_list.SetForegroundColour(get_wx_color('text_primary'))
        self.card_tags_list.InsertColumn(0, "Name", width=150)
        self.card_tags_list.InsertColumn(1, "Color", width=80)
        self.card_tags_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit_card_tag)
        card_tags_sizer.Add(self.card_tags_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        card_tags_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_card_tag_btn = wx.Button(panel, label="+ Add Tag")
        add_card_tag_btn.Bind(wx.EVT_BUTTON, self._on_add_card_tag)
        card_tags_btn_sizer.Add(add_card_tag_btn, 0, wx.RIGHT, 5)

        edit_card_tag_btn = wx.Button(panel, label="Edit")
        edit_card_tag_btn.Bind(wx.EVT_BUTTON, self._on_edit_card_tag)
        card_tags_btn_sizer.Add(edit_card_tag_btn, 0, wx.RIGHT, 5)

        del_card_tag_btn = wx.Button(panel, label="Delete")
        del_card_tag_btn.Bind(wx.EVT_BUTTON, self._on_delete_card_tag)
        card_tags_btn_sizer.Add(del_card_tag_btn, 0)

        card_tags_sizer.Add(card_tags_btn_sizer, 0, wx.ALL, 10)

        main_sizer.Add(card_tags_sizer, 1, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        # Populate lists
        self._refresh_deck_tags_list()
        self._refresh_card_tags_list()

        return panel

    def _refresh_deck_tags_list(self):
        """Refresh the deck tags list"""
        self.deck_tags_list.DeleteAllItems()
        tags = self.db.get_deck_tags()
        for i, tag in enumerate(tags):
            idx = self.deck_tags_list.InsertItem(i, tag['name'])
            self.deck_tags_list.SetItem(idx, 1, tag['color'])
            self.deck_tags_list.SetItemData(idx, tag['id'])

    def _refresh_card_tags_list(self):
        """Refresh the card tags list"""
        self.card_tags_list.DeleteAllItems()
        tags = self.db.get_card_tags()
        for i, tag in enumerate(tags):
            idx = self.card_tags_list.InsertItem(i, tag['name'])
            self.card_tags_list.SetItem(idx, 1, tag['color'])
            self.card_tags_list.SetItemData(idx, tag['id'])

    def _show_tag_dialog(self, parent, title, name='', color='#6B5B95'):
        """Show dialog to add/edit a tag"""
        dlg = wx.Dialog(parent, title=title, size=(350, 200))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Name field
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(dlg, label="Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        name_ctrl = wx.TextCtrl(dlg, value=name)
        name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_ctrl, 1)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 15)

        # Color field
        color_sizer = wx.BoxSizer(wx.HORIZONTAL)
        color_label = wx.StaticText(dlg, label="Color:")
        color_label.SetForegroundColour(get_wx_color('text_primary'))
        color_sizer.Add(color_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        color_ctrl = wx.ColourPickerCtrl(dlg, colour=wx.Colour(color))
        color_sizer.Add(color_ctrl, 0)
        sizer.Add(color_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        cancel_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        cancel_btn.SetForegroundColour(get_wx_color('text_primary'))
        save_btn = wx.Button(dlg, wx.ID_OK, "Save")
        save_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        save_btn.SetForegroundColour(get_wx_color('text_primary'))
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            new_name = name_ctrl.GetValue().strip()
            new_color = color_ctrl.GetColour().GetAsString(wx.C2S_HTML_SYNTAX)
            dlg.Destroy()
            if new_name:
                return {'name': new_name, 'color': new_color}
        else:
            dlg.Destroy()
        return None

    def _on_add_deck_tag(self, event):
        """Add a new deck tag"""
        result = self._show_tag_dialog(self, "Add Deck Tag")
        if result:
            try:
                self.db.add_deck_tag(result['name'], result['color'])
                self._refresh_deck_tags_list()
            except Exception as e:
                wx.MessageBox(f"Could not add tag: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_edit_deck_tag(self, event):
        """Edit selected deck tag"""
        idx = self.deck_tags_list.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a tag to edit.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        tag_id = self.deck_tags_list.GetItemData(idx)
        tag = self.db.get_deck_tag(tag_id)
        if not tag:
            return
        result = self._show_tag_dialog(self, "Edit Deck Tag", tag['name'], tag['color'])
        if result:
            try:
                self.db.update_deck_tag(tag_id, result['name'], result['color'])
                self._refresh_deck_tags_list()
            except Exception as e:
                wx.MessageBox(f"Could not update tag: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_delete_deck_tag(self, event):
        """Delete selected deck tag"""
        idx = self.deck_tags_list.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a tag to delete.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        tag_id = self.deck_tags_list.GetItemData(idx)
        if wx.MessageBox(
            "Delete this tag? It will be removed from all decks.",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_WARNING
        ) == wx.YES:
            self.db.delete_deck_tag(tag_id)
            self._refresh_deck_tags_list()

    def _on_add_card_tag(self, event):
        """Add a new card tag"""
        result = self._show_tag_dialog(self, "Add Card Tag")
        if result:
            try:
                self.db.add_card_tag(result['name'], result['color'])
                self._refresh_card_tags_list()
            except Exception as e:
                wx.MessageBox(f"Could not add tag: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_edit_card_tag(self, event):
        """Edit selected card tag"""
        idx = self.card_tags_list.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a tag to edit.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        tag_id = self.card_tags_list.GetItemData(idx)
        tag = self.db.get_card_tag(tag_id)
        if not tag:
            return
        result = self._show_tag_dialog(self, "Edit Card Tag", tag['name'], tag['color'])
        if result:
            try:
                self.db.update_card_tag(tag_id, result['name'], result['color'])
                self._refresh_card_tags_list()
            except Exception as e:
                wx.MessageBox(f"Could not update tag: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_delete_card_tag(self, event):
        """Delete selected card tag"""
        idx = self.card_tags_list.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a tag to delete.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        tag_id = self.card_tags_list.GetItemData(idx)
        if wx.MessageBox(
            "Delete this tag? It will be removed from all cards.",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_WARNING
        ) == wx.YES:
            self.db.delete_card_tag(tag_id)
            self._refresh_card_tags_list()
