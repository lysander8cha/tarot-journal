"""Batch edit dialog for editing multiple cards at once."""

import json
import os

import wx
import wx.lib.scrolledpanel as scrolled

from ui_helpers import get_wx_color


class BatchEditDialog(wx.Dialog):
    """Dialog for editing multiple cards at once."""

    # Rank/suit options per deck type
    RANKS = {
        'Tarot': ['', 'Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                  'Eight', 'Nine', 'Ten',
                  'Page / Knave / Princess / Court Rank 1',
                  'Knight / Prince / Court Rank 2',
                  'Queen / Court Rank 3', 'King / Court Rank 4',
                  '0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX',
                  'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII',
                  'XIX', 'XX', 'XXI'],
        'Playing Cards': ['', 'Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                          'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King', 'Joker'],
        'Lenormand': ['', '2', '3', '4', '5', '6', '7', '8', '9', '10',
                      'Jack', 'Queen', 'King', 'Ace'],
        'I Ching': [''] + [str(i) for i in range(1, 65)],
    }
    SUITS = {
        'Tarot': ['', 'Major Arcana', 'Wands', 'Cups', 'Swords', 'Pentacles'],
        'Playing Cards': ['', 'Hearts', 'Diamonds', 'Clubs', 'Spades'],
        'Lenormand': ['', 'Hearts', 'Diamonds', 'Clubs', 'Spades'],
    }

    def __init__(self, parent, db, thumb_cache, card_ids, deck_id):
        count = len(card_ids)
        super().__init__(parent, title=f"Batch Edit ({count} cards)",
                         size=(650, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetBackgroundColour(get_wx_color('bg_primary'))
        self.db = db
        self.thumb_cache = thumb_cache
        self.card_ids = card_ids
        self.deck_id = deck_id
        self.applied = False

        # Determine deck type
        deck = self.db.get_deck(deck_id)
        self.cartomancy_type = deck['cartomancy_type_name'] if deck else 'Tarot'

        # Controls storage
        self._tag_add_cbs = []
        self._tag_remove_cbs = []
        self._group_add_cbs = []
        self._group_remove_cbs = []
        self._all_tags = []
        self._all_groups = []
        self._enable_cbs = {}   # field_name -> wx.CheckBox
        self._field_ctrls = {}  # field_name -> control widget
        self._notes_mode = None  # radio button for append
        self._custom_field_cbs = {}
        self._custom_field_ctrls = {}

        self._build_ui()

    def _build_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Scrollable content area
        scroll = scrolled.ScrolledPanel(self)
        scroll.SetBackgroundColour(get_wx_color('bg_primary'))
        scroll.SetupScrolling(scroll_x=False)
        content = wx.BoxSizer(wx.VERTICAL)

        self._build_card_preview(scroll, content)
        self._build_tags_section(scroll, content)
        self._build_groups_section(scroll, content)
        self._build_classification_section(scroll, content)
        self._build_notes_section(scroll, content)
        self._build_custom_fields_section(scroll, content)

        scroll.SetSizer(content)
        main_sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 5)

        # Bottom buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        cancel_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        cancel_btn.SetForegroundColour(get_wx_color('text_primary'))
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)

        apply_btn = wx.Button(self, wx.ID_OK, "Apply to All")
        apply_btn.SetBackgroundColour(get_wx_color('bg_secondary'))
        apply_btn.SetForegroundColour(get_wx_color('text_primary'))
        apply_btn.Bind(wx.EVT_BUTTON, self._on_apply)
        btn_sizer.Add(apply_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(main_sizer)

    def _add_section_header(self, parent, sizer, label):
        sep = wx.StaticLine(parent)
        sizer.Add(sep, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        title = wx.StaticText(parent, label=label)
        title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(get_wx_color('accent'))
        sizer.Add(title, 0, wx.LEFT | wx.BOTTOM, 10)

    def _make_enable_row(self, parent, sizer, field_name, label_text):
        """Create a row with an enable checkbox + label. Returns the sizer for the row."""
        row = wx.BoxSizer(wx.HORIZONTAL)
        cb = wx.CheckBox(parent, label="")
        row.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        lbl = wx.StaticText(parent, label=label_text)
        lbl.SetForegroundColour(get_wx_color('text_primary'))
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self._enable_cbs[field_name] = cb
        return row

    # ── Card Preview ──────────────────────────────────────

    def _build_card_preview(self, parent, sizer):
        preview = scrolled.ScrolledPanel(parent, size=(-1, 120))
        preview.SetBackgroundColour(get_wx_color('bg_secondary'))
        preview.SetupScrolling(scroll_y=False)
        strip = wx.BoxSizer(wx.HORIZONTAL)

        for card_id in self.card_ids:
            card = self.db.get_card_with_metadata(card_id)
            if not card:
                continue

            item = wx.BoxSizer(wx.VERTICAL)

            # Thumbnail
            bmp = None
            image_path = card['image_path']
            if image_path and os.path.exists(image_path):
                thumb_path = self.thumb_cache.get_thumbnail_path(image_path)
                if thumb_path and os.path.exists(thumb_path):
                    img = wx.Image(thumb_path, wx.BITMAP_TYPE_ANY)
                    w, h = img.GetSize()
                    max_w, max_h = 60, 90
                    scale = min(max_w / w, max_h / h)
                    img = img.Scale(int(w * scale), int(h * scale), wx.IMAGE_QUALITY_HIGH)
                    bmp = wx.StaticBitmap(preview, bitmap=img.ConvertToBitmap())

            if not bmp:
                placeholder = wx.StaticText(preview, label="\U0001F0A0", size=(60, 90))
                placeholder.SetForegroundColour(get_wx_color('text_dim'))
                placeholder.SetFont(wx.Font(28, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                item.Add(placeholder, 0, wx.ALIGN_CENTER_HORIZONTAL)
            else:
                item.Add(bmp, 0, wx.ALIGN_CENTER_HORIZONTAL)

            # Name (truncated)
            name = card['name']
            if len(name) > 12:
                name = name[:11] + "\u2026"
            name_lbl = wx.StaticText(preview, label=name)
            name_lbl.SetForegroundColour(get_wx_color('text_primary'))
            name_lbl.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            item.Add(name_lbl, 0, wx.ALIGN_CENTER_HORIZONTAL)

            strip.Add(item, 0, wx.ALL, 4)

        preview.SetSizer(strip)
        sizer.Add(preview, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

    # ── Tags ──────────────────────────────────────────────

    def _build_tags_section(self, parent, sizer):
        self._all_tags = list(self.db.get_card_tags())
        if not self._all_tags:
            return

        self._add_section_header(parent, sizer, "Tags")

        # Add row
        add_label = wx.StaticText(parent, label="Add:")
        add_label.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(add_label, 0, wx.LEFT, 10)
        add_wrap = wx.WrapSizer(wx.HORIZONTAL)
        for tag in self._all_tags:
            cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
            cb = wx.CheckBox(parent, label="")
            cb_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
            lbl = wx.StaticText(parent, label=tag['name'])
            lbl.SetForegroundColour(get_wx_color('text_primary'))
            cb_sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            add_wrap.Add(cb_sizer, 0, wx.TOP, 2)
            self._tag_add_cbs.append(cb)
        sizer.Add(add_wrap, 0, wx.LEFT | wx.RIGHT, 20)

        # Remove row
        rm_label = wx.StaticText(parent, label="Remove:")
        rm_label.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(rm_label, 0, wx.LEFT | wx.TOP, 10)
        rm_wrap = wx.WrapSizer(wx.HORIZONTAL)
        for tag in self._all_tags:
            cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
            cb = wx.CheckBox(parent, label="")
            cb_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
            lbl = wx.StaticText(parent, label=tag['name'])
            lbl.SetForegroundColour(get_wx_color('text_primary'))
            cb_sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            rm_wrap.Add(cb_sizer, 0, wx.TOP, 2)
            self._tag_remove_cbs.append(cb)
        sizer.Add(rm_wrap, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

    # ── Groups ────────────────────────────────────────────

    def _build_groups_section(self, parent, sizer):
        self._all_groups = list(self.db.get_card_groups(self.deck_id))
        if not self._all_groups:
            return

        self._add_section_header(parent, sizer, "Groups")

        add_label = wx.StaticText(parent, label="Add:")
        add_label.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(add_label, 0, wx.LEFT, 10)
        add_wrap = wx.WrapSizer(wx.HORIZONTAL)
        for group in self._all_groups:
            cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
            cb = wx.CheckBox(parent, label="")
            cb_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
            lbl = wx.StaticText(parent, label=group['name'])
            lbl.SetForegroundColour(get_wx_color('text_primary'))
            cb_sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            add_wrap.Add(cb_sizer, 0, wx.TOP, 2)
            self._group_add_cbs.append(cb)
        sizer.Add(add_wrap, 0, wx.LEFT | wx.RIGHT, 20)

        rm_label = wx.StaticText(parent, label="Remove:")
        rm_label.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(rm_label, 0, wx.LEFT | wx.TOP, 10)
        rm_wrap = wx.WrapSizer(wx.HORIZONTAL)
        for group in self._all_groups:
            cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
            cb = wx.CheckBox(parent, label="")
            cb_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
            lbl = wx.StaticText(parent, label=group['name'])
            lbl.SetForegroundColour(get_wx_color('text_primary'))
            cb_sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            rm_wrap.Add(cb_sizer, 0, wx.TOP, 2)
            self._group_remove_cbs.append(cb)
        sizer.Add(rm_wrap, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

    # ── Classification ────────────────────────────────────

    def _build_classification_section(self, parent, sizer):
        self._add_section_header(parent, sizer, "Classification")

        # Archetype
        arch_row = self._make_enable_row(parent, sizer, 'archetype', "Archetype:")
        arch_ctrl = wx.TextCtrl(parent)
        arch_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        arch_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        arch_row.Add(arch_ctrl, 1)
        sizer.Add(arch_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        self._field_ctrls['archetype'] = arch_ctrl

        # Rank (deck-type-specific)
        ranks = self.RANKS.get(self.cartomancy_type)
        if ranks:
            rank_label = "Hexagram Number:" if self.cartomancy_type == 'I Ching' else "Rank:"
            rank_row = self._make_enable_row(parent, sizer, 'rank', rank_label)
            rank_ctrl = wx.Choice(parent, choices=ranks)
            rank_row.Add(rank_ctrl, 1)
            sizer.Add(rank_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
            self._field_ctrls['rank'] = rank_ctrl

        # Suit
        suits = self.SUITS.get(self.cartomancy_type)
        if self.cartomancy_type == 'I Ching':
            suit_row = self._make_enable_row(parent, sizer, 'suit', "Pinyin:")
            suit_ctrl = wx.TextCtrl(parent)
            suit_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
            suit_ctrl.SetForegroundColour(get_wx_color('text_primary'))
            suit_row.Add(suit_ctrl, 1)
            sizer.Add(suit_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
            self._field_ctrls['suit'] = suit_ctrl
        elif suits:
            suit_label = "Playing Card Suit:" if self.cartomancy_type == 'Lenormand' else "Suit:"
            suit_row = self._make_enable_row(parent, sizer, 'suit', suit_label)
            suit_ctrl = wx.Choice(parent, choices=suits)
            suit_row.Add(suit_ctrl, 1)
            sizer.Add(suit_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
            self._field_ctrls['suit'] = suit_ctrl

    # ── Notes ─────────────────────────────────────────────

    def _build_notes_section(self, parent, sizer):
        self._add_section_header(parent, sizer, "Notes")

        top_row = wx.BoxSizer(wx.HORIZONTAL)
        cb = wx.CheckBox(parent, label="")
        top_row.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self._enable_cbs['notes'] = cb

        notes_label = wx.StaticText(parent, label="Notes:")
        notes_label.SetForegroundColour(get_wx_color('text_primary'))
        top_row.Add(notes_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        # Append / Replace radio buttons
        rb_append = wx.RadioButton(parent, label="", style=wx.RB_GROUP)
        rb_append.SetValue(True)
        top_row.Add(rb_append, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        append_lbl = wx.StaticText(parent, label="Append")
        append_lbl.SetForegroundColour(get_wx_color('text_primary'))
        top_row.Add(append_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        rb_replace = wx.RadioButton(parent, label="")
        top_row.Add(rb_replace, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        replace_lbl = wx.StaticText(parent, label="Replace")
        replace_lbl.SetForegroundColour(get_wx_color('text_primary'))
        top_row.Add(replace_lbl, 0, wx.ALIGN_CENTER_VERTICAL)

        self._notes_mode = rb_append
        sizer.Add(top_row, 0, wx.LEFT | wx.RIGHT, 10)

        notes_ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE, size=(-1, 80))
        notes_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        notes_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(notes_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self._field_ctrls['notes'] = notes_ctrl

    # ── Custom Fields ─────────────────────────────────────

    def _build_custom_fields_section(self, parent, sizer):
        custom_fields = self.db.get_deck_custom_fields(self.deck_id)
        if not custom_fields:
            return

        self._add_section_header(parent, sizer, "Custom Fields")

        for field in custom_fields:
            fname = field['field_name']
            ftype = field['field_type']

            row = wx.BoxSizer(wx.HORIZONTAL)
            cb = wx.CheckBox(parent, label="")
            row.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            lbl = wx.StaticText(parent, label=f"{fname}:")
            lbl.SetForegroundColour(get_wx_color('text_primary'))
            row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

            ctrl = None
            if ftype == 'checkbox':
                ctrl = wx.CheckBox(parent, label="")
            elif ftype == 'number':
                ctrl = wx.SpinCtrl(parent, min=-9999, max=9999)
            elif ftype == 'select':
                options = ['']
                if field['field_options']:
                    try:
                        options += json.loads(field['field_options'])
                    except (json.JSONDecodeError, ValueError):
                        pass
                ctrl = wx.Choice(parent, choices=options)
            elif ftype == 'multiline':
                ctrl = wx.TextCtrl(parent, style=wx.TE_MULTILINE, size=(-1, 60))
                ctrl.SetBackgroundColour(get_wx_color('bg_input'))
                ctrl.SetForegroundColour(get_wx_color('text_primary'))
            else:
                ctrl = wx.TextCtrl(parent)
                ctrl.SetBackgroundColour(get_wx_color('bg_input'))
                ctrl.SetForegroundColour(get_wx_color('text_primary'))

            if ctrl:
                if ftype == 'multiline':
                    row.Add(ctrl, 1, wx.EXPAND)
                else:
                    row.Add(ctrl, 1)

            sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
            self._custom_field_cbs[fname] = cb
            self._custom_field_ctrls[fname] = (ctrl, ftype)

    # ── Apply Logic ───────────────────────────────────────

    def _on_apply(self, event):
        """Apply batch changes to all selected cards."""
        # Gather which tags/groups to add/remove
        tags_to_add = {self._all_tags[i]['id'] for i, cb in enumerate(self._tag_add_cbs) if cb.GetValue()}
        tags_to_remove = {self._all_tags[i]['id'] for i, cb in enumerate(self._tag_remove_cbs) if cb.GetValue()}
        groups_to_add = {self._all_groups[i]['id'] for i, cb in enumerate(self._group_add_cbs) if cb.GetValue()}
        groups_to_remove = {self._all_groups[i]['id'] for i, cb in enumerate(self._group_remove_cbs) if cb.GetValue()}

        # Classification values (only if enabled)
        set_archetype = None
        if self._enable_cbs.get('archetype') and self._enable_cbs['archetype'].GetValue():
            set_archetype = self._field_ctrls['archetype'].GetValue().strip() or None

        set_rank = None
        if self._enable_cbs.get('rank') and self._enable_cbs['rank'].GetValue():
            ctrl = self._field_ctrls['rank']
            if isinstance(ctrl, wx.Choice):
                sel = ctrl.GetSelection()
                set_rank = ctrl.GetString(sel) if sel > 0 else None
            else:
                set_rank = ctrl.GetValue().strip() or None

        set_suit = None
        if self._enable_cbs.get('suit') and self._enable_cbs['suit'].GetValue():
            ctrl = self._field_ctrls['suit']
            if isinstance(ctrl, wx.Choice):
                sel = ctrl.GetSelection()
                set_suit = ctrl.GetString(sel) if sel > 0 else None
            else:
                set_suit = ctrl.GetValue().strip() or None

        # Notes
        set_notes = None
        notes_append = True
        if self._enable_cbs.get('notes') and self._enable_cbs['notes'].GetValue():
            set_notes = self._field_ctrls['notes'].GetValue()
            notes_append = self._notes_mode.GetValue()

        # Custom fields
        custom_updates = {}
        for fname, cb in self._custom_field_cbs.items():
            if cb.GetValue():
                ctrl, ftype = self._custom_field_ctrls[fname]
                if ftype == 'checkbox':
                    custom_updates[fname] = ctrl.GetValue()
                elif ftype == 'number':
                    custom_updates[fname] = ctrl.GetValue()
                elif ftype == 'select':
                    sel = ctrl.GetSelection()
                    custom_updates[fname] = ctrl.GetString(sel) if sel > 0 else ''
                else:
                    custom_updates[fname] = ctrl.GetValue()

        # Check if anything was actually selected
        has_changes = (tags_to_add or tags_to_remove or groups_to_add or groups_to_remove
                       or set_archetype is not None or set_rank is not None
                       or set_suit is not None or set_notes is not None
                       or custom_updates)
        if not has_changes:
            wx.MessageBox("No changes selected.", "Nothing to Apply", wx.OK | wx.ICON_INFORMATION)
            return

        # Apply to each card
        for card_id in self.card_ids:
            # Tags
            if tags_to_add or tags_to_remove:
                current = {t['id'] for t in self.db.get_tags_for_card(card_id)}
                updated = (current | tags_to_add) - tags_to_remove
                self.db.set_card_tags(card_id, list(updated))

            # Groups
            if groups_to_add or groups_to_remove:
                current = {g['id'] for g in self.db.get_groups_for_card(card_id)}
                updated = (current | groups_to_add) - groups_to_remove
                self.db.set_card_groups(card_id, list(updated))

            # Classification + Notes
            meta_kwargs = {}
            if set_archetype is not None:
                meta_kwargs['archetype'] = set_archetype
            if set_rank is not None:
                meta_kwargs['rank'] = set_rank
            if set_suit is not None:
                meta_kwargs['suit'] = set_suit

            if set_notes is not None:
                if notes_append:
                    card = self.db.get_card_with_metadata(card_id)
                    existing = card['notes'] or '' if card else ''
                    if existing:
                        meta_kwargs['notes'] = existing + "\n" + set_notes
                    else:
                        meta_kwargs['notes'] = set_notes
                else:
                    meta_kwargs['notes'] = set_notes

            # Custom fields — merge with existing
            if custom_updates:
                card = self.db.get_card_with_metadata(card_id)
                existing_cf = {}
                if card and card['custom_fields']:
                    try:
                        existing_cf = json.loads(card['custom_fields']) if isinstance(card['custom_fields'], str) else card['custom_fields']
                    except (json.JSONDecodeError, ValueError):
                        pass
                existing_cf.update(custom_updates)
                meta_kwargs['custom_fields'] = existing_cf

            if meta_kwargs:
                self.db.update_card_metadata(card_id, **meta_kwargs)

        self.applied = True
        self.EndModal(wx.ID_OK)
