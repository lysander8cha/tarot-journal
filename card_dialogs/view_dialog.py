"""Card view dialog for viewing card details."""

import json

import wx

from ui_helpers import logger, _cfg, get_wx_color
from image_utils import load_and_scale_image


class CardViewDialog(wx.Dialog):
    """
    Dialog for viewing card details with navigation support.
    Updates content in-place when navigating between cards to preserve window position.
    """
    def __init__(self, parent, db, thumb_cache, card_id, card_ids=None, on_edit_callback=None, on_fullsize_callback=None):
        super().__init__(parent, title="Card Info", size=(700, 550),
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetBackgroundColour(get_wx_color('bg_primary'))

        self.db = db
        self.thumb_cache = thumb_cache
        self.card_ids = card_ids or []
        self.current_card_id = card_id
        self.on_edit_callback = on_edit_callback
        self.on_fullsize_callback = on_fullsize_callback
        self.edit_requested = False

        self._build_ui()
        self._load_card(card_id)

    def _build_ui(self):
        """Build the dialog UI structure (called once)"""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Content area - horizontal split
        self.content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: Image panel (fixed structure, content updates)
        self.image_panel = wx.Panel(self)
        self.image_panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.image_sizer = wx.BoxSizer(wx.VERTICAL)
        self.image_panel.SetSizer(self.image_sizer)
        self.content_sizer.Add(self.image_panel, 0, wx.EXPAND | wx.ALL, 10)

        # Right side: Info panel (scrollable, content updates)
        self.info_panel = wx.ScrolledWindow(self)
        self.info_panel.SetScrollRate(0, 10)
        self.info_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        self.info_sizer = wx.BoxSizer(wx.VERTICAL)
        self.info_panel.SetSizer(self.info_sizer)
        self.content_sizer.Add(self.info_panel, 1, wx.EXPAND | wx.ALL, 10)

        self.main_sizer.Add(self.content_sizer, 1, wx.EXPAND)

        # Button row
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Navigation buttons on the left
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.prev_btn = wx.Button(self, label="< Prev")
        self.prev_btn.Bind(wx.EVT_BUTTON, self._on_prev)
        nav_sizer.Add(self.prev_btn, 0, wx.RIGHT, 5)

        self.next_btn = wx.Button(self, label="Next >")
        self.next_btn.Bind(wx.EVT_BUTTON, self._on_next)
        nav_sizer.Add(self.next_btn, 0)

        btn_sizer.Add(nav_sizer, 0, wx.RIGHT, 20)
        btn_sizer.AddStretchSpacer()

        # Action buttons on the right
        edit_btn = wx.Button(self, label="Edit Card")
        edit_btn.Bind(wx.EVT_BUTTON, self._on_edit)
        btn_sizer.Add(edit_btn, 0, wx.RIGHT, 10)

        close_btn = wx.Button(self, wx.ID_CANCEL, "Close")
        btn_sizer.Add(close_btn, 0)

        self.main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 15)

        self.SetSizer(self.main_sizer)

    def _load_card(self, card_id):
        """Load and display a card's information"""
        self.current_card_id = card_id

        # Get card data
        card = self.db.get_card_with_metadata(card_id)
        if not card:
            return

        deck_id = card['deck_id']
        deck = self.db.get_deck(deck_id)
        if not deck:
            return

        cartomancy_type = deck['cartomancy_type_name']

        # Update window title
        self.SetTitle(f"Card: {card['name']}")

        # Helper to safely get card fields
        def get_field(field_name, default=''):
            try:
                if field_name in card.keys():
                    return card[field_name] if card[field_name] is not None else default
            except (KeyError, TypeError):
                pass
            return default

        # Clear and rebuild image panel
        self.image_sizer.Clear(True)

        image_path = card['image_path']
        _card_info_sz = _cfg.get('images', 'card_info_max', [300, 450])
        wx_bitmap = load_and_scale_image(image_path, tuple(_card_info_sz), as_wx_bitmap=True)

        if wx_bitmap:
            bmp = wx.StaticBitmap(self.image_panel, bitmap=wx_bitmap)
            bmp.SetCursor(wx.Cursor(wx.CURSOR_HAND))
            bmp.SetToolTip("Click to view larger")

            def on_image_click(e, img_path=image_path, name=card['name']):
                if self.on_fullsize_callback:
                    self.on_fullsize_callback(img_path, name)
            bmp.Bind(wx.EVT_LEFT_DOWN, on_image_click)

            self.image_sizer.Add(bmp, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        else:
            self._add_placeholder_image()

        self.image_panel.Layout()

        # Clear and rebuild info panel
        self.info_sizer.Clear(True)

        # Card name
        name_label = wx.StaticText(self.info_panel, label=card['name'])
        name_label.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        self.info_sizer.Add(name_label, 0, wx.BOTTOM, 10)

        # Deck name
        deck_label = wx.StaticText(self.info_panel, label=f"Deck: {deck['name']}")
        deck_label.SetForegroundColour(get_wx_color('text_secondary'))
        self.info_sizer.Add(deck_label, 0, wx.BOTTOM, 15)

        # Separator
        sep1 = wx.StaticLine(self.info_panel)
        self.info_sizer.Add(sep1, 0, wx.EXPAND | wx.BOTTOM, 15)

        # Classification section
        class_title = wx.StaticText(self.info_panel, label="Classification")
        class_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        class_title.SetForegroundColour(get_wx_color('accent'))
        self.info_sizer.Add(class_title, 0, wx.BOTTOM, 8)

        # Archetype
        archetype = get_field('archetype', '')
        if archetype:
            self._add_info_row("Archetype", archetype)

        # Rank / Hexagram Number
        rank = get_field('rank', '')
        if rank:
            rank_label = "Hexagram Number" if cartomancy_type == 'I Ching' else "Rank"
            self._add_info_row(rank_label, str(rank))

        # Suit / Pinyin
        suit = get_field('suit', '')
        if suit:
            suit_label = "Pinyin" if cartomancy_type == 'I Ching' else "Suit"
            self._add_info_row(suit_label, suit)

        # I Ching specific fields
        if cartomancy_type == 'I Ching':
            custom_fields_json = get_field('custom_fields', None)
            if custom_fields_json:
                try:
                    iching_custom = json.loads(custom_fields_json)
                    trad = iching_custom.get('traditional_chinese', '')
                    if trad:
                        self._add_info_row("Traditional Chinese", trad, font_size=12)
                    simp = iching_custom.get('simplified_chinese', '')
                    if simp:
                        self._add_info_row("Simplified Chinese", simp, font_size=12)
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning("Failed to parse I Ching custom fields for card %s: %s", card_id, e)

        # Sort order
        sort_order = get_field('card_order', 0)
        self._add_info_row("Sort Order", str(sort_order))

        # Notes section
        notes = get_field('notes', '')
        if notes:
            sep2 = wx.StaticLine(self.info_panel)
            self.info_sizer.Add(sep2, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)

            notes_title = wx.StaticText(self.info_panel, label="Notes")
            notes_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            notes_title.SetForegroundColour(get_wx_color('accent'))
            self.info_sizer.Add(notes_title, 0, wx.BOTTOM, 8)

            notes_text = wx.StaticText(self.info_panel, label=notes)
            notes_text.SetForegroundColour(get_wx_color('text_primary'))
            notes_text.Wrap(280)
            self.info_sizer.Add(notes_text, 0, wx.BOTTOM, 15)

        # Custom fields section
        custom_fields_json = get_field('custom_fields', None)
        if custom_fields_json:
            try:
                custom_fields = json.loads(custom_fields_json)
                # Filter out I Ching specific fields already displayed
                display_fields = {k: v for k, v in custom_fields.items()
                                 if k not in ('traditional_chinese', 'simplified_chinese')
                                 and v is not None and str(v).strip()}
                if display_fields:
                    sep3 = wx.StaticLine(self.info_panel)
                    self.info_sizer.Add(sep3, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)

                    cf_title = wx.StaticText(self.info_panel, label="Custom Fields")
                    cf_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                    cf_title.SetForegroundColour(get_wx_color('accent'))
                    self.info_sizer.Add(cf_title, 0, wx.BOTTOM, 8)

                    for field_name, field_value in display_fields.items():
                        cf_lbl = wx.StaticText(self.info_panel, label=f"{field_name}:")
                        cf_lbl.SetForegroundColour(get_wx_color('text_secondary'))
                        self.info_sizer.Add(cf_lbl, 0, wx.BOTTOM, 3)
                        cf_val = wx.StaticText(self.info_panel, label=str(field_value))
                        cf_val.SetForegroundColour(get_wx_color('text_primary'))
                        cf_val.Wrap(280)
                        self.info_sizer.Add(cf_val, 0, wx.BOTTOM, 10)
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("Failed to display custom fields for card %s: %s", card_id, e)

        # Tags section
        inherited_tags = self.db.get_inherited_tags_for_card(card_id)
        card_tags = self.db.get_tags_for_card(card_id)

        if inherited_tags or card_tags:
            sep4 = wx.StaticLine(self.info_panel)
            self.info_sizer.Add(sep4, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)

            tags_title = wx.StaticText(self.info_panel, label="Tags")
            tags_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            tags_title.SetForegroundColour(get_wx_color('accent'))
            self.info_sizer.Add(tags_title, 0, wx.BOTTOM, 8)

            if inherited_tags:
                self._add_info_row("Deck Tags", ", ".join([t['name'] for t in inherited_tags]))
            if card_tags:
                self._add_info_row("Card Tags", ", ".join([t['name'] for t in card_tags]))

        # Groups section
        card_groups = self.db.get_groups_for_card(card_id)
        if card_groups:
            sep5 = wx.StaticLine(self.info_panel)
            self.info_sizer.Add(sep5, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)

            groups_title = wx.StaticText(self.info_panel, label="Groups")
            groups_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            groups_title.SetForegroundColour(get_wx_color('accent'))
            self.info_sizer.Add(groups_title, 0, wx.BOTTOM, 8)

            self._add_info_row("Member of", ", ".join([g['name'] for g in card_groups]))

        self.info_panel.Layout()
        self.info_panel.FitInside()
        self.info_panel.Scroll(0, 0)  # Reset scroll position

        # Update navigation buttons
        self._update_nav_buttons()

    def _add_placeholder_image(self):
        """Add a placeholder when no image is available"""
        no_img = wx.StaticText(self.image_panel, label="🂠")
        no_img.SetFont(wx.Font(72, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        no_img.SetForegroundColour(get_wx_color('text_dim'))
        self.image_sizer.Add(no_img, 0, wx.ALL | wx.ALIGN_CENTER, 10)

    def _add_info_row(self, label, value, font_size=None):
        """Add a label: value row to the info panel"""
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(self.info_panel, label=f"{label}: ")
        lbl.SetForegroundColour(get_wx_color('text_secondary'))
        row.Add(lbl, 0)
        val = wx.StaticText(self.info_panel, label=value)
        val.SetForegroundColour(get_wx_color('text_primary'))
        if font_size:
            val.SetFont(wx.Font(font_size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        row.Add(val, 0)
        self.info_sizer.Add(row, 0, wx.BOTTOM, 5)

    def _update_nav_buttons(self):
        """Update prev/next button enabled state"""
        if not self.card_ids:
            self.prev_btn.Disable()
            self.next_btn.Disable()
            return

        try:
            current_index = self.card_ids.index(self.current_card_id)
        except ValueError:
            current_index = -1

        self.prev_btn.Enable(current_index > 0)
        self.next_btn.Enable(current_index >= 0 and current_index < len(self.card_ids) - 1)

    def _on_prev(self, event):
        """Navigate to previous card"""
        if not self.card_ids:
            return
        try:
            current_index = self.card_ids.index(self.current_card_id)
            if current_index > 0:
                self._load_card(self.card_ids[current_index - 1])
        except ValueError:
            pass

    def _on_next(self, event):
        """Navigate to next card"""
        if not self.card_ids:
            return
        try:
            current_index = self.card_ids.index(self.current_card_id)
            if current_index < len(self.card_ids) - 1:
                self._load_card(self.card_ids[current_index + 1])
        except ValueError:
            pass

    def _on_edit(self, event):
        """Handle edit button click"""
        self.edit_requested = True
        self.EndModal(wx.ID_OK)

    def get_current_card_id(self):
        """Return the currently displayed card ID"""
        return self.current_card_id
