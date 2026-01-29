"""DEPRECATED: Legacy wxPython UI - see frontend/ for active Electron/React code.

Settings panel mixin for MainFrame."""

import wx
import wx.adv
import wx.lib.scrolledpanel as scrolled
import wx.lib.agw.flatnotebook as fnb
from datetime import datetime
from pathlib import Path

from ui_helpers import (
    logger, _cfg, VERSION, _theme, COLORS, _fonts_config,
    get_wx_color, refresh_colors,
)
from theme_config import get_theme, PRESET_THEMES
from import_presets import get_presets, BUILTIN_PRESETS, COURT_PRESETS, ARCHETYPE_MAPPING_OPTIONS, DEFAULT_CARD_BACK_PATTERNS


class SettingsMixin:

    # ═══════════════════════════════════════════
    # SETTINGS PANEL
    # ═══════════════════════════════════════════
    def _create_settings_panel(self):
        panel = scrolled.ScrolledPanel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))
        panel.SetupScrolling()

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Theme section
        theme_box = wx.StaticBox(panel, label="Appearance")
        theme_box.SetForegroundColour(get_wx_color('accent'))
        theme_sizer = wx.StaticBoxSizer(theme_box, wx.VERTICAL)

        preset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        theme_preset_label = wx.StaticText(panel, label="Theme Preset:")
        theme_preset_label.SetForegroundColour(get_wx_color('text_primary'))
        preset_sizer.Add(theme_preset_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.theme_choice = wx.Choice(panel, choices=list(PRESET_THEMES.keys()))
        self.theme_choice.SetSelection(0)
        preset_sizer.Add(self.theme_choice, 0, wx.RIGHT, 10)

        apply_theme_btn = wx.Button(panel, label="Apply Preset")
        apply_theme_btn.Bind(wx.EVT_BUTTON, self._on_apply_theme)
        preset_sizer.Add(apply_theme_btn, 0, wx.RIGHT, 10)

        customize_btn = wx.Button(panel, label="Customize...")
        customize_btn.Bind(wx.EVT_BUTTON, self._on_customize_theme)
        preset_sizer.Add(customize_btn, 0)

        theme_sizer.Add(preset_sizer, 0, wx.ALL, 10)

        sizer.Add(theme_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Import presets section
        presets_box = wx.StaticBox(panel, label="Import Presets")
        presets_box.SetForegroundColour(get_wx_color('accent'))
        presets_sizer = wx.StaticBoxSizer(presets_box, wx.VERTICAL)

        presets_desc = wx.StaticText(panel, label="Configure filename mappings for deck imports.")
        presets_desc.SetForegroundColour(get_wx_color('text_primary'))
        presets_sizer.Add(presets_desc, 0, wx.ALL, 10)

        presets_inner = wx.BoxSizer(wx.HORIZONTAL)

        # Preset list
        self.presets_list = wx.ListCtrl(panel, size=(250, 150), style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER)
        self.presets_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.presets_list.SetForegroundColour(get_wx_color('text_primary'))
        self.presets_list.SetTextColour(get_wx_color('text_primary'))
        self.presets_list.InsertColumn(0, "", width=230)
        self.presets_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_preset_select)
        self.presets_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit_preset)
        presets_inner.Add(self.presets_list, 0, wx.RIGHT, 10)

        # Preset details
        self.preset_details = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(300, 150))
        self.preset_details.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.preset_details.SetForegroundColour(get_wx_color('text_primary'))
        presets_inner.Add(self.preset_details, 1, wx.EXPAND)

        presets_sizer.Add(presets_inner, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        preset_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        new_preset_btn = wx.Button(panel, label="+ New Preset")
        new_preset_btn.Bind(wx.EVT_BUTTON, self._on_new_preset)
        preset_btn_sizer.Add(new_preset_btn, 0, wx.RIGHT, 5)

        edit_preset_btn = wx.Button(panel, label="Edit")
        edit_preset_btn.Bind(wx.EVT_BUTTON, self._on_edit_preset)
        preset_btn_sizer.Add(edit_preset_btn, 0, wx.RIGHT, 5)

        del_preset_btn = wx.Button(panel, label="Delete")
        del_preset_btn.Bind(wx.EVT_BUTTON, self._on_delete_preset)
        preset_btn_sizer.Add(del_preset_btn, 0)

        presets_sizer.Add(preset_btn_sizer, 0, wx.ALL, 10)

        sizer.Add(presets_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Default Decks section
        defaults_box = wx.StaticBox(panel, label="Default Decks")
        defaults_box.SetForegroundColour(get_wx_color('accent'))
        defaults_sizer = wx.StaticBoxSizer(defaults_box, wx.VERTICAL)

        defaults_desc = wx.StaticText(panel, label="Select default decks to use automatically for each type.")
        defaults_desc.SetForegroundColour(get_wx_color('text_primary'))
        defaults_sizer.Add(defaults_desc, 0, wx.ALL, 10)

        # Store default deck choices
        self.default_deck_choices = {}

        # Create dropdown for each cartomancy type
        for cart_type in self.db.get_cartomancy_types():
            type_name = cart_type['name']
            type_sizer = wx.BoxSizer(wx.HORIZONTAL)

            label = wx.StaticText(panel, label=f"{type_name}:")
            label.SetForegroundColour(get_wx_color('text_primary'))
            label.SetMinSize((120, -1))
            type_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

            # Get decks for this type
            decks = self.db.get_decks(cart_type['id'])
            deck_names = ["(None)"] + [f"{d['name']} ({d['id']})" for d in decks]

            choice = wx.Choice(panel, choices=deck_names)
            choice.SetSelection(0)

            # Load saved default
            default_deck_id = self.db.get_default_deck(type_name)
            if default_deck_id:
                for i, deck in enumerate(decks):
                    if deck['id'] == default_deck_id:
                        choice.SetSelection(i + 1)  # +1 because of "(None)" option
                        break

            # Save on change
            def make_handler(cart_type_name):
                def on_change(event):
                    sel = event.GetEventObject().GetSelection()
                    if sel == 0:  # "(None)" selected
                        self.db.set_setting(f'default_deck_{cart_type_name.lower()}', '')
                    else:
                        # Extract deck ID from "Name (ID)" format
                        choice_text = event.GetEventObject().GetStringSelection()
                        deck_id = choice_text.split('(')[-1].rstrip(')')
                        self.db.set_default_deck(cart_type_name, int(deck_id))
                    wx.MessageBox(f"Default {cart_type_name} deck updated!", "Success", wx.OK | wx.ICON_INFORMATION)
                return on_change

            choice.Bind(wx.EVT_CHOICE, make_handler(type_name))
            self.default_deck_choices[type_name] = choice

            type_sizer.Add(choice, 1, wx.EXPAND | wx.RIGHT, 10)
            defaults_sizer.Add(type_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        sizer.Add(defaults_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Default Reader/Querent section
        people_defaults_box = wx.StaticBox(panel, label="Default Reader & Querent")
        people_defaults_box.SetForegroundColour(get_wx_color('accent'))
        people_defaults_sizer = wx.StaticBoxSizer(people_defaults_box, wx.VERTICAL)

        people_defaults_desc = wx.StaticText(panel, label="Set default reader and querent for new journal entries.")
        people_defaults_desc.SetForegroundColour(get_wx_color('text_primary'))
        people_defaults_sizer.Add(people_defaults_desc, 0, wx.ALL, 10)

        # Get profiles for dropdowns
        profiles = self.db.get_profiles()
        profile_names = ["(None)"] + [p['name'] for p in profiles]
        profile_ids = [None] + [p['id'] for p in profiles]

        # Querent row
        querent_sizer = wx.BoxSizer(wx.HORIZONTAL)
        querent_label = wx.StaticText(panel, label="Default Querent:")
        querent_label.SetForegroundColour(get_wx_color('text_primary'))
        querent_label.SetMinSize((120, -1))
        querent_sizer.Add(querent_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.default_querent_choice = wx.Choice(panel, choices=profile_names)
        self.default_querent_choice.SetSelection(0)

        # Load saved default querent
        default_querent_id = self.db.get_default_querent()
        if default_querent_id:
            for i, pid in enumerate(profile_ids):
                if pid == default_querent_id:
                    self.default_querent_choice.SetSelection(i)
                    break

        def on_querent_change(event):
            sel = self.default_querent_choice.GetSelection()
            profile_id = profile_ids[sel] if sel > 0 else None
            self.db.set_default_querent(profile_id)
            # If "same as querent" is checked, also update reader
            if self.default_reader_same_cb.GetValue():
                self.default_reader_choice.SetSelection(sel)
                self.db.set_default_reader(profile_id)

        self.default_querent_choice.Bind(wx.EVT_CHOICE, on_querent_change)
        querent_sizer.Add(self.default_querent_choice, 1, wx.EXPAND | wx.RIGHT, 10)
        people_defaults_sizer.Add(querent_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Reader row
        reader_sizer = wx.BoxSizer(wx.HORIZONTAL)
        reader_label = wx.StaticText(panel, label="Default Reader:")
        reader_label.SetForegroundColour(get_wx_color('text_primary'))
        reader_label.SetMinSize((120, -1))
        reader_sizer.Add(reader_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.default_reader_choice = wx.Choice(panel, choices=profile_names)
        self.default_reader_choice.SetSelection(0)

        # Load saved default reader
        default_reader_id = self.db.get_default_reader()
        if default_reader_id:
            for i, pid in enumerate(profile_ids):
                if pid == default_reader_id:
                    self.default_reader_choice.SetSelection(i)
                    break

        def on_reader_change(event):
            sel = self.default_reader_choice.GetSelection()
            profile_id = profile_ids[sel] if sel > 0 else None
            self.db.set_default_reader(profile_id)

        self.default_reader_choice.Bind(wx.EVT_CHOICE, on_reader_change)
        reader_sizer.Add(self.default_reader_choice, 1, wx.EXPAND | wx.RIGHT, 10)
        people_defaults_sizer.Add(reader_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # "Reader same as Querent" checkbox
        same_sizer = wx.BoxSizer(wx.HORIZONTAL)
        same_spacer = wx.StaticText(panel, label="")
        same_spacer.SetMinSize((120, -1))
        same_sizer.Add(same_spacer, 0, wx.RIGHT, 10)

        self.default_reader_same_cb = wx.CheckBox(panel, label="")
        same_sizer.Add(self.default_reader_same_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        same_label = wx.StaticText(panel, label="Reader same as Querent")
        same_label.SetForegroundColour(get_wx_color('text_primary'))
        same_sizer.Add(same_label, 0, wx.ALIGN_CENTER_VERTICAL)

        # Load saved "same as querent" setting
        if self.db.get_default_reader_same_as_querent():
            self.default_reader_same_cb.SetValue(True)
            self.default_reader_choice.Enable(False)

        def on_same_change(event):
            same = self.default_reader_same_cb.GetValue()
            self.db.set_default_reader_same_as_querent(same)
            if same:
                sel = self.default_querent_choice.GetSelection()
                self.default_reader_choice.SetSelection(sel)
                self.default_reader_choice.Enable(False)
                profile_id = profile_ids[sel] if sel > 0 else None
                self.db.set_default_reader(profile_id)
            else:
                self.default_reader_choice.Enable(True)

        self.default_reader_same_cb.Bind(wx.EVT_CHECKBOX, on_same_change)
        people_defaults_sizer.Add(same_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        sizer.Add(people_defaults_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Cache section
        cache_box = wx.StaticBox(panel, label="Thumbnail Cache")
        cache_box.SetForegroundColour(get_wx_color('accent'))
        cache_sizer = wx.StaticBoxSizer(cache_box, wx.HORIZONTAL)

        self.cache_label = wx.StaticText(panel, label="")
        self.cache_label.SetForegroundColour(get_wx_color('text_primary'))
        cache_sizer.Add(self.cache_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)

        refresh_btn = wx.Button(panel, label="Refresh")
        refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self._update_cache_info())
        cache_sizer.Add(refresh_btn, 0, wx.ALL, 10)

        clear_btn = wx.Button(panel, label="Clear Cache")
        clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_cache)
        cache_sizer.Add(clear_btn, 0, wx.ALL, 10)

        sizer.Add(cache_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Backup & Restore section
        backup_box = wx.StaticBox(panel, label="Backup & Restore")
        backup_box.SetForegroundColour(get_wx_color('accent'))
        backup_sizer = wx.StaticBoxSizer(backup_box, wx.VERTICAL)

        backup_desc = wx.StaticText(panel, label="Create and restore full backups of your tarot journal.")
        backup_desc.SetForegroundColour(get_wx_color('text_primary'))
        backup_sizer.Add(backup_desc, 0, wx.ALL, 10)

        # Include images checkbox (using empty label + StaticText per CLAUDE.md)
        images_cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.backup_include_images_cb = wx.CheckBox(panel, label="")
        images_cb_sizer.Add(self.backup_include_images_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        images_cb_label = wx.StaticText(panel, label="Include card images (larger backup size)")
        images_cb_label.SetForegroundColour(get_wx_color('text_primary'))
        images_cb_sizer.Add(images_cb_label, 0, wx.ALIGN_CENTER_VERTICAL)
        backup_sizer.Add(images_cb_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Buttons row
        backup_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        create_backup_btn = wx.Button(panel, label="Create Backup")
        create_backup_btn.Bind(wx.EVT_BUTTON, self._on_create_backup)
        backup_btn_sizer.Add(create_backup_btn, 0, wx.RIGHT, 10)

        restore_backup_btn = wx.Button(panel, label="Restore from Backup")
        restore_backup_btn.Bind(wx.EVT_BUTTON, self._on_restore_backup)
        backup_btn_sizer.Add(restore_backup_btn, 0)
        backup_sizer.Add(backup_btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Last backup time label
        last_backup_time = self.db.get_setting("last_backup_time")
        if last_backup_time:
            try:
                dt = datetime.fromisoformat(last_backup_time)
                last_backup_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError) as e:
                logger.debug("Could not parse backup time: %s", e)
                last_backup_str = "Unknown"
        else:
            last_backup_str = "Never"
        self.last_backup_label = wx.StaticText(panel, label=f"Last backup: {last_backup_str}")
        self.last_backup_label.SetForegroundColour(get_wx_color('text_dim'))
        backup_sizer.Add(self.last_backup_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        sizer.Add(backup_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # About section
        about_box = wx.StaticBox(panel, label="About")
        about_box.SetForegroundColour(get_wx_color('accent'))
        about_sizer = wx.StaticBoxSizer(about_box, wx.VERTICAL)

        about_text = wx.StaticText(panel, label=f"Tarot Journal v{VERSION}\nA journaling app for tarot, lenormand, and oracle readings.")
        about_text.SetForegroundColour(get_wx_color('text_secondary'))
        about_sizer.Add(about_text, 0, wx.ALL, 10)

        sizer.Add(about_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(sizer)

        # Initialize
        self._refresh_presets_list()
        self._update_cache_info()

        return panel

    def _refresh_presets_list(self, preserve_scroll=True):
        # Save scroll position of settings panel (if it exists)
        scroll_pos = None
        if preserve_scroll and hasattr(self, 'settings_panel') and self.settings_panel:
            scroll_pos = self.settings_panel.GetViewStart()

        self.presets_list.DeleteAllItems()
        for name in self.presets.get_preset_names():
            self.presets_list.InsertItem(self.presets_list.GetItemCount(), name)

        # Restore scroll position
        if scroll_pos is not None:
            wx.CallAfter(self.settings_panel.Scroll, scroll_pos[0], scroll_pos[1])

    def _update_cache_info(self):
        count = self.thumb_cache.get_cache_count()
        size_mb = self.thumb_cache.get_cache_size() / (1024 * 1024)
        self.cache_label.SetLabel(f"{count} thumbnails cached ({size_mb:.1f} MB)")

    # ═══════════════════════════════════════════
    # EVENT HANDLERS - Settings
    # ═══════════════════════════════════════════
    def _on_apply_theme(self, event):
        preset_name = self.theme_choice.GetStringSelection()
        _theme.apply_preset(preset_name)
        _theme.save_theme()
        self._apply_theme_live()
        wx.MessageBox(f"'{preset_name}' theme applied!", "Theme Applied", wx.OK | wx.ICON_INFORMATION)

    def _apply_theme_live(self):
        """Apply theme changes without restarting"""
        refresh_colors()
        self._update_widget_colors(self)
        self.Refresh()
        self.Update()

    def _update_widget_colors(self, widget):
        """Recursively update colors on all widgets"""
        try:
            # Determine appropriate colors based on widget type
            if isinstance(widget, wx.Frame):
                widget.SetBackgroundColour(get_wx_color('bg_primary'))
            elif isinstance(widget, fnb.FlatNotebook):
                widget.SetBackgroundColour(get_wx_color('bg_primary'))
                widget.SetTabAreaColour(get_wx_color('bg_primary'))
                widget.SetActiveTabColour(get_wx_color('bg_tertiary'))
                widget.SetNonActiveTabTextColour(get_wx_color('text_primary'))
                widget.SetActiveTabTextColour(get_wx_color('text_primary'))
                widget.SetGradientColourTo(get_wx_color('bg_tertiary'))
                widget.SetGradientColourFrom(get_wx_color('bg_primary'))
            elif isinstance(widget, wx.Notebook):
                widget.SetBackgroundColour(get_wx_color('bg_secondary'))
                widget.SetForegroundColour(get_wx_color('text_primary'))
            elif isinstance(widget, wx.ListCtrl):
                widget.SetBackgroundColour(get_wx_color('bg_secondary'))
                widget.SetForegroundColour(get_wx_color('text_primary'))
                widget.SetTextColour(get_wx_color('text_primary'))
            elif isinstance(widget, wx.ListBox):
                widget.SetBackgroundColour(get_wx_color('bg_secondary'))
                widget.SetForegroundColour(get_wx_color('text_primary'))
            elif isinstance(widget, wx.TextCtrl):
                widget.SetBackgroundColour(get_wx_color('bg_input'))
                widget.SetForegroundColour(get_wx_color('text_primary'))
            elif isinstance(widget, wx.StaticBox):
                widget.SetForegroundColour(get_wx_color('accent'))
            elif isinstance(widget, wx.StaticText):
                # Check parent background to determine text color
                widget.SetForegroundColour(get_wx_color('text_primary'))
            elif isinstance(widget, wx.Button):
                pass  # Let system handle button colors
            elif isinstance(widget, wx.Choice):
                pass  # Let system handle choice colors
            elif isinstance(widget, wx.SearchCtrl):
                pass  # Let system handle search colors
            elif isinstance(widget, scrolled.ScrolledPanel):
                widget.SetBackgroundColour(get_wx_color('bg_primary'))
            elif isinstance(widget, wx.Panel):
                # Check if it has a special role
                if hasattr(widget, 'card_id'):
                    widget.SetBackgroundColour(get_wx_color('bg_tertiary'))
                else:
                    widget.SetBackgroundColour(get_wx_color('bg_primary'))
            elif isinstance(widget, wx.SplitterWindow):
                widget.SetBackgroundColour(get_wx_color('bg_primary'))

            widget.Refresh()
        except Exception as e:
            # Some widgets may fail to update colors; log and continue
            logger.debug(f"Failed to update colors for widget {type(widget).__name__}: {e}")

        # Recurse into children
        if hasattr(widget, 'GetChildren'):
            for child in widget.GetChildren():
                self._update_widget_colors(child)

    def _on_customize_theme(self, event):
        """Open theme customization dialog with live preview"""
        dlg = wx.Dialog(self, title="Customize Theme", size=(650, 550))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(dlg, label="Customize Theme Colors")
        title.SetForegroundColour(get_wx_color('text_primary'))
        title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL, 15)

        note = wx.StaticText(dlg, label="Edit colors using hex values (e.g., #1e2024). Changes apply immediately.")
        note.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(note, 0, wx.LEFT | wx.BOTTOM, 15)

        # Scrolled panel for colors
        scroll = scrolled.ScrolledPanel(dlg)
        scroll.SetBackgroundColour(get_wx_color('bg_primary'))
        scroll.SetupScrolling()
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        color_labels = {
            'bg_primary': 'Main Background',
            'bg_secondary': 'Panel Background',
            'bg_tertiary': 'Hover / Border Background',
            'bg_input': 'Input Field Background',
            'accent': 'Accent Color (buttons, links)',
            'accent_hover': 'Accent Hover',
            'accent_dim': 'Accent Muted (selections)',
            'text_primary': 'Primary Text',
            'text_secondary': 'Secondary Text',
            'text_dim': 'Muted Text',
            'border': 'Border Color',
            'card_slot': 'Card Slot Background',
        }

        color_ctrls = {}
        swatches = {}

        for key, label in color_labels.items():
            row = wx.BoxSizer(wx.HORIZONTAL)

            lbl = wx.StaticText(scroll, label=label + ":", size=(180, -1), style=wx.ALIGN_RIGHT)
            lbl.SetForegroundColour(get_wx_color('text_secondary'))
            row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

            ctrl = wx.TextCtrl(scroll, value=COLORS.get(key, '#000000'), size=(100, -1))
            ctrl.SetBackgroundColour(get_wx_color('bg_input'))
            ctrl.SetForegroundColour(get_wx_color('text_primary'))
            color_ctrls[key] = ctrl
            row.Add(ctrl, 0, wx.RIGHT, 10)

            swatch = wx.Panel(scroll, size=(30, 25))
            swatch.SetBackgroundColour(get_wx_color(key))
            swatches[key] = swatch
            row.Add(swatch, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

            def make_picker(k=key, c=ctrl, s=swatch):
                def pick(e):
                    current = c.GetValue()
                    try:
                        data = wx.ColourData()
                        data.SetColour(wx.Colour(current))
                        picker = wx.ColourDialog(dlg, data)
                        if picker.ShowModal() == wx.ID_OK:
                            color = picker.GetColourData().GetColour()
                            hex_color = "#{:02x}{:02x}{:02x}".format(color.Red(), color.Green(), color.Blue())
                            c.SetValue(hex_color)
                            s.SetBackgroundColour(color)
                            s.Refresh()
                        picker.Destroy()
                    except Exception as exc:
                        logger.debug("Color picker error: %s", exc)
                return pick

            pick_btn = wx.Button(scroll, label="Pick", size=(50, -1))
            pick_btn.Bind(wx.EVT_BUTTON, make_picker())
            row.Add(pick_btn, 0)

            scroll_sizer.Add(row, 0, wx.EXPAND | wx.ALL, 5)

            # Update swatch on text change
            def make_updater(k=key, c=ctrl, s=swatch):
                def update(e):
                    val = c.GetValue()
                    if val.startswith('#') and len(val) == 7:
                        try:
                            s.SetBackgroundColour(wx.Colour(val))
                            s.Refresh()
                        except Exception as exc:
                            logger.debug("Could not update color swatch: %s", exc)
                    e.Skip()
                return update

            ctrl.Bind(wx.EVT_TEXT, make_updater())

        scroll.SetSizer(scroll_sizer)
        sizer.Add(scroll, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        def apply_changes(e=None):
            for key, ctrl in color_ctrls.items():
                val = ctrl.GetValue().strip()
                if val.startswith('#') and len(val) == 7:
                    _theme.set_color(key, val)
            _theme.save_theme()
            self._apply_theme_live()

        apply_btn = wx.Button(dlg, label="Apply")
        apply_btn.Bind(wx.EVT_BUTTON, apply_changes)
        btn_sizer.Add(apply_btn, 0, wx.RIGHT, 10)

        close_btn = wx.Button(dlg, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CLOSE))
        btn_sizer.Add(close_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        dlg.SetSizer(sizer)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_preset_select(self, event):
        idx = self.presets_list.GetFirstSelected()
        if idx == -1:
            return

        preset_name = self.presets_list.GetItemText(idx)
        preset = self.presets.get_preset(preset_name)

        if preset:
            details = f"Type: {preset.get('type', 'Unknown')}\n"
            details += f"Description: {preset.get('description', 'No description')}\n\n"
            details += f"Mappings: {len(preset.get('mappings', {}))} entries\n\n"

            mappings = preset.get('mappings', {})
            sample = list(mappings.items())[:10]
            if sample:
                details += "Sample mappings:\n"
                for key, value in sample:
                    details += f"  {key} → {value}\n"
                if len(mappings) > 10:
                    details += f"  ... and {len(mappings) - 10} more"

            # Show customization status
            if self.presets.is_builtin_preset(preset_name):
                if self.presets.is_preset_customized(preset_name):
                    details += "\n\n(Customized - click 'Delete' to revert to defaults)"
                else:
                    details += "\n\n(Built-in preset - click 'Edit' to customize)"
            else:
                details += "\n\n(Custom preset)"

            self.preset_details.SetValue(details)

    def _find_listctrl_item(self, listctrl, text):
        """Find item index by text in ListCtrl, returns -1 if not found"""
        for i in range(listctrl.GetItemCount()):
            if listctrl.GetItemText(i) == text:
                return i
        return -1

    def _on_new_preset(self, event):
        """Create a new preset with option to clone from existing"""
        dlg = wx.Dialog(self, title="New Preset", size=(400, 180))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Name field
        name_row = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(dlg, label="Preset name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_row.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        name_ctrl = wx.TextCtrl(dlg, size=(250, -1))
        name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        name_row.Add(name_ctrl, 1)
        sizer.Add(name_row, 0, wx.EXPAND | wx.ALL, 15)

        # Clone from dropdown
        clone_row = wx.BoxSizer(wx.HORIZONTAL)
        clone_label = wx.StaticText(dlg, label="Clone from:")
        clone_label.SetForegroundColour(get_wx_color('text_primary'))
        clone_row.Add(clone_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # Build list of presets to clone from
        clone_choices = ["(Empty preset)"] + self.presets.get_preset_names()
        clone_choice = wx.Choice(dlg, choices=clone_choices)
        clone_choice.SetSelection(0)
        clone_row.Add(clone_choice, 1)
        sizer.Add(clone_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        create_btn = wx.Button(dlg, wx.ID_OK, "Create")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(create_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            name = name_ctrl.GetValue().strip()
            if name:
                clone_from = clone_choice.GetStringSelection()

                # Get data from source preset if cloning
                if clone_from == "(Empty preset)":
                    preset_type = 'Oracle'
                    mappings = {}
                    description = ''
                    suit_names = {}
                else:
                    source = self.presets.get_preset(clone_from)
                    if source:
                        preset_type = source.get('type', 'Oracle')
                        mappings = dict(source.get('mappings', {}))
                        description = source.get('description', '')
                        suit_names = dict(source.get('suit_names', {}))
                    else:
                        preset_type = 'Oracle'
                        mappings = {}
                        description = ''
                        suit_names = {}

                preset_name = f"Custom: {name}"
                self.presets.add_custom_preset(name, preset_type, mappings, description, suit_names)
                self._refresh_presets_list()

                # Select the new preset
                idx = self._find_listctrl_item(self.presets_list, preset_name)
                if idx != -1:
                    self.presets_list.Select(idx)

                # Open editor
                self._open_preset_editor(preset_name)

        dlg.Destroy()

    def _on_edit_preset(self, event):
        """Edit selected preset"""
        idx = self.presets_list.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a preset to edit.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return

        preset_name = self.presets_list.GetItemText(idx)
        self._open_preset_editor(preset_name)

    def _open_preset_editor(self, preset_name):
        """Open the preset editor dialog"""
        preset = self.presets.get_preset(preset_name)
        if not preset:
            return

        dlg = wx.Dialog(self, title=f"Edit Preset: {preset_name}", size=(700, 550))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Instructions
        instr = wx.StaticText(dlg, label="Define filename patterns and their corresponding card names.\nPatterns are matched case-insensitively, ignoring spaces, dashes, and underscores.")
        instr.SetForegroundColour(get_wx_color('text_secondary'))
        sizer.Add(instr, 0, wx.ALL, 10)

        # Type selection
        type_sizer = wx.BoxSizer(wx.HORIZONTAL)
        type_label = wx.StaticText(dlg, label="Deck Type:")
        type_label.SetForegroundColour(get_wx_color('text_primary'))
        type_sizer.Add(type_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        type_choice = wx.Choice(dlg, choices=['Tarot', 'Lenormand', 'Oracle'])
        current_type = preset.get('type', 'Oracle')
        type_idx = type_choice.FindString(current_type)
        if type_idx != wx.NOT_FOUND:
            type_choice.SetSelection(type_idx)
        else:
            type_choice.SetSelection(2)  # Default to Oracle
        type_sizer.Add(type_choice, 0)
        sizer.Add(type_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Description
        desc_sizer = wx.BoxSizer(wx.HORIZONTAL)
        desc_label = wx.StaticText(dlg, label="Description:")
        desc_label.SetForegroundColour(get_wx_color('text_primary'))
        desc_sizer.Add(desc_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        desc_ctrl = wx.TextCtrl(dlg, value=preset.get('description', ''))
        desc_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        desc_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        desc_sizer.Add(desc_ctrl, 1)
        sizer.Add(desc_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Mappings header
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        pattern_header = wx.StaticText(dlg, label="Filename Pattern", size=(250, -1))
        pattern_header.SetForegroundColour(get_wx_color('text_primary'))
        pattern_header.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(pattern_header, 0, wx.LEFT, 10)

        card_header = wx.StaticText(dlg, label="Card Name")
        card_header.SetForegroundColour(get_wx_color('text_primary'))
        card_header.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(card_header, 0, wx.LEFT, 20)
        sizer.Add(header_sizer, 0, wx.BOTTOM, 5)

        # Scrollable mappings area
        scroll = scrolled.ScrolledPanel(dlg)
        scroll.SetBackgroundColour(get_wx_color('bg_secondary'))
        scroll.SetupScrolling()
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        mapping_rows = []
        mappings = preset.get('mappings', {})

        def add_mapping_row(pattern='', card_name=''):
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)

            pattern_ctrl = wx.TextCtrl(scroll, value=pattern, size=(230, -1))
            pattern_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
            pattern_ctrl.SetForegroundColour(get_wx_color('text_primary'))
            row_sizer.Add(pattern_ctrl, 0, wx.RIGHT, 10)

            arrow = wx.StaticText(scroll, label="\u2192")
            arrow.SetForegroundColour(get_wx_color('text_dim'))
            row_sizer.Add(arrow, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

            card_ctrl = wx.TextCtrl(scroll, value=card_name, size=(230, -1))
            card_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
            card_ctrl.SetForegroundColour(get_wx_color('text_primary'))
            row_sizer.Add(card_ctrl, 0, wx.RIGHT, 10)

            remove_btn = wx.Button(scroll, label="\u00d7", size=(30, -1))
            row_sizer.Add(remove_btn, 0)

            scroll_sizer.Add(row_sizer, 0, wx.ALL, 3)
            mapping_rows.append((pattern_ctrl, card_ctrl, row_sizer, remove_btn))

            def on_remove(e, rs=row_sizer, row=(pattern_ctrl, card_ctrl, row_sizer, remove_btn)):
                mapping_rows.remove(row)
                scroll_sizer.Remove(rs)
                pattern_ctrl.Destroy()
                card_ctrl.Destroy()
                remove_btn.Destroy()
                scroll.Layout()
                scroll.SetupScrolling()

            remove_btn.Bind(wx.EVT_BUTTON, on_remove)
            scroll.Layout()
            scroll.SetupScrolling()

        # Load existing mappings
        for pattern, card_name in mappings.items():
            add_mapping_row(pattern, card_name)

        # Add some empty rows if none exist
        if not mappings:
            for _ in range(5):
                add_mapping_row()

        scroll.SetSizer(scroll_sizer)
        sizer.Add(scroll, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Add rows button
        add_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_row_btn = wx.Button(dlg, label="+ Add Row")
        add_row_btn.Bind(wx.EVT_BUTTON, lambda e: add_mapping_row())
        add_btn_sizer.Add(add_row_btn, 0, wx.RIGHT, 10)

        add_10_btn = wx.Button(dlg, label="+ Add 10 Rows")
        add_10_btn.Bind(wx.EVT_BUTTON, lambda e: [add_mapping_row() for _ in range(10)])
        add_btn_sizer.Add(add_10_btn, 0)
        sizer.Add(add_btn_sizer, 0, wx.ALL, 10)

        # Save/Cancel buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Save")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            # Collect mappings
            new_mappings = {}
            for pattern_ctrl, card_ctrl, _, _ in mapping_rows:
                pattern = pattern_ctrl.GetValue().strip()
                card_name = card_ctrl.GetValue().strip()
                if pattern and card_name:
                    new_mappings[pattern] = card_name

            new_type = type_choice.GetStringSelection()
            new_desc = desc_ctrl.GetValue().strip()

            # Preserve suit_names from original preset
            suit_names = preset.get('suit_names', {})

            # Extract the name without "Custom: " prefix
            if preset_name.startswith("Custom: "):
                base_name = preset_name[8:]
            else:
                base_name = preset_name

            # Delete old custom preset if it exists, then add new
            self.presets.delete_custom_preset(preset_name)
            self.presets.add_custom_preset(base_name, new_type, new_mappings, new_desc, suit_names)

            self._refresh_presets_list()

            # Reselect - builtin presets keep their name, custom gets "Custom: " prefix
            if self.presets.is_builtin_preset(base_name):
                new_name = base_name  # Builtin name stays the same
            else:
                new_name = f"Custom: {base_name}"

            idx = self._find_listctrl_item(self.presets_list, new_name)
            if idx != -1:
                self.presets_list.Select(idx)
                self._on_preset_select(None)

            wx.MessageBox("Preset saved!", "Success", wx.OK | wx.ICON_INFORMATION)

        dlg.Destroy()

    def _on_delete_preset(self, event):
        idx = self.presets_list.GetFirstSelected()
        if idx == -1:
            return

        preset_name = self.presets_list.GetItemText(idx)

        # Check if it's a builtin that hasn't been customized
        if self.presets.is_builtin_preset(preset_name) and not self.presets.is_preset_customized(preset_name):
            wx.MessageBox("Built-in presets cannot be deleted.\n\nYou can edit them to customize, then delete to revert.", "Cannot Delete", wx.OK | wx.ICON_WARNING)
            return

        # If it's a customized builtin, offer to revert
        if self.presets.is_builtin_preset(preset_name) and self.presets.is_preset_customized(preset_name):
            if wx.MessageBox(f"Revert '{preset_name}' to default settings?", "Confirm Revert", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                self.presets.delete_custom_preset(preset_name)
                self._refresh_presets_list()
                wx.MessageBox("Preset reverted to defaults.", "Done", wx.OK | wx.ICON_INFORMATION)
            return

        # Regular custom preset deletion
        if wx.MessageBox(f"Delete '{preset_name}'?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.presets.delete_custom_preset(preset_name)
            self._refresh_presets_list()

    def _on_clear_cache(self, event):
        if wx.MessageBox("Clear all cached thumbnails?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.thumb_cache.clear_cache()
            self._update_cache_info()
            wx.MessageBox("Cache cleared.", "Done", wx.OK | wx.ICON_INFORMATION)

    def _on_create_backup(self, event):
        """Create a full backup of the database and config files."""
        from pathlib import Path

        # Get default backup directory
        backup_dir = Path.home() / "Documents" / "TarotJournalBackups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"tarot_journal_backup_{timestamp}.zip"

        # Show file dialog
        with wx.FileDialog(
            self, "Save Backup",
            defaultDir=str(backup_dir),
            defaultFile=default_filename,
            wildcard="Backup files (*.zip)|*.zip",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return

            filepath = dlg.GetPath()

        # Get include images option
        include_images = self.backup_include_images_cb.GetValue()

        # Show busy cursor for potentially long operation
        wx.BeginBusyCursor()
        try:
            result = self.db.create_full_backup(filepath, include_images)

            # Update last backup label
            last_backup_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.last_backup_label.SetLabel(f"Last backup: {last_backup_str}")

            # Show success message
            msg = f"Backup created successfully!\n\n"
            msg += f"Location: {filepath}\n"
            msg += f"Entries: {result['entry_count']}\n"
            msg += f"Decks: {result['deck_count']}\n"
            if include_images:
                msg += f"Images: {result['images_included']}\n"
            if result['presets_included']:
                msg += "Import presets: included"

            wx.MessageBox(msg, "Backup Complete", wx.OK | wx.ICON_INFORMATION)

        except Exception as e:
            wx.MessageBox(f"Error creating backup:\n{str(e)}", "Backup Error", wx.OK | wx.ICON_ERROR)
        finally:
            wx.EndBusyCursor()

    def _on_restore_backup(self, event):
        """Restore database and config files from a backup."""
        # Show warning
        result = wx.MessageBox(
            "WARNING: Restoring from a backup will replace ALL current data!\n\n"
            "This includes:\n"
            "\u2022 All journal entries\n"
            "\u2022 All decks and cards\n"
            "\u2022 All spreads and profiles\n"
            "\u2022 All tags and settings\n\n"
            "This action cannot be undone. Continue?",
            "Confirm Restore",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
        )

        if result != wx.YES:
            return

        # Get default backup directory
        from pathlib import Path
        backup_dir = Path.home() / "Documents" / "TarotJournalBackups"
        if not backup_dir.exists():
            backup_dir = Path.home() / "Documents"

        # Show file dialog
        with wx.FileDialog(
            self, "Select Backup to Restore",
            defaultDir=str(backup_dir),
            wildcard="Backup files (*.zip)|*.zip",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return

            filepath = dlg.GetPath()

        # Show busy cursor
        wx.BeginBusyCursor()
        try:
            result = self.db.restore_from_backup(filepath)

            # Refresh all UI panels
            self._refresh_all()
            self._refresh_profiles_list()
            self._refresh_presets_list()
            self._update_cache_info()

            # Reload import presets
            from import_presets import get_presets
            self.presets = get_presets()

            # Show success message
            msg = f"Backup restored successfully!\n\n"
            msg += f"Backup date: {result['backup_date']}\n"
            msg += f"Entries: {result['entry_count']}\n"
            msg += f"Decks: {result['deck_count']}\n"
            if result['images_restored'] > 0:
                msg += f"Images restored: {result['images_restored']}\n"
            if result['presets_restored']:
                msg += "Import presets: restored"

            wx.MessageBox(msg, "Restore Complete", wx.OK | wx.ICON_INFORMATION)

        except ValueError as e:
            wx.MessageBox(f"Invalid backup file:\n{str(e)}", "Restore Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error restoring backup:\n{str(e)}", "Restore Error", wx.OK | wx.ICON_ERROR)
        finally:
            wx.EndBusyCursor()

    def _on_stats(self, event):
        stats = self.db.get_stats()

        msg = f"""Your Tarot Journey

Total Journal Entries: {stats['total_entries']}
Total Decks: {stats['total_decks']}
Total Cards: {stats['total_cards']}
Saved Spreads: {stats['total_spreads']}

Most Used Decks:
"""
        for deck in stats['top_decks']:
            msg += f"  \u2022 {deck[0]}: {deck[1]} readings\n"

        msg += "\nMost Used Spreads:\n"
        for spread in stats['top_spreads']:
            msg += f"  \u2022 {spread[0]}: {spread[1]} readings\n"

        wx.MessageBox(msg, "Statistics", wx.OK | wx.ICON_INFORMATION)
