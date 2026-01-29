"""DEPRECATED: Legacy wxPython UI - see frontend/ for active Electron/React code.

Profiles panel mixin for MainFrame."""

import wx
import wx.adv
from datetime import datetime
from ui_helpers import logger, get_wx_color


class ProfilesMixin:

    # ═══════════════════════════════════════════
    # PROFILES PANEL
    # ═══════════════════════════════════════════
    def _create_profiles_panel(self):
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: profiles list
        left_panel = wx.Panel(panel)
        left_panel.SetBackgroundColour(get_wx_color('bg_primary'))
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        list_label = wx.StaticText(left_panel, label="Profiles")
        list_label.SetForegroundColour(get_wx_color('accent'))
        list_label.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        left_sizer.Add(list_label, 0, wx.ALL, 10)

        self.profiles_list = wx.ListCtrl(left_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.profiles_list.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.profiles_list.SetForegroundColour(get_wx_color('text_primary'))
        self.profiles_list.InsertColumn(0, "Name", width=150)
        self.profiles_list.InsertColumn(1, "Gender", width=80)
        self.profiles_list.InsertColumn(2, "Birth Date", width=100)
        self.profiles_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_profile_selected)
        left_sizer.Add(self.profiles_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(left_panel, label="Add Profile")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add_profile)
        edit_btn = wx.Button(left_panel, label="Edit")
        edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_profile)
        delete_btn = wx.Button(left_panel, label="Delete")
        delete_btn.Bind(wx.EVT_BUTTON, self._on_delete_profile)

        btn_sizer.Add(add_btn, 1, wx.RIGHT, 5)
        btn_sizer.Add(edit_btn, 1, wx.RIGHT, 5)
        btn_sizer.Add(delete_btn, 1)
        left_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        left_panel.SetSizer(left_sizer)

        # Right side: profile details view
        right_panel = wx.Panel(panel)
        right_panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        details_label = wx.StaticText(right_panel, label="Profile Details")
        details_label.SetForegroundColour(get_wx_color('accent'))
        details_label.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        right_sizer.Add(details_label, 0, wx.ALL, 10)

        self.profile_details_text = wx.StaticText(right_panel, label="Select a profile to view details")
        self.profile_details_text.SetForegroundColour(get_wx_color('text_secondary'))
        right_sizer.Add(self.profile_details_text, 1, wx.EXPAND | wx.ALL, 10)

        right_panel.SetSizer(right_sizer)

        sizer.Add(left_panel, 1, wx.EXPAND)
        sizer.Add(right_panel, 1, wx.EXPAND)

        panel.SetSizer(sizer)

        # Load profiles
        self._refresh_profiles_list()

        return panel

    def _refresh_profiles_list(self):
        """Refresh the profiles list"""
        self.profiles_list.DeleteAllItems()
        profiles = self.db.get_profiles()
        for profile in profiles:
            idx = self.profiles_list.InsertItem(self.profiles_list.GetItemCount(), profile['name'])
            self.profiles_list.SetItem(idx, 1, profile['gender'] or '')
            self.profiles_list.SetItem(idx, 2, profile['birth_date'] or '')
            self.profiles_list.SetItemData(idx, profile['id'])

    def _on_profile_selected(self, event):
        """Handle profile selection"""
        idx = self.profiles_list.GetFirstSelected()
        if idx == -1:
            self.profile_details_text.SetLabel("Select a profile to view details")
            return

        profile_id = self.profiles_list.GetItemData(idx)
        profile = self.db.get_profile(profile_id)
        if not profile:
            return

        details = f"Name: {profile['name']}\n\n"
        details += f"Gender: {profile['gender'] or 'Not specified'}\n\n"
        details += f"Birth Date: {profile['birth_date'] or 'Not specified'}\n"
        details += f"Birth Time: {profile['birth_time'] or 'Not specified'}\n\n"
        details += f"Birth Place: {profile['birth_place_name'] or 'Not specified'}\n"
        if profile['birth_place_lat'] and profile['birth_place_lon']:
            details += f"Coordinates: {profile['birth_place_lat']:.4f}, {profile['birth_place_lon']:.4f}"

        self.profile_details_text.SetLabel(details)

    def _on_add_profile(self, event):
        """Add a new profile"""
        self._show_profile_dialog()

    def _on_edit_profile(self, event):
        """Edit selected profile"""
        idx = self.profiles_list.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a profile to edit.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        profile_id = self.profiles_list.GetItemData(idx)
        self._show_profile_dialog(profile_id)

    def _on_delete_profile(self, event):
        """Delete selected profile"""
        idx = self.profiles_list.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a profile to delete.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return

        profile_id = self.profiles_list.GetItemData(idx)
        profile = self.db.get_profile(profile_id)

        result = wx.MessageBox(
            f"Delete profile '{profile['name']}'?\n\nThis will remove the profile from any journal entries that reference it.",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_WARNING
        )
        if result == wx.YES:
            self.db.delete_profile(profile_id)
            self._refresh_profiles_list()
            self.profile_details_text.SetLabel("Select a profile to view details")

    def _show_profile_dialog(self, profile_id=None):
        """Show dialog to add or edit a profile"""
        is_edit = profile_id is not None
        profile = self.db.get_profile(profile_id) if is_edit else None

        dlg = wx.Dialog(self, title="Edit Profile" if is_edit else "Add Profile", size=(450, 400))
        dlg.SetBackgroundColour(get_wx_color('bg_primary'))

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Name
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(dlg, label="Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        name_ctrl = wx.TextCtrl(dlg, value=profile['name'] if profile else "")
        name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_ctrl, 1)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Gender
        gender_sizer = wx.BoxSizer(wx.HORIZONTAL)
        gender_label = wx.StaticText(dlg, label="Gender:")
        gender_label.SetForegroundColour(get_wx_color('text_primary'))
        gender_sizer.Add(gender_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        gender_choices = ["", "Male", "Female", "Nonbinary"]
        gender_ctrl = wx.Choice(dlg, choices=gender_choices)
        gender_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        current_gender = profile['gender'] if profile else ""
        if current_gender in gender_choices:
            gender_ctrl.SetSelection(gender_choices.index(current_gender))
        else:
            gender_ctrl.SetSelection(0)
        gender_sizer.Add(gender_ctrl, 1)
        sizer.Add(gender_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Birth Date
        birth_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        birth_date_label = wx.StaticText(dlg, label="Birth Date:")
        birth_date_label.SetForegroundColour(get_wx_color('text_primary'))
        birth_date_sizer.Add(birth_date_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        birth_date_ctrl = wx.adv.DatePickerCtrl(dlg, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY | wx.adv.DP_ALLOWNONE)
        if profile and profile['birth_date']:
            try:
                dt = datetime.strptime(profile['birth_date'], '%Y-%m-%d')
                wx_date = wx.DateTime()
                wx_date.Set(dt.day, dt.month - 1, dt.year)
                birth_date_ctrl.SetValue(wx_date)
            except (ValueError, TypeError) as e:
                logger.debug("Could not parse birth date: %s", e)
        birth_date_sizer.Add(birth_date_ctrl, 1)
        sizer.Add(birth_date_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Birth Time
        birth_time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        birth_time_label = wx.StaticText(dlg, label="Birth Time:")
        birth_time_label.SetForegroundColour(get_wx_color('text_primary'))
        birth_time_sizer.Add(birth_time_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        birth_time_ctrl = wx.TextCtrl(dlg, value=profile['birth_time'] if profile and profile['birth_time'] else "")
        birth_time_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        birth_time_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        birth_time_ctrl.SetHint("HH:MM (24-hour format)")
        birth_time_sizer.Add(birth_time_ctrl, 1)
        sizer.Add(birth_time_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Birth Place
        birth_place_sizer = wx.BoxSizer(wx.HORIZONTAL)
        birth_place_label = wx.StaticText(dlg, label="Birth Place:")
        birth_place_label.SetForegroundColour(get_wx_color('text_primary'))
        birth_place_sizer.Add(birth_place_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        birth_place_ctrl = wx.TextCtrl(dlg, value=profile['birth_place_name'] if profile and profile['birth_place_name'] else "")
        birth_place_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        birth_place_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        birth_place_ctrl.SetHint("City, Country")
        birth_place_sizer.Add(birth_place_ctrl, 1)
        sizer.Add(birth_place_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Birth coordinates (optional, for future astro use)
        coords_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lat_label = wx.StaticText(dlg, label="Latitude:")
        lat_label.SetForegroundColour(get_wx_color('text_secondary'))
        coords_sizer.Add(lat_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        lat_ctrl = wx.TextCtrl(dlg, size=(80, -1), value=str(profile['birth_place_lat']) if profile and profile['birth_place_lat'] else "")
        lat_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        lat_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        coords_sizer.Add(lat_ctrl, 0, wx.RIGHT, 15)

        lon_label = wx.StaticText(dlg, label="Longitude:")
        lon_label.SetForegroundColour(get_wx_color('text_secondary'))
        coords_sizer.Add(lon_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        lon_ctrl = wx.TextCtrl(dlg, size=(80, -1), value=str(profile['birth_place_lon']) if profile and profile['birth_place_lon'] else "")
        lon_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        lon_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        coords_sizer.Add(lon_ctrl, 0)
        sizer.Add(coords_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        coords_note = wx.StaticText(dlg, label="(Coordinates are optional - for future astrological features)")
        coords_note.SetForegroundColour(get_wx_color('text_dim'))
        sizer.Add(coords_note, 0, wx.LEFT | wx.BOTTOM, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        save_btn = wx.Button(dlg, wx.ID_OK, "Save")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(save_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        dlg.SetSizer(sizer)

        if dlg.ShowModal() == wx.ID_OK:
            name = name_ctrl.GetValue().strip()
            if not name:
                wx.MessageBox("Name is required.", "Validation Error", wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return

            gender = gender_ctrl.GetStringSelection()
            if gender == "":
                gender = None

            # Get birth date
            birth_date = None
            if birth_date_ctrl.GetValue().IsValid():
                wx_date = birth_date_ctrl.GetValue()
                birth_date = f"{wx_date.GetYear()}-{wx_date.GetMonth()+1:02d}-{wx_date.GetDay():02d}"

            birth_time = birth_time_ctrl.GetValue().strip() or None
            birth_place = birth_place_ctrl.GetValue().strip() or None

            # Parse coordinates
            lat = None
            lon = None
            try:
                lat_str = lat_ctrl.GetValue().strip()
                lon_str = lon_ctrl.GetValue().strip()
                if lat_str:
                    lat = float(lat_str)
                if lon_str:
                    lon = float(lon_str)
            except ValueError:
                pass

            if is_edit:
                self.db.update_profile(profile_id, name=name, gender=gender,
                                       birth_date=birth_date, birth_time=birth_time,
                                       birth_place_name=birth_place,
                                       birth_place_lat=lat, birth_place_lon=lon)
            else:
                self.db.add_profile(name=name, gender=gender,
                                    birth_date=birth_date, birth_time=birth_time,
                                    birth_place_name=birth_place,
                                    birth_place_lat=lat, birth_place_lon=lon)

            self._refresh_profiles_list()
            self.profile_details_text.SetLabel("Select a profile to view details")

        dlg.Destroy()
