"""DEPRECATED: Legacy wxPython UI - see frontend/ for active Electron/React code.

Spreads panel mixin for MainFrame."""

import wx
import wx.lib.scrolledpanel as scrolled
import json

from ui_helpers import _cfg, get_wx_color
from rich_text_panel import RichTextPanel


class SpreadsMixin:
    # ═══════════════════════════════════════════
    # SPREADS PANEL
    # ═══════════════════════════════════════════
    def _create_spreads_panel(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))

        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)
        splitter.SetBackgroundColour(get_wx_color('bg_primary'))
        splitter.SetMinimumPaneSize(200)

        # Left: Spread list
        left = wx.Panel(splitter)
        left.SetBackgroundColour(get_wx_color('bg_primary'))
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        spreads_label = wx.StaticText(left, label="Spreads")
        spreads_label.SetForegroundColour(get_wx_color('text_primary'))
        left_sizer.Add(spreads_label, 0, wx.ALL, 5)

        self.spread_list = wx.ListCtrl(left, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER)
        self.spread_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.spread_list.SetForegroundColour(get_wx_color('text_primary'))
        self.spread_list.SetTextColour(get_wx_color('text_primary'))
        self.spread_list.InsertColumn(0, "", width=230)
        self.spread_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_spread_select)
        left_sizer.Add(self.spread_list, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        new_btn = wx.Button(left, label="+ New")
        new_btn.Bind(wx.EVT_BUTTON, self._on_new_spread)
        btn_sizer.Add(new_btn, 0, wx.RIGHT, 5)

        clone_btn = wx.Button(left, label="Clone")
        clone_btn.Bind(wx.EVT_BUTTON, self._on_clone_spread)
        btn_sizer.Add(clone_btn, 0, wx.RIGHT, 5)

        del_btn = wx.Button(left, label="Delete")
        del_btn.Bind(wx.EVT_BUTTON, self._on_delete_spread)
        btn_sizer.Add(del_btn, 0)

        left_sizer.Add(btn_sizer, 0, wx.ALL, 5)
        left.SetSizer(left_sizer)

        # Right: Designer
        right = wx.Panel(splitter)
        right.SetBackgroundColour(get_wx_color('bg_primary'))
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Name/description
        meta_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(right, label="Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        meta_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.spread_name_ctrl = wx.TextCtrl(right, size=(200, -1))
        self.spread_name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        self.spread_name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        meta_sizer.Add(self.spread_name_ctrl, 0, wx.RIGHT, 20)

        right_sizer.Add(meta_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Description with rich text editing (collapsible)
        # Note: CollapsiblePane labels don't support custom colors on macOS, so we add a separate label
        desc_label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        desc_label = wx.StaticText(right, label="Description:")
        desc_label.SetForegroundColour(get_wx_color('text_primary'))
        desc_label_sizer.Add(desc_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        desc_collapse_hint = wx.StaticText(right, label="(click to expand/collapse)")
        desc_collapse_hint.SetForegroundColour(get_wx_color('text_dim'))
        desc_label_sizer.Add(desc_collapse_hint, 0, wx.ALIGN_CENTER_VERTICAL)
        right_sizer.Add(desc_label_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        desc_box = wx.CollapsiblePane(right, label="", style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)
        desc_pane = desc_box.GetPane()
        desc_pane.SetBackgroundColour(get_wx_color('bg_primary'))
        desc_pane_sizer = wx.BoxSizer(wx.VERTICAL)
        self.spread_desc_ctrl = RichTextPanel(desc_pane, value='', min_height=100)
        desc_pane_sizer.Add(self.spread_desc_ctrl, 1, wx.EXPAND)
        desc_pane.SetSizer(desc_pane_sizer)

        def on_desc_collapse(e):
            right.Layout()
            right.GetParent().Layout()
        desc_box.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, on_desc_collapse)

        right_sizer.Add(desc_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Deck types selection
        deck_types_sizer = wx.BoxSizer(wx.HORIZONTAL)
        deck_types_label = wx.StaticText(right, label="Allowed Deck Type:")
        deck_types_label.SetForegroundColour(get_wx_color('text_primary'))
        deck_types_sizer.Add(deck_types_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # Create dropdown with "Any" as first option, then cartomancy types
        self.spread_deck_type_names = ["Any"]  # Store names for lookup
        cart_types = self.db.get_cartomancy_types()
        for ct in cart_types:
            self.spread_deck_type_names.append(ct['name'])

        self.spread_deck_type_choice = wx.Choice(right, choices=self.spread_deck_type_names)
        self.spread_deck_type_choice.SetSelection(0)  # Default to "Any"
        deck_types_sizer.Add(self.spread_deck_type_choice, 0, wx.RIGHT, 10)

        deck_type_note = wx.StaticText(right, label="(restricts which decks can be used with this spread)")
        deck_type_note.SetForegroundColour(get_wx_color('text_dim'))
        deck_types_sizer.Add(deck_type_note, 0, wx.ALIGN_CENTER_VERTICAL)

        right_sizer.Add(deck_types_sizer, 0, wx.LEFT | wx.BOTTOM, 10)

        # Default deck selection
        default_deck_sizer = wx.BoxSizer(wx.HORIZONTAL)
        default_deck_label = wx.StaticText(right, label="Default Deck:")
        default_deck_label.SetForegroundColour(get_wx_color('text_primary'))
        default_deck_sizer.Add(default_deck_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.spread_default_deck_choice = wx.Choice(right, size=(250, -1))
        self._refresh_spread_default_deck_choices()
        default_deck_sizer.Add(self.spread_default_deck_choice, 0, wx.RIGHT, 10)

        default_deck_note = wx.StaticText(right, label="(overrides global default for this spread)")
        default_deck_note.SetForegroundColour(get_wx_color('text_dim'))
        default_deck_sizer.Add(default_deck_note, 0, wx.ALIGN_CENTER_VERTICAL)

        right_sizer.Add(default_deck_sizer, 0, wx.LEFT | wx.BOTTOM, 10)

        # Instructions
        instr = wx.StaticText(right, label="Drag positions to arrange • Right-click to delete")
        instr.SetForegroundColour(get_wx_color('text_dim'))
        right_sizer.Add(instr, 0, wx.LEFT, 10)

        # Legend toggle
        toggle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.designer_legend_toggle = wx.CheckBox(right, label="")
        self.designer_legend_toggle.Bind(wx.EVT_CHECKBOX, self._on_designer_legend_toggle)
        toggle_sizer.Add(self.designer_legend_toggle, 0, wx.RIGHT, 5)

        designer_legend_label = wx.StaticText(right, label="Show Position Legend")
        designer_legend_label.SetForegroundColour(get_wx_color('text_primary'))
        toggle_sizer.Add(designer_legend_label, 0, wx.ALIGN_CENTER_VERTICAL)

        toggle_sizer.AddSpacer(20)

        # Snap to grid toggle
        self.designer_snap_toggle = wx.CheckBox(right, label="")
        self.designer_snap_toggle.SetValue(True)  # Default to enabled
        self.designer_snap_toggle.Bind(wx.EVT_CHECKBOX, lambda e: self.designer_canvas.Refresh())
        toggle_sizer.Add(self.designer_snap_toggle, 0, wx.RIGHT, 5)

        designer_snap_label = wx.StaticText(right, label="Snap to Grid")
        designer_snap_label.SetForegroundColour(get_wx_color('text_primary'))
        toggle_sizer.Add(designer_snap_label, 0, wx.ALIGN_CENTER_VERTICAL)

        right_sizer.Add(toggle_sizer, 0, wx.LEFT | wx.TOP, 10)

        # Container for canvas and legend
        canvas_legend_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Designer canvas
        self.designer_canvas = wx.Panel(right, size=(-1, 450))
        self.designer_canvas.SetBackgroundColour(get_wx_color('card_slot'))
        self.designer_canvas.Bind(wx.EVT_PAINT, self._on_designer_paint)
        self.designer_canvas.Bind(wx.EVT_LEFT_DOWN, self._on_designer_left_down)
        self.designer_canvas.Bind(wx.EVT_LEFT_UP, self._on_designer_left_up)
        self.designer_canvas.Bind(wx.EVT_MOTION, self._on_designer_motion)
        self.designer_canvas.Bind(wx.EVT_RIGHT_DOWN, self._on_designer_right_down)
        canvas_legend_sizer.Add(self.designer_canvas, 1, wx.EXPAND | wx.ALL, 10)

        # Legend panel (initially hidden)
        self.designer_legend_panel = wx.Panel(right)
        self.designer_legend_panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        designer_legend_sizer_inner = wx.BoxSizer(wx.VERTICAL)

        legend_title = wx.StaticText(self.designer_legend_panel, label="Position Legend:")
        legend_title.SetForegroundColour(get_wx_color('text_primary'))
        legend_title.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        designer_legend_sizer_inner.Add(legend_title, 0, wx.ALL, 10)

        # Create scrolled window for legend items
        self.designer_legend_scroll = scrolled.ScrolledPanel(self.designer_legend_panel, size=(200, 400))
        self.designer_legend_scroll.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.designer_legend_items_sizer = wx.BoxSizer(wx.VERTICAL)
        self.designer_legend_scroll.SetSizer(self.designer_legend_items_sizer)
        self.designer_legend_scroll.SetupScrolling()
        designer_legend_sizer_inner.Add(self.designer_legend_scroll, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.designer_legend_panel.SetSizer(designer_legend_sizer_inner)
        self.designer_legend_panel.Hide()
        canvas_legend_sizer.Add(self.designer_legend_panel, 0, wx.EXPAND | wx.ALL, 10)

        right_sizer.Add(canvas_legend_sizer, 1, wx.EXPAND)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_pos_btn = wx.Button(right, label="+ Add Position")
        add_pos_btn.Bind(wx.EVT_BUTTON, self._on_add_position)
        btn_sizer.Add(add_pos_btn, 0, wx.RIGHT, 10)

        clear_btn = wx.Button(right, label="Clear All")
        clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_positions)
        btn_sizer.Add(clear_btn, 0)

        btn_sizer.AddStretchSpacer()

        save_btn = wx.Button(right, label="Save Spread")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save_spread)
        btn_sizer.Add(save_btn, 0)

        right_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        right.SetSizer(right_sizer)

        splitter.SplitVertically(left, right, _cfg.get('panels', 'spreads_splitter', 250))

        panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel_sizer.Add(splitter, 1, wx.EXPAND)
        panel.SetSizer(panel_sizer)

        return panel

    def _refresh_spreads_list(self):
        self.spread_list.DeleteAllItems()
        spreads = self.db.get_spreads()
        for spread in spreads:
            idx = self.spread_list.InsertItem(self.spread_list.GetItemCount(), spread['name'])
            self.spread_list.SetItemData(idx, spread['id'])
        self._update_spread_choice()

    # ═══════════════════════════════════════════
    # EVENT HANDLERS - Spreads
    # ═══════════════════════════════════════════
    def _refresh_spread_default_deck_choices(self):
        """Refresh the default deck dropdown in spread editor"""
        self.spread_default_deck_choice.Clear()
        self.spread_default_deck_choice.Append("(Use global default)", None)
        decks = self.db.get_decks()
        for deck in decks:
            self.spread_default_deck_choice.Append(deck['name'], deck['id'])
        self.spread_default_deck_choice.SetSelection(0)

    def _on_spread_select(self, event):
        idx = self.spread_list.GetFirstSelected()
        if idx == -1:
            return

        spread_name = self.spread_list.GetItemText(idx)
        spreads = self.db.get_spreads()

        for spread in spreads:
            if spread['name'] == spread_name:
                self.editing_spread_id = spread['id']
                self.spread_name_ctrl.SetValue(spread['name'])
                self.spread_desc_ctrl.SetValue(spread['description'] or '')
                self.designer_positions = json.loads(spread['positions'])

                # Load allowed deck type
                self.spread_deck_type_choice.SetSelection(0)  # Default to "Any"
                allowed_types_json = spread['allowed_deck_types'] if 'allowed_deck_types' in spread.keys() else None
                if allowed_types_json:
                    allowed_types = json.loads(allowed_types_json)
                    if allowed_types and len(allowed_types) > 0:
                        # Use the first allowed type (now single-select)
                        deck_type = allowed_types[0]
                        if deck_type in self.spread_deck_type_names:
                            idx = self.spread_deck_type_names.index(deck_type)
                            self.spread_deck_type_choice.SetSelection(idx)

                # Load default deck
                self._refresh_spread_default_deck_choices()
                default_deck_id = spread['default_deck_id'] if 'default_deck_id' in spread.keys() else None
                if default_deck_id:
                    for i in range(self.spread_default_deck_choice.GetCount()):
                        if self.spread_default_deck_choice.GetClientData(i) == default_deck_id:
                            self.spread_default_deck_choice.SetSelection(i)
                            break

                self._update_designer_legend()
                self.designer_canvas.Refresh()
                break

    def _on_new_spread(self, event):
        self.editing_spread_id = None
        self.spread_name_ctrl.SetValue('')
        self.spread_desc_ctrl.SetValue('')
        self.designer_positions = []
        # Reset deck type to "Any"
        self.spread_deck_type_choice.SetSelection(0)
        # Reset default deck to global default
        self._refresh_spread_default_deck_choices()
        self._update_designer_legend()
        self.designer_canvas.Refresh()

    def _on_clone_spread(self, event):
        """Clone an existing spread to create a new one"""
        spreads = self.db.get_spreads()
        if not spreads:
            wx.MessageBox("No spreads available to clone.", "No Spreads", wx.OK | wx.ICON_INFORMATION)
            return

        # Build list of spread names
        spread_names = [s['name'] for s in spreads]

        dlg = wx.SingleChoiceDialog(self, "Select a spread to clone:", "Clone Spread", spread_names)
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        if dlg.ShowModal() == wx.ID_OK:
            selected_idx = dlg.GetSelection()
            source_spread = spreads[selected_idx]

            # Clear current editing state (new spread)
            self.editing_spread_id = None

            # Copy name with "Copy of" prefix
            self.spread_name_ctrl.SetValue(f"Copy of {source_spread['name']}")

            # Copy description
            desc = source_spread['description'] if source_spread['description'] else ''
            self.spread_desc_ctrl.SetValue(desc)

            # Copy positions (deep copy to avoid reference issues)
            import json
            positions = json.loads(source_spread['positions']) if isinstance(source_spread['positions'], str) else source_spread['positions']
            self.designer_positions = [dict(p) for p in positions]

            # Copy deck type restriction
            self.spread_deck_type_choice.SetSelection(0)  # Default to "Any"
            if 'allowed_deck_types' in source_spread.keys() and source_spread['allowed_deck_types']:
                allowed_types = json.loads(source_spread['allowed_deck_types']) if isinstance(source_spread['allowed_deck_types'], str) else source_spread['allowed_deck_types']
                if allowed_types and len(allowed_types) > 0:
                    deck_type = allowed_types[0]
                    if deck_type in self.spread_deck_type_names:
                        idx = self.spread_deck_type_names.index(deck_type)
                        self.spread_deck_type_choice.SetSelection(idx)

            # Copy default deck
            self._refresh_spread_default_deck_choices()
            default_deck_id = source_spread['default_deck_id'] if 'default_deck_id' in source_spread.keys() else None
            if default_deck_id:
                for i in range(self.spread_default_deck_choice.GetCount()):
                    if self.spread_default_deck_choice.GetClientData(i) == default_deck_id:
                        self.spread_default_deck_choice.SetSelection(i)
                        break

            self._update_designer_legend()
            self.designer_canvas.Refresh()

        dlg.Destroy()

    def _on_delete_spread(self, event):
        idx = self.spread_list.GetFirstSelected()
        if idx == -1:
            return

        spread_name = self.spread_list.GetItemText(idx)

        if wx.MessageBox(f"Delete '{spread_name}'?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            spreads = self.db.get_spreads()
            for spread in spreads:
                if spread['name'] == spread_name:
                    self.db.delete_spread(spread['id'])
                    break
            self._refresh_spreads_list()
            self._on_new_spread(None)

    def _on_save_spread(self, event):
        name = self.spread_name_ctrl.GetValue().strip()
        if not name:
            wx.MessageBox("Please enter a spread name.", "Name Required", wx.OK | wx.ICON_WARNING)
            return

        if not self.designer_positions:
            wx.MessageBox("Add at least one card position.", "No Positions", wx.OK | wx.ICON_WARNING)
            return

        desc = self.spread_desc_ctrl.GetValue().strip()

        # Get allowed deck type from dropdown
        deck_type_idx = self.spread_deck_type_choice.GetSelection()
        if deck_type_idx > 0:  # Not "Any"
            allowed_deck_types = [self.spread_deck_type_names[deck_type_idx]]
        else:
            allowed_deck_types = []  # "Any" means no restriction

        # Get default deck selection
        default_deck_sel = self.spread_default_deck_choice.GetSelection()
        default_deck_id = self.spread_default_deck_choice.GetClientData(default_deck_sel) if default_deck_sel > 0 else None

        if self.editing_spread_id:
            self.db.update_spread(self.editing_spread_id, name=name,
                                 positions=self.designer_positions, description=desc,
                                 allowed_deck_types=allowed_deck_types if allowed_deck_types else None,
                                 default_deck_id=default_deck_id,
                                 clear_default_deck=(default_deck_sel == 0))
        else:
            self.editing_spread_id = self.db.add_spread(name, self.designer_positions, desc,
                                                        allowed_deck_types=allowed_deck_types if allowed_deck_types else None,
                                                        default_deck_id=default_deck_id)

        self._refresh_spreads_list()
        wx.MessageBox("Spread saved!", "Success", wx.OK | wx.ICON_INFORMATION)

    def _on_add_position(self, event):
        dlg = wx.TextEntryDialog(self, "Label for this position:", "Add Position")
        if dlg.ShowModal() == wx.ID_OK:
            label = dlg.GetValue().strip()
            if label:
                # Snap to grid if enabled
                grid_size = 20
                snap_enabled = self.designer_snap_toggle.GetValue()
                def snap(val):
                    if snap_enabled:
                        return round(val / grid_size) * grid_size
                    return val

                offset = len(self.designer_positions) * 20
                self.designer_positions.append({
                    'x': snap(60 + (offset % 400)),
                    'y': snap(60 + (offset // 400) * 140),
                    'width': snap(80),
                    'height': snap(120),
                    'label': label
                })
                self._update_designer_legend()
                self.designer_canvas.Refresh()
        dlg.Destroy()

    def _on_clear_positions(self, event):
        self.designer_positions = []
        self._update_designer_legend()
        self.designer_canvas.Refresh()

    def _on_designer_legend_toggle(self, event):
        """Toggle legend visibility in spread designer"""
        show = self.designer_legend_toggle.GetValue()
        self.designer_legend_panel.Show(show)
        if show:
            self._update_designer_legend()
        self.designer_canvas.GetParent().Layout()
        self.designer_canvas.Refresh()

    def _update_designer_legend(self):
        """Update the legend panel with current positions"""
        # Clear existing legend items
        self.designer_legend_items_sizer.Clear(True)

        # Add legend items for each position
        for i, pos in enumerate(self.designer_positions):
            label = pos.get('label', f'Position {i+1}')
            key = pos.get('key', str(i + 1))
            legend_item = wx.StaticText(self.designer_legend_scroll, label=f"{key}. {label}")
            legend_item.SetForegroundColour(get_wx_color('text_primary'))
            legend_item.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            self.designer_legend_items_sizer.Add(legend_item, 0, wx.ALL, 5)

        self.designer_legend_scroll.SetupScrolling()
        self.designer_legend_panel.Layout()

    def _on_designer_paint(self, event):
        dc = wx.PaintDC(self.designer_canvas)
        dc.SetBackground(wx.Brush(get_wx_color('card_slot')))
        dc.Clear()

        # Draw grid if snap is enabled
        grid_size = 20
        if self.designer_snap_toggle.GetValue():
            canvas_w, canvas_h = self.designer_canvas.GetSize()
            dc.SetPen(wx.Pen(get_wx_color('bg_tertiary'), 1))
            # Draw vertical lines
            for x in range(0, canvas_w, grid_size):
                dc.DrawLine(x, 0, x, canvas_h)
            # Draw horizontal lines
            for y in range(0, canvas_h, grid_size):
                dc.DrawLine(0, y, canvas_w, y)

        for i, pos in enumerate(self.designer_positions):
            x, y = pos['x'], pos['y']
            w, h = pos.get('width', 80), pos.get('height', 120)
            label = pos.get('label', f'Position {i+1}')
            is_rotated = pos.get('rotated', False)

            # Draw rectangle with different color if rotated
            if is_rotated:
                dc.SetBrush(wx.Brush(get_wx_color('accent_dim')))
                dc.SetPen(wx.Pen(get_wx_color('accent'), 3))
            else:
                dc.SetBrush(wx.Brush(get_wx_color('bg_tertiary')))
                dc.SetPen(wx.Pen(get_wx_color('accent'), 2))

            dc.DrawRectangle(int(x), int(y), int(w), int(h))

            # Get legend key (custom or default to position number)
            legend_key = pos.get('key', str(i + 1))

            # Show position number and label based on legend toggle
            show_legend = self.designer_legend_toggle.GetValue()

            if show_legend:
                # Show only legend key when legend is visible
                dc.SetTextForeground(get_wx_color('text_secondary'))
                dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                dc.DrawText(legend_key, int(x - 12), int(y - 12))
            else:
                # Show label inside card when legend is hidden
                dc.SetTextForeground(get_wx_color('text_primary'))
                dc.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                dc.DrawText(label, int(x + 5), int(y + h//2 - 8))

                dc.SetTextForeground(get_wx_color('text_dim'))
                dc.DrawText(legend_key, int(x + 5), int(y + 5))

            # Show rotation indicator
            if is_rotated:
                dc.SetTextForeground(get_wx_color('accent'))
                dc.DrawText("↻", int(x + w - 20), int(y + 5))

            # Draw resize handles (small squares at corners)
            handle_size = 8
            dc.SetBrush(wx.Brush(get_wx_color('accent')))
            dc.SetPen(wx.Pen(get_wx_color('bg_primary'), 1))
            # Bottom-right corner (main resize handle)
            dc.DrawRectangle(int(x + w - handle_size), int(y + h - handle_size), handle_size, handle_size)

    def _on_designer_left_down(self, event):
        x, y = event.GetX(), event.GetY()
        handle_size = 8

        for i, pos in enumerate(self.designer_positions):
            px, py = pos['x'], pos['y']
            pw, ph = pos.get('width', 80), pos.get('height', 120)

            # Check if clicking on resize handle (bottom-right corner)
            if (px + pw - handle_size <= x <= px + pw and
                py + ph - handle_size <= y <= py + ph):
                self.drag_data['idx'] = i
                self.drag_data['resize'] = 'se'
                self.drag_data['start_w'] = pw
                self.drag_data['start_h'] = ph
                self.drag_data['start_x'] = x
                self.drag_data['start_y'] = y
                self.designer_canvas.CaptureMouse()
                return

            # Check if clicking inside the card (for dragging)
            if px <= x <= px + pw and py <= y <= py + ph:
                self.drag_data['idx'] = i
                self.drag_data['resize'] = None
                self.drag_data['offset_x'] = x - px
                self.drag_data['offset_y'] = y - py
                self.designer_canvas.CaptureMouse()
                break

    def _on_designer_left_up(self, event):
        if self.designer_canvas.HasCapture():
            self.designer_canvas.ReleaseMouse()
        self.drag_data['idx'] = None
        self.drag_data['resize'] = None

    def _on_designer_motion(self, event):
        x, y = event.GetX(), event.GetY()
        handle_size = 8

        # Update cursor based on position over resize handles
        if not event.Dragging():
            cursor = wx.CURSOR_ARROW
            for pos in self.designer_positions:
                px, py = pos['x'], pos['y']
                pw, ph = pos.get('width', 80), pos.get('height', 120)
                # Check if over bottom-right resize handle
                if (px + pw - handle_size <= x <= px + pw and
                    py + ph - handle_size <= y <= py + ph):
                    cursor = wx.CURSOR_SIZENWSE
                    break
            self.designer_canvas.SetCursor(wx.Cursor(cursor))

        if self.drag_data['idx'] is not None and event.Dragging():
            idx = self.drag_data['idx']

            # Grid snapping helper
            grid_size = 20
            snap_enabled = self.designer_snap_toggle.GetValue()
            def snap(val):
                if snap_enabled:
                    return round(val / grid_size) * grid_size
                return val

            # Handle resizing
            if self.drag_data.get('resize') == 'se':
                # Calculate new size based on mouse delta
                delta_x = x - self.drag_data['start_x']
                delta_y = y - self.drag_data['start_y']
                new_w = max(40, self.drag_data['start_w'] + delta_x)  # Min width 40
                new_h = max(60, self.drag_data['start_h'] + delta_y)  # Min height 60

                self.designer_positions[idx]['width'] = int(snap(new_w))
                self.designer_positions[idx]['height'] = int(snap(new_h))
                self.designer_canvas.Refresh()
                return

            # Handle dragging (moving)
            mx = x - self.drag_data['offset_x']
            my = y - self.drag_data['offset_y']

            # Snap to grid
            mx = snap(mx)
            my = snap(my)

            # Bounds
            canvas_w, canvas_h = self.designer_canvas.GetSize()
            pw = self.designer_positions[idx].get('width', 80)
            ph = self.designer_positions[idx].get('height', 120)
            mx = max(0, min(mx, canvas_w - pw))
            my = max(0, min(my, canvas_h - ph))

            self.designer_positions[idx]['x'] = mx
            self.designer_positions[idx]['y'] = my
            self.designer_canvas.Refresh()

    def _on_designer_right_down(self, event):
        x, y = event.GetX(), event.GetY()

        for i, pos in enumerate(self.designer_positions):
            px, py = pos['x'], pos['y']
            pw, ph = pos.get('width', 80), pos.get('height', 120)

            if px <= x <= px + pw and py <= y <= py + ph:
                menu = wx.Menu()

                # Edit option
                edit_item = menu.Append(wx.ID_ANY, "Edit Position...")
                menu.Bind(wx.EVT_MENU, lambda e, idx=i: self._edit_position(idx), edit_item)

                menu.AppendSeparator()

                # Rotate option
                is_rotated = pos.get('rotated', False)
                rotate_item = menu.Append(wx.ID_ANY, "Unrotate Card" if is_rotated else "Rotate Card 90°")
                menu.Bind(wx.EVT_MENU, lambda e, idx=i: self._toggle_position_rotation(idx), rotate_item)

                menu.AppendSeparator()

                # Delete option
                delete_item = menu.Append(wx.ID_ANY, f"Delete '{pos['label']}'")
                menu.Bind(wx.EVT_MENU, lambda e, idx=i: self._delete_position(idx), delete_item)

                self.designer_canvas.PopupMenu(menu)
                menu.Destroy()
                break

    def _toggle_position_rotation(self, idx):
        """Toggle the rotation of a position"""
        current = self.designer_positions[idx].get('rotated', False)
        self.designer_positions[idx]['rotated'] = not current

        # Swap width and height when rotating
        w = self.designer_positions[idx].get('width', 80)
        h = self.designer_positions[idx].get('height', 120)
        self.designer_positions[idx]['width'] = h
        self.designer_positions[idx]['height'] = w

        self._update_designer_legend()
        self.designer_canvas.Refresh()

    def _delete_position(self, idx):
        """Delete a position from the spread"""
        pos = self.designer_positions[idx]
        if wx.MessageBox(f"Delete '{pos['label']}'?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.designer_positions.pop(idx)
            self._update_designer_legend()
            self.designer_canvas.Refresh()

    def _edit_position(self, idx):
        """Edit a position's label and legend key"""
        pos = self.designer_positions[idx]
        current_label = pos.get('label', f'Position {idx + 1}')
        current_key = pos.get('key', str(idx + 1))

        dlg = wx.Dialog(self, title="Edit Position", size=(350, 180))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Label field
        label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label_label = wx.StaticText(dlg, label="Label:")
        label_label.SetForegroundColour(get_wx_color('text_primary'))
        label_sizer.Add(label_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        label_ctrl = wx.TextCtrl(dlg, value=current_label, size=(200, -1))
        label_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        label_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        label_sizer.Add(label_ctrl, 1)
        sizer.Add(label_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Legend key field
        key_sizer = wx.BoxSizer(wx.HORIZONTAL)
        key_label = wx.StaticText(dlg, label="Legend Key:")
        key_label.SetForegroundColour(get_wx_color('text_primary'))
        key_sizer.Add(key_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        key_ctrl = wx.TextCtrl(dlg, value=current_key, size=(60, -1))
        key_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        key_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        key_sizer.Add(key_ctrl, 0)
        key_hint = wx.StaticText(dlg, label="(number or letter shown on card)")
        key_hint.SetForegroundColour(get_wx_color('text_dim'))
        key_sizer.Add(key_hint, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        sizer.Add(key_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        ok_btn = wx.Button(dlg, wx.ID_OK, "OK")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(ok_btn, 0)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            new_label = label_ctrl.GetValue().strip()
            new_key = key_ctrl.GetValue().strip()
            if new_label:
                self.designer_positions[idx]['label'] = new_label
            if new_key:
                self.designer_positions[idx]['key'] = new_key
            self._update_designer_legend()
            self.designer_canvas.Refresh()

        dlg.Destroy()
