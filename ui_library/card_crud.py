"""Card CRUD operations for the library panel."""

from pathlib import Path

import wx
from PIL import Image

from ui_helpers import get_wx_color
from card_dialogs import CardViewDialog, CardEditDialog, BatchEditDialog


class CardCrudMixin:
    """Mixin providing card CRUD operations."""

    def _on_add_card(self, event):
        """Add a new card to the selected deck"""
        # Get deck_id based on current view mode
        deck_id = None
        if self._deck_view_mode == 'image':
            deck_id = self._selected_deck_id
        else:
            idx = self.deck_list.GetFirstSelected()
            if idx != -1:
                deck_id = self.deck_list.GetItemData(idx)

        if not deck_id:
            wx.MessageBox("Select a deck first.", "No Deck", wx.OK | wx.ICON_INFORMATION)
            return

        dlg = wx.TextEntryDialog(self, "Card name:", "Add Card")
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetValue().strip()
            if name:
                file_dlg = wx.FileDialog(self, "Select image (optional)", wildcard="Images|*.jpg;*.jpeg;*.png;*.gif;*.webp")
                image_path = None
                if file_dlg.ShowModal() == wx.ID_OK:
                    image_path = file_dlg.GetPath()
                file_dlg.Destroy()

                self.db.add_card(deck_id, name, image_path)
                if image_path:
                    self.thumb_cache.get_thumbnail(image_path)
                self._refresh_cards_display(deck_id)
        dlg.Destroy()

    def _on_import_cards(self, event):
        """Import multiple card images into the selected deck"""
        # Get deck_id based on current view mode
        deck_id = None
        if self._deck_view_mode == 'image':
            deck_id = self._selected_deck_id
        else:
            idx = self.deck_list.GetFirstSelected()
            if idx != -1:
                deck_id = self.deck_list.GetItemData(idx)

        if not deck_id:
            wx.MessageBox("Select a deck first.", "No Deck", wx.OK | wx.ICON_INFORMATION)
            return

        dlg = wx.FileDialog(self, "Select images", wildcard="Images|*.jpg;*.jpeg;*.png;*.gif;*.webp",
                           style=wx.FD_OPEN | wx.FD_MULTIPLE)
        if dlg.ShowModal() == wx.ID_OK:
            files = dlg.GetPaths()
            existing = self.db.get_cards(deck_id)
            order = len(existing)
            cards = []

            for filepath in files:
                name = Path(filepath).stem.replace('_', ' ').replace('-', ' ').title()
                cards.append((name, filepath, order))
                order += 1

            self.db.bulk_add_cards(deck_id, cards)
            self.thumb_cache.pregenerate_thumbnails([c[1] for c in cards])
            self._refresh_cards_display(deck_id)
            wx.MessageBox(f"Imported {len(cards)} cards.", "Success", wx.OK | wx.ICON_INFORMATION)
        dlg.Destroy()

    def _show_fullsize_image(self, image_path, title="Image"):
        """Show a full-size image in a resizable dialog"""
        from image_utils import load_pil_image

        pil_img = load_pil_image(image_path)
        if pil_img is None:
            wx.MessageBox("Could not load image", "Error", wx.OK | wx.ICON_ERROR)
            return

        orig_width, orig_height = pil_img.size

        # Get screen size to limit dialog size
        display = wx.Display(wx.Display.GetFromWindow(self))
        screen_rect = display.GetClientArea()
        max_dlg_width = int(screen_rect.width * 0.85)
        max_dlg_height = int(screen_rect.height * 0.85)

        # Calculate initial size - fit image to screen with some padding
        padding = 60
        scale = min((max_dlg_width - padding) / orig_width, (max_dlg_height - padding) / orig_height, 1.0)
        initial_width = int(orig_width * scale) + padding
        initial_height = int(orig_height * scale) + padding

        dlg = wx.Dialog(self, title=title, size=(initial_width, initial_height),
                       style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        # Use a scrolled window to allow viewing full image if larger than dialog
        scroll = wx.ScrolledWindow(dlg)
        scroll.SetBackgroundColour(get_wx_color('bg_primary'))
        scroll.SetScrollRate(10, 10)

        # Store original image for resizing
        dlg._pil_img = pil_img
        dlg._scroll = scroll
        dlg._bitmap = None

        def update_image():
            """Update the displayed image based on dialog size"""
            dlg_width, dlg_height = dlg.GetClientSize()
            img_width, img_height = dlg._pil_img.size

            # Scale image to fit dialog while preserving aspect ratio
            scale = min((dlg_width - 20) / img_width, (dlg_height - 20) / img_height, 1.0)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            # Resize and convert
            scaled_img = dlg._pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            if scaled_img.mode != 'RGB':
                scaled_img = scaled_img.convert('RGB')

            wx_img = wx.Image(new_width, new_height)
            wx_img.SetData(scaled_img.tobytes())

            # Update or create bitmap
            if dlg._bitmap:
                dlg._bitmap.SetBitmap(wx.Bitmap(wx_img))
            else:
                dlg._bitmap = wx.StaticBitmap(scroll, bitmap=wx.Bitmap(wx_img))

            scroll.SetVirtualSize((new_width, new_height))
            scroll.Refresh()

        # Initial display
        update_image()

        # Update on resize
        def on_resize(e):
            update_image()
            e.Skip()
        dlg.Bind(wx.EVT_SIZE, on_resize)

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(scroll, 1, wx.EXPAND)
        dlg.SetSizer(sizer)

        # Close on Escape
        def on_key(e):
            if e.GetKeyCode() == wx.WXK_ESCAPE:
                dlg.Close()
            else:
                e.Skip()
        dlg.Bind(wx.EVT_CHAR_HOOK, on_key)

        dlg.ShowModal()
        dlg.Destroy()

    def _on_view_card(self, event, card_id, return_after_edit=False):
        """Show a card detail view with full-size image and all metadata"""
        if not card_id:
            return

        # Get the sorted list of cards for navigation
        card_list = self._current_cards_sorted if hasattr(self, '_current_cards_sorted') else []
        card_ids = [c['id'] for c in card_list]

        # Create and show the dialog
        dlg = CardViewDialog(
            self, self.db, self.thumb_cache, card_id,
            card_ids=card_ids,
            on_fullsize_callback=self._show_fullsize_image
        )

        result = dlg.ShowModal()
        final_card_id = dlg.get_current_card_id()
        edit_requested = dlg.edit_requested
        dlg.Destroy()

        # Handle edit request
        if edit_requested:
            self._on_edit_card(None, final_card_id, return_to_view=True)

    def _on_edit_card(self, event, card_id=None, return_to_view=False, selected_tab=0, dialog_pos=None, dialog_size=None):
        """Edit a card using the CardEditDialog, or BatchEditDialog for multiple cards"""
        # Batch edit: multiple cards selected and no specific card_id passed
        if card_id is None and len(self.selected_card_ids) > 1:
            # Sort selected cards in deck order so thumbnails appear consistently
            card_list = self._current_cards_sorted if hasattr(self, '_current_cards_sorted') else []
            deck_order = [c['id'] for c in card_list]
            sorted_ids = sorted(self.selected_card_ids, key=lambda cid: deck_order.index(cid) if cid in deck_order else cid)

            # Get deck_id from the first selected card
            first_card = self.db.get_card_with_metadata(sorted_ids[0])
            if not first_card:
                return
            deck_id = first_card['deck_id']

            dlg = BatchEditDialog(self, self.db, self.thumb_cache, sorted_ids, deck_id)
            result = dlg.ShowModal()
            applied = dlg.applied
            dlg.Destroy()

            if applied:
                self._refresh_cards_display(deck_id, preserve_scroll=True)
            return

        if card_id is None:
            # Get first selected card
            if self.selected_card_ids:
                card_id = next(iter(self.selected_card_ids))
            else:
                card_id = None

        if not card_id:
            wx.MessageBox("Select a card to edit.", "No Card", wx.OK | wx.ICON_INFORMATION)
            return

        # Get card with full metadata first
        card = self.db.get_card_with_metadata(card_id)
        if not card:
            return

        deck_id = card['deck_id']
        if not deck_id:
            return

        # Get the sorted list of cards for navigation
        card_list = self._current_cards_sorted if hasattr(self, '_current_cards_sorted') else []
        card_ids = [c['id'] for c in card_list]

        # Create refresh callback
        def refresh_callback():
            self._refresh_cards_display(deck_id, preserve_scroll=True)

        # Create and show the dialog
        dlg = CardEditDialog(
            self, self.db, self.thumb_cache, card_id,
            card_ids=card_ids,
            on_refresh_callback=refresh_callback,
            selected_tab=selected_tab
        )

        result = dlg.ShowModal()
        final_card_id = dlg.get_current_card_id()
        save_requested = dlg.save_requested
        dlg.Destroy()

        # Refresh display after save
        if save_requested:
            self._refresh_cards_display(deck_id, preserve_scroll=True)

        # Return to card view if requested
        if return_to_view:
            self._on_view_card(None, final_card_id)

    def _on_delete_card(self, event):
        """Delete the selected card(s)"""
        if not self.selected_card_ids:
            wx.MessageBox("Select card(s) to delete.", "No Card", wx.OK | wx.ICON_INFORMATION)
            return

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

        count = len(self.selected_card_ids)
        msg = f"Delete {count} card(s)?" if count > 1 else "Delete this card?"

        if wx.MessageBox(msg, "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            for card_id in self.selected_card_ids:
                self.db.delete_card(card_id)
            self.selected_card_ids = set()
            self._refresh_cards_display(deck_id)
