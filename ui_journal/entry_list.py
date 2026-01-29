"""Entry list management for the journal panel."""

from datetime import datetime

import wx

from ui_helpers import logger, get_wx_color


class EntryListMixin:
    """Mixin providing entry list management functionality."""

    def _refresh_entries_list(self):
        self.entry_list.DeleteAllItems()

        search = self.search_ctrl.GetValue()
        tag_idx = self.tag_filter.GetSelection()
        tag_ids = None

        if tag_idx > 0:
            tags = self.db.get_tags()
            if tag_idx - 1 < len(tags):
                tag_ids = [tags[tag_idx - 1]['id']]

        if search or tag_ids:
            entries = self.db.search_entries(query=search if search else None, tag_ids=tag_ids)
        else:
            entries = self.db.get_entries()

        for entry in entries:
            # Use reading_datetime if available, otherwise created_at
            reading_dt = entry['reading_datetime'] if 'reading_datetime' in entry.keys() and entry['reading_datetime'] else None
            if reading_dt:
                try:
                    dt = datetime.fromisoformat(reading_dt)
                    date_str = dt.strftime('%Y-%m-%d %H:%M')
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse reading datetime: %s", e)
                    date_str = reading_dt[:16] if reading_dt else ''
            elif entry['created_at']:
                date_str = entry['created_at'][:10]
            else:
                date_str = ''
            title = entry['title'] or '(Untitled)'
            idx = self.entry_list.InsertItem(self.entry_list.GetItemCount(), date_str)
            self.entry_list.SetItem(idx, 1, title)
            self.entry_list.SetItemData(idx, entry['id'])


    def _refresh_tags_list(self):
        tags = self.db.get_tags()
        self.tag_filter.Clear()
        self.tag_filter.Append("All Tags")
        for tag in tags:
            self.tag_filter.Append(tag['name'])
        self.tag_filter.SetSelection(0)

    def _update_deck_choice(self):
        """Update the deck map for use in dialogs"""
        decks = self.db.get_decks()
        self._deck_map = {}
        for deck in decks:
            name = deck['name']
            self._deck_map[name] = deck['id']


    def _update_spread_choice(self):
        """Update the spread map for use in dialogs"""
        spreads = self.db.get_spreads()
        self._spread_map = {}
        for spread in spreads:
            self._spread_map[spread['name']] = spread['id']


    def _on_search(self, event):
        self._refresh_entries_list()

    def _on_tag_filter(self, event):
        self._refresh_entries_list()

    def _on_entry_select(self, event):
        idx = event.GetIndex()
        entry_id = self.entry_list.GetItemData(idx)
        self.current_entry_id = entry_id
        self._display_entry_in_viewer(entry_id)

    def _on_delete_entry(self, event):
        if not self.current_entry_id:
            return

        if wx.MessageBox("Delete this entry?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.db.delete_entry(self.current_entry_id)
            self.current_entry_id = None
            # Clear viewer
            self.viewer_sizer.Clear(True)
            placeholder = wx.StaticText(self.viewer_panel, label="Select an entry to view")
            placeholder.SetForegroundColour(get_wx_color('text_secondary'))
            placeholder.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
            self.viewer_sizer.Add(placeholder, 0, wx.ALL, 20)
            self.viewer_panel.Layout()
            self._refresh_entries_list()
