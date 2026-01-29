"""Card group management for the library panel."""

import wx

from ui_helpers import get_wx_color


class CardGroupsMixin:
    """Mixin providing card group management functionality."""

    def _on_manage_groups(self, event):
        """Open the group management dialog for the current deck"""
        deck_id = self._current_deck_id_for_cards
        if not deck_id:
            wx.MessageBox("Select a deck first.", "No Deck", wx.OK | wx.ICON_INFORMATION)
            return

        deck = self.db.get_deck(deck_id)
        deck_name = deck['name'] if deck else "Deck"

        dlg = wx.Dialog(self, title=f"Manage Groups — {deck_name}", size=(500, 350))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(dlg, label="Custom card groupings for this deck.\nCards can belong to multiple groups.")
        info.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(info, 0, wx.ALL, 10)

        groups_list = wx.ListCtrl(dlg, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        groups_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        groups_list.SetTextColour(get_wx_color('text_primary'))
        groups_list.InsertColumn(0, "Name", width=200)
        groups_list.InsertColumn(1, "Color", width=80)
        groups_list.InsertColumn(2, "Cards", width=60)
        sizer.Add(groups_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        def refresh_list():
            groups_list.DeleteAllItems()
            groups = self.db.get_card_groups(deck_id)
            for i, group in enumerate(groups):
                idx = groups_list.InsertItem(i, group['name'])
                groups_list.SetItem(idx, 1, group['color'])
                count = len(self.db.get_cards_in_group(group['id']))
                groups_list.SetItem(idx, 2, str(count))
                groups_list.SetItemData(idx, group['id'])

        refresh_list()

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        add_btn = wx.Button(dlg, label="+ Add Group")
        add_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        add_btn.SetForegroundColour(get_wx_color('text_primary'))
        def on_add(evt):
            result = self._show_tag_dialog(dlg, "Add Group")
            if result:
                try:
                    self.db.add_card_group(deck_id, result['name'], result['color'])
                    refresh_list()
                except Exception as e:
                    wx.MessageBox(f"Could not add group: {e}", "Error", wx.OK | wx.ICON_ERROR)
        add_btn.Bind(wx.EVT_BUTTON, on_add)
        btn_sizer.Add(add_btn, 0, wx.RIGHT, 5)

        edit_btn = wx.Button(dlg, label="Edit")
        edit_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        edit_btn.SetForegroundColour(get_wx_color('text_primary'))
        def on_edit(evt):
            sel = groups_list.GetFirstSelected()
            if sel == -1:
                wx.MessageBox("Select a group to edit.", "No Selection", wx.OK | wx.ICON_INFORMATION)
                return
            group_id = groups_list.GetItemData(sel)
            group = self.db.get_card_group(group_id)
            if not group:
                return
            result = self._show_tag_dialog(dlg, "Edit Group", group['name'], group['color'])
            if result:
                try:
                    self.db.update_card_group(group_id, result['name'], result['color'])
                    refresh_list()
                except Exception as e:
                    wx.MessageBox(f"Could not update group: {e}", "Error", wx.OK | wx.ICON_ERROR)
        edit_btn.Bind(wx.EVT_BUTTON, on_edit)
        groups_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, on_edit)
        btn_sizer.Add(edit_btn, 0, wx.RIGHT, 5)

        delete_btn = wx.Button(dlg, label="Delete")
        delete_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        delete_btn.SetForegroundColour(get_wx_color('text_primary'))
        def on_delete(evt):
            sel = groups_list.GetFirstSelected()
            if sel == -1:
                wx.MessageBox("Select a group to delete.", "No Selection", wx.OK | wx.ICON_INFORMATION)
                return
            group_id = groups_list.GetItemData(sel)
            if wx.MessageBox(
                "Delete this group? Cards will be removed from it but not deleted.",
                "Confirm Delete",
                wx.YES_NO | wx.ICON_WARNING
            ) == wx.YES:
                self.db.delete_card_group(group_id)
                refresh_list()
        delete_btn.Bind(wx.EVT_BUTTON, on_delete)
        btn_sizer.Add(delete_btn, 0)

        btn_sizer.AddSpacer(20)

        up_btn = wx.Button(dlg, label="\u25B2 Up")
        up_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        up_btn.SetForegroundColour(get_wx_color('text_primary'))
        def on_move_up(evt):
            sel = groups_list.GetFirstSelected()
            if sel <= 0:
                return
            id_sel = groups_list.GetItemData(sel)
            id_above = groups_list.GetItemData(sel - 1)
            self.db.swap_card_group_order(id_sel, id_above)
            refresh_list()
            groups_list.Select(sel - 1)
            groups_list.EnsureVisible(sel - 1)
        up_btn.Bind(wx.EVT_BUTTON, on_move_up)
        btn_sizer.Add(up_btn, 0, wx.RIGHT, 5)

        down_btn = wx.Button(dlg, label="\u25BC Down")
        down_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        down_btn.SetForegroundColour(get_wx_color('text_primary'))
        def on_move_down(evt):
            sel = groups_list.GetFirstSelected()
            if sel == -1 or sel >= groups_list.GetItemCount() - 1:
                return
            id_sel = groups_list.GetItemData(sel)
            id_below = groups_list.GetItemData(sel + 1)
            self.db.swap_card_group_order(id_sel, id_below)
            refresh_list()
            groups_list.Select(sel + 1)
            groups_list.EnsureVisible(sel + 1)
        down_btn.Bind(wx.EVT_BUTTON, on_move_down)
        btn_sizer.Add(down_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALL, 10)

        close_btn = wx.Button(dlg, wx.ID_CLOSE, "Close")
        close_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        close_btn.SetForegroundColour(get_wx_color('text_primary'))
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: dlg.EndModal(wx.ID_CLOSE))
        sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 10)

        dlg.SetSizer(sizer)
        dlg.ShowModal()
        dlg.Destroy()

        # Refresh the filter dropdown to reflect group changes
        if self._current_deck_id_for_cards:
            self._refresh_cards_display(self._current_deck_id_for_cards)
