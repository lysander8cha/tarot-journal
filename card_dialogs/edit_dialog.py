"""Card edit dialog for editing card details."""

import json

import wx
import wx.lib.scrolledpanel as scrolled
import wx.lib.agw.flatnotebook as fnb

from ui_helpers import logger, _cfg, get_wx_color
from image_utils import load_and_scale_image
from widgets import ArchetypeAutocomplete
from rich_text_panel import RichTextPanel


class CardEditDialog(wx.Dialog):
    """
    Dialog for editing card details with navigation support.
    Updates content in-place when navigating between cards to preserve window position.
    """
    def __init__(self, parent, db, thumb_cache, card_id, card_ids=None,
                 on_refresh_callback=None, selected_tab=0):
        super().__init__(parent, title="Edit Card", size=(750, 580),
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetBackgroundColour(get_wx_color('bg_primary'))

        self.parent = parent
        self.db = db
        self.thumb_cache = thumb_cache
        self.card_ids = card_ids or []
        self.current_card_id = card_id
        self.on_refresh_callback = on_refresh_callback
        self.initial_tab = selected_tab
        self.save_requested = False
        self.data_modified = False

        # These will be set during _build_ui and updated during _load_card
        self.notebook = None
        self.image_panel = None
        self.image_sizer = None
        self.form_container = None
        self.form_sizer = None
        self.prev_btn = None
        self.next_btn = None

        # Form control references (rebuilt for each card)
        self._form_controls = {}

        self._build_ui()
        self._load_card(card_id)

    def _build_ui(self):
        """Build the dialog UI structure (called once)"""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Content area - horizontal split
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: Image panel
        self.image_panel = wx.Panel(self)
        self.image_panel.SetBackgroundColour(get_wx_color('bg_secondary'))
        self.image_sizer = wx.BoxSizer(wx.VERTICAL)
        self.image_panel.SetSizer(self.image_sizer)
        content_sizer.Add(self.image_panel, 0, wx.ALL, 10)

        # Right side: Form container (will hold notebook)
        self.form_container = wx.Panel(self)
        self.form_container.SetBackgroundColour(get_wx_color('bg_primary'))
        self.form_sizer = wx.BoxSizer(wx.VERTICAL)
        self.form_container.SetSizer(self.form_sizer)
        content_sizer.Add(self.form_container, 1, wx.EXPAND | wx.ALL, 10)

        self.main_sizer.Add(content_sizer, 1, wx.EXPAND)

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

        # Save/Cancel buttons on the right
        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)

        save_btn = wx.Button(self, wx.ID_OK, "Save")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        btn_sizer.Add(save_btn, 0)

        self.main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(self.main_sizer)

    def _load_card(self, card_id, preserve_tab=False):
        """Load and display a card's edit form"""
        # Save current tab if preserving
        current_tab = 0
        if preserve_tab and self.notebook:
            current_tab = self.notebook.GetSelection()
        else:
            current_tab = self.initial_tab

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
        deck_custom_fields = self.db.get_deck_custom_fields(deck_id)

        # Update window title
        self.SetTitle(f"Edit Card: {card['name']}")

        # Helper to safely get card fields
        def get_field(field_name, default=''):
            try:
                if field_name in card.keys():
                    return card[field_name] if card[field_name] is not None else default
            except (KeyError, TypeError):
                pass
            return default

        # Parse existing custom field values
        existing_custom_values = {}
        try:
            custom_fields_json = get_field('custom_fields', None)
            if custom_fields_json:
                existing_custom_values = json.loads(custom_fields_json)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse custom fields JSON: %s", e)

        # Clear and rebuild image panel
        self.image_sizer.Clear(True)
        self._build_image_preview(card)
        self.image_panel.Layout()

        # Clear and rebuild form
        self.form_sizer.Clear(True)
        self._build_form(card, deck, cartomancy_type, deck_custom_fields, existing_custom_values, get_field)
        self.form_container.Layout()

        # Restore tab selection
        if self.notebook and current_tab > 0 and current_tab < self.notebook.GetPageCount():
            self.notebook.SetSelection(current_tab)

        # Update navigation buttons
        self._update_nav_buttons()

        self.Layout()

    def _build_image_preview(self, card):
        """Build the image preview panel"""
        _card_edit_sz = _cfg.get('images', 'card_edit_max', [300, 450])
        image_path = card['image_path']

        wx_bitmap = load_and_scale_image(image_path, tuple(_card_edit_sz), as_wx_bitmap=True)

        if wx_bitmap:
            bmp = wx.StaticBitmap(self.image_panel, bitmap=wx_bitmap)
            self.image_sizer.Add(bmp, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        else:
            self._add_placeholder_image()

    def _add_placeholder_image(self):
        """Add a placeholder when no image is available"""
        no_img = wx.StaticText(self.image_panel, label="🂠")
        no_img.SetFont(wx.Font(72, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        no_img.SetForegroundColour(get_wx_color('text_dim'))
        self.image_sizer.Add(no_img, 0, wx.ALL | wx.ALIGN_CENTER, 10)

    def _build_form(self, card, deck, cartomancy_type, deck_custom_fields, existing_custom_values, get_field):
        """Build the form with all tabs"""
        # Reset form controls
        self._form_controls = {
            'card': card,
            'deck_id': deck['id'],
            'cartomancy_type': cartomancy_type,
        }

        # Create notebook
        style = (fnb.FNB_NO_X_BUTTON | fnb.FNB_NO_NAV_BUTTONS | fnb.FNB_NODRAG)
        self.notebook = fnb.FlatNotebook(self.form_container, agwStyle=style)
        self.notebook.SetBackgroundColour(get_wx_color('bg_primary'))
        self.notebook.SetTabAreaColour(get_wx_color('bg_primary'))
        self.notebook.SetActiveTabColour(get_wx_color('bg_tertiary'))
        self.notebook.SetNonActiveTabTextColour(get_wx_color('text_primary'))
        self.notebook.SetActiveTabTextColour(get_wx_color('text_primary'))
        self.notebook.SetGradientColourTo(get_wx_color('bg_tertiary'))
        self.notebook.SetGradientColourFrom(get_wx_color('bg_secondary'))

        # Build tabs
        self._build_basic_tab(card, get_field)
        self._build_classification_tab(card, cartomancy_type, get_field)
        self._build_notes_tab(get_field)
        self._build_tags_tab(card['id'])
        self._build_groups_tab(card['id'], deck['id'])
        self._build_custom_fields_tab(deck_custom_fields, existing_custom_values)

        self.form_sizer.Add(self.notebook, 1, wx.EXPAND)

    def _build_basic_tab(self, card, get_field):
        """Build the Basic Info tab"""
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Name
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(panel, label="Name:")
        name_label.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        name_ctrl = wx.TextCtrl(panel, value=card['name'])
        name_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        name_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        name_sizer.Add(name_ctrl, 1)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 10)
        self._form_controls['name'] = name_ctrl

        # Image path
        image_sizer = wx.BoxSizer(wx.HORIZONTAL)
        image_label = wx.StaticText(panel, label="Image:")
        image_label.SetForegroundColour(get_wx_color('text_primary'))
        image_sizer.Add(image_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        image_ctrl = wx.TextCtrl(panel, value=card['image_path'] or '')
        image_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        image_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        image_sizer.Add(image_ctrl, 1, wx.RIGHT, 5)
        self._form_controls['image_path'] = image_ctrl

        browse_btn = wx.Button(panel, label="Browse")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse_image)
        image_sizer.Add(browse_btn, 0)
        sizer.Add(image_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Sort order
        order_sizer = wx.BoxSizer(wx.HORIZONTAL)
        order_label = wx.StaticText(panel, label="Sort Order:")
        order_label.SetForegroundColour(get_wx_color('text_primary'))
        order_sizer.Add(order_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        order_ctrl = wx.SpinCtrl(panel, min=0, max=999, initial=get_field('card_order', 0) or 0)
        order_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        order_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        order_sizer.Add(order_ctrl, 0)
        sizer.Add(order_sizer, 0, wx.EXPAND | wx.ALL, 10)
        self._form_controls['card_order'] = order_ctrl

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Basic Info")

    def _build_classification_tab(self, card, cartomancy_type, get_field):
        """Build the Classification tab"""
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Archetype
        arch_sizer = wx.BoxSizer(wx.HORIZONTAL)
        arch_label = wx.StaticText(panel, label="Archetype:")
        arch_label.SetForegroundColour(get_wx_color('text_primary'))
        arch_sizer.Add(arch_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        archetype_ctrl = ArchetypeAutocomplete(
            panel, self.db, cartomancy_type,
            value=get_field('archetype', '')
        )
        arch_sizer.Add(archetype_ctrl, 1, wx.EXPAND)
        sizer.Add(arch_sizer, 0, wx.EXPAND | wx.ALL, 10)
        self._form_controls['archetype'] = archetype_ctrl

        # Type-specific fields
        rank_ctrl = None
        suit_ctrl = None

        if cartomancy_type == 'Tarot':
            rank_ctrl, suit_ctrl = self._build_tarot_fields(panel, sizer, get_field)
        elif cartomancy_type == 'Playing Cards':
            rank_ctrl, suit_ctrl = self._build_playing_cards_fields(panel, sizer, get_field)
        elif cartomancy_type == 'Lenormand':
            rank_ctrl, suit_ctrl = self._build_lenormand_fields(panel, sizer, get_field)
        elif cartomancy_type == 'I Ching':
            rank_ctrl, suit_ctrl = self._build_iching_fields(panel, sizer, card, get_field)
        elif cartomancy_type == 'Oracle':
            help_text = wx.StaticText(panel,
                label="Oracle decks use free-text archetypes.\nNo predefined ranks or suits.")
            help_text.SetForegroundColour(get_wx_color('text_secondary'))
            sizer.Add(help_text, 0, wx.ALL, 10)

        self._form_controls['rank'] = rank_ctrl
        self._form_controls['suit'] = suit_ctrl

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Classification")

    def _build_tarot_fields(self, panel, sizer, get_field):
        """Build Tarot-specific rank and suit fields"""
        # Rank
        rank_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rank_label = wx.StaticText(panel, label="Rank:")
        rank_label.SetForegroundColour(get_wx_color('text_primary'))
        rank_sizer.Add(rank_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        tarot_ranks = ['', 'Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                      'Eight', 'Nine', 'Ten',
                      'Page / Knave / Princess / Court Rank 1',
                      'Knight / Prince / Court Rank 2',
                      'Queen / Court Rank 3',
                      'King / Court Rank 4',
                      '0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX',
                      'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII',
                      'XIX', 'XX', 'XXI']
        rank_ctrl = wx.Choice(panel, choices=tarot_ranks)
        current_rank = get_field('rank', '')
        if current_rank in tarot_ranks:
            rank_ctrl.SetSelection(tarot_ranks.index(current_rank))
        rank_sizer.Add(rank_ctrl, 1)
        sizer.Add(rank_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Suit
        suit_sizer = wx.BoxSizer(wx.HORIZONTAL)
        suit_label = wx.StaticText(panel, label="Suit:")
        suit_label.SetForegroundColour(get_wx_color('text_primary'))
        suit_sizer.Add(suit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        tarot_suits = ['', 'Major Arcana', 'Wands', 'Cups', 'Swords', 'Pentacles']
        suit_ctrl = wx.Choice(panel, choices=tarot_suits)
        current_suit = get_field('suit', '')
        if current_suit in tarot_suits:
            suit_ctrl.SetSelection(tarot_suits.index(current_suit))
        suit_sizer.Add(suit_ctrl, 1)
        sizer.Add(suit_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        return rank_ctrl, suit_ctrl

    def _build_playing_cards_fields(self, panel, sizer, get_field):
        """Build Playing Cards-specific rank and suit fields"""
        rank_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rank_label = wx.StaticText(panel, label="Rank:")
        rank_label.SetForegroundColour(get_wx_color('text_primary'))
        rank_sizer.Add(rank_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        playing_ranks = ['', 'Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                        'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King', 'Joker']
        rank_ctrl = wx.Choice(panel, choices=playing_ranks)
        current_rank = get_field('rank', '')
        if current_rank in playing_ranks:
            rank_ctrl.SetSelection(playing_ranks.index(current_rank))
        rank_sizer.Add(rank_ctrl, 1)
        sizer.Add(rank_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        suit_sizer = wx.BoxSizer(wx.HORIZONTAL)
        suit_label = wx.StaticText(panel, label="Suit:")
        suit_label.SetForegroundColour(get_wx_color('text_primary'))
        suit_sizer.Add(suit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        playing_suits = ['', 'Hearts', 'Diamonds', 'Clubs', 'Spades']
        suit_ctrl = wx.Choice(panel, choices=playing_suits)
        current_suit = get_field('suit', '')
        if current_suit in playing_suits:
            suit_ctrl.SetSelection(playing_suits.index(current_suit))
        suit_sizer.Add(suit_ctrl, 1)
        sizer.Add(suit_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        return rank_ctrl, suit_ctrl

    def _build_lenormand_fields(self, panel, sizer, get_field):
        """Build Lenormand-specific rank and suit fields"""
        rank_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rank_label = wx.StaticText(panel, label="Playing Card Rank:")
        rank_label.SetForegroundColour(get_wx_color('text_primary'))
        rank_sizer.Add(rank_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        lenormand_ranks = ['', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        rank_ctrl = wx.Choice(panel, choices=lenormand_ranks)
        current_rank = get_field('rank', '')
        if current_rank in lenormand_ranks:
            rank_ctrl.SetSelection(lenormand_ranks.index(current_rank))
        rank_sizer.Add(rank_ctrl, 1)
        sizer.Add(rank_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        suit_sizer = wx.BoxSizer(wx.HORIZONTAL)
        suit_label = wx.StaticText(panel, label="Playing Card Suit:")
        suit_label.SetForegroundColour(get_wx_color('text_primary'))
        suit_sizer.Add(suit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        lenormand_suits = ['', 'Hearts', 'Diamonds', 'Clubs', 'Spades']
        suit_ctrl = wx.Choice(panel, choices=lenormand_suits)
        current_suit = get_field('suit', '')
        if current_suit in lenormand_suits:
            suit_ctrl.SetSelection(lenormand_suits.index(current_suit))
        suit_sizer.Add(suit_ctrl, 1)
        sizer.Add(suit_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        return rank_ctrl, suit_ctrl

    def _build_iching_fields(self, panel, sizer, card, get_field):
        """Build I Ching-specific fields"""
        # Hexagram Number
        hex_sizer = wx.BoxSizer(wx.HORIZONTAL)
        hex_label = wx.StaticText(panel, label="Hexagram Number:")
        hex_label.SetForegroundColour(get_wx_color('text_primary'))
        hex_sizer.Add(hex_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        hex_numbers = [''] + [str(i) for i in range(1, 65)]
        rank_ctrl = wx.Choice(panel, choices=hex_numbers)
        current_rank = get_field('rank', '')
        if current_rank in hex_numbers:
            rank_ctrl.SetSelection(hex_numbers.index(current_rank))
        hex_sizer.Add(rank_ctrl, 1)
        sizer.Add(hex_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Pinyin
        pinyin_sizer = wx.BoxSizer(wx.HORIZONTAL)
        pinyin_label = wx.StaticText(panel, label="Pinyin:")
        pinyin_label.SetForegroundColour(get_wx_color('text_primary'))
        pinyin_sizer.Add(pinyin_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        suit_ctrl = wx.TextCtrl(panel)
        suit_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        suit_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        suit_ctrl.SetValue(get_field('suit', ''))
        pinyin_sizer.Add(suit_ctrl, 1)
        sizer.Add(pinyin_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Get custom fields for Chinese characters
        custom_fields = {}
        try:
            cf_json = card.get('custom_fields') if hasattr(card, 'get') else (card['custom_fields'] if 'custom_fields' in card.keys() else None)
            if cf_json:
                custom_fields = json.loads(cf_json) if isinstance(cf_json, str) else cf_json
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            logger.warning("Failed to parse custom fields for card edit: %s", e)

        # Traditional Chinese
        trad_sizer = wx.BoxSizer(wx.HORIZONTAL)
        trad_label = wx.StaticText(panel, label="Traditional Chinese:")
        trad_label.SetForegroundColour(get_wx_color('text_primary'))
        trad_sizer.Add(trad_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        trad_ctrl = wx.TextCtrl(panel)
        trad_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        trad_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        trad_ctrl.SetValue(custom_fields.get('traditional_chinese', ''))
        trad_sizer.Add(trad_ctrl, 1)
        sizer.Add(trad_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._form_controls['iching_trad'] = trad_ctrl

        # Simplified Chinese
        simp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        simp_label = wx.StaticText(panel, label="Simplified Chinese:")
        simp_label.SetForegroundColour(get_wx_color('text_primary'))
        simp_sizer.Add(simp_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        simp_ctrl = wx.TextCtrl(panel)
        simp_ctrl.SetBackgroundColour(get_wx_color('bg_input'))
        simp_ctrl.SetForegroundColour(get_wx_color('text_primary'))
        simp_ctrl.SetValue(custom_fields.get('simplified_chinese', ''))
        simp_sizer.Add(simp_ctrl, 1)
        sizer.Add(simp_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._form_controls['iching_simp'] = simp_ctrl

        return rank_ctrl, suit_ctrl

    def _build_notes_tab(self, get_field):
        """Build the Notes tab"""
        panel = scrolled.ScrolledPanel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))
        panel.SetupScrolling(scroll_x=False)
        sizer = wx.BoxSizer(wx.VERTICAL)

        notes_label = wx.StaticText(panel, label="Personal Notes / Interpretations:")
        notes_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(notes_label, 0, wx.ALL, 10)

        notes_ctrl = RichTextPanel(panel, value=get_field('notes', ''), min_height=150)
        sizer.Add(notes_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._form_controls['notes'] = notes_ctrl

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Notes")

    def _build_tags_tab(self, card_id):
        """Build the Tags tab"""
        panel = wx.Panel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Inherited tags from deck (read-only)
        inherited_tags = self.db.get_inherited_tags_for_card(card_id)
        if inherited_tags:
            inherited_label = wx.StaticText(panel, label="Inherited from deck:")
            inherited_label.SetForegroundColour(get_wx_color('text_secondary'))
            sizer.Add(inherited_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

            inherited_tags_text = ", ".join([t['name'] for t in inherited_tags])
            inherited_display = wx.StaticText(panel, label=inherited_tags_text)
            inherited_display.SetForegroundColour(get_wx_color('text_dim'))
            sizer.Add(inherited_display, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Card-specific tags
        card_tags_label = wx.StaticText(panel, label="Card Tags:")
        card_tags_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(card_tags_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Get current card tags and all available card tags
        current_card_tags = {t['id'] for t in self.db.get_tags_for_card(card_id)}
        all_card_tags = list(self.db.get_card_tags())
        self._form_controls['all_card_tags'] = all_card_tags

        # CheckListBox for tag selection
        card_tag_choices = [tag['name'] for tag in all_card_tags]
        card_tag_checklist = wx.CheckListBox(panel, choices=card_tag_choices)
        card_tag_checklist.SetBackgroundColour(get_wx_color('bg_secondary'))
        card_tag_checklist.SetForegroundColour(get_wx_color('text_primary'))

        for i, tag in enumerate(all_card_tags):
            if tag['id'] in current_card_tags:
                card_tag_checklist.Check(i, True)

        sizer.Add(card_tag_checklist, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        self._form_controls['tag_checklist'] = card_tag_checklist

        # Button to add new card tag
        add_btn = wx.Button(panel, label="+ New Tag")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add_tag)
        sizer.Add(add_btn, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Tags")

    def _build_groups_tab(self, card_id, deck_id):
        """Build the Groups tab"""
        panel = scrolled.ScrolledPanel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))
        panel.SetupScrolling(scroll_x=False)
        sizer = wx.BoxSizer(wx.VERTICAL)

        groups_label = wx.StaticText(panel, label="Card Groups:")
        groups_label.SetForegroundColour(get_wx_color('text_primary'))
        sizer.Add(groups_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Get current card groups and all available groups for this deck
        current_card_groups = {g['id'] for g in self.db.get_groups_for_card(card_id)}
        all_groups = list(self.db.get_card_groups(deck_id))
        self._form_controls['all_card_groups'] = all_groups

        if all_groups:
            # Individual checkboxes with separate labels (macOS color fix)
            group_checkboxes = []
            for group in all_groups:
                cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
                cb = wx.CheckBox(panel, label="")
                if group['id'] in current_card_groups:
                    cb.SetValue(True)
                cb_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
                cb_label = wx.StaticText(panel, label=group['name'])
                cb_label.SetForegroundColour(get_wx_color('text_primary'))
                cb_sizer.Add(cb_label, 0, wx.ALIGN_CENTER_VERTICAL)
                sizer.Add(cb_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
                group_checkboxes.append(cb)
            self._form_controls['group_checkboxes'] = group_checkboxes
        else:
            no_groups = wx.StaticText(panel, label="No groups created for this deck yet.\nUse the \"Groups...\" button in the Card Library to create groups.")
            no_groups.SetForegroundColour(get_wx_color('text_dim'))
            sizer.Add(no_groups, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Groups")

    def _build_custom_fields_tab(self, deck_custom_fields, existing_custom_values):
        """Build the Custom Fields tab"""
        panel = scrolled.ScrolledPanel(self.notebook)
        panel.SetBackgroundColour(get_wx_color('bg_primary'))
        panel.SetupScrolling(scroll_x=False)
        sizer = wx.BoxSizer(wx.VERTICAL)

        custom_field_ctrls = {}

        if deck_custom_fields:
            custom_label = wx.StaticText(panel, label="Deck Custom Fields:")
            custom_label.SetForegroundColour(get_wx_color('text_primary'))
            custom_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            sizer.Add(custom_label, 0, wx.ALL, 10)

            for field in deck_custom_fields:
                field_name = field['field_name']
                field_type = field['field_type']
                field_options = None
                if field['field_options']:
                    try:
                        field_options = json.loads(field['field_options'])
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning("Failed to parse field_options for '%s': %s", field.get('field_name', '?'), e)

                current_value = existing_custom_values.get(field_name, '')

                if field_type == 'multiline':
                    field_sizer = wx.BoxSizer(wx.VERTICAL)
                    f_label = wx.StaticText(panel, label=f"{field_name}:")
                    f_label.SetForegroundColour(get_wx_color('text_primary'))
                    field_sizer.Add(f_label, 0, wx.BOTTOM, 5)
                    ctrl = RichTextPanel(panel, value=str(current_value), min_height=120)
                    field_sizer.Add(ctrl, 0, wx.EXPAND)
                else:
                    field_sizer = wx.BoxSizer(wx.HORIZONTAL)
                    f_label = wx.StaticText(panel, label=f"{field_name}:")
                    f_label.SetForegroundColour(get_wx_color('text_primary'))
                    field_sizer.Add(f_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

                    if field_type == 'text':
                        ctrl = wx.TextCtrl(panel, value=str(current_value))
                        ctrl.SetBackgroundColour(get_wx_color('bg_input'))
                        ctrl.SetForegroundColour(get_wx_color('text_primary'))
                        field_sizer.Add(ctrl, 1)
                    elif field_type == 'number':
                        try:
                            num_val = int(current_value) if current_value else 0
                        except (ValueError, TypeError) as e:
                            logger.debug("Could not convert '%s' to number: %s", current_value, e)
                            num_val = 0
                        ctrl = wx.SpinCtrl(panel, min=-9999, max=9999, initial=num_val)
                        ctrl.SetBackgroundColour(get_wx_color('bg_input'))
                        ctrl.SetForegroundColour(get_wx_color('text_primary'))
                        field_sizer.Add(ctrl, 0)
                    elif field_type == 'select' and field_options:
                        ctrl = wx.Choice(panel, choices=[''] + field_options)
                        if current_value in field_options:
                            ctrl.SetSelection(field_options.index(current_value) + 1)
                        field_sizer.Add(ctrl, 1)
                    elif field_type == 'checkbox':
                        ctrl = wx.CheckBox(panel, label="")
                        ctrl.SetValue(bool(current_value))
                        field_sizer.Add(ctrl, 0)
                    else:
                        ctrl = wx.TextCtrl(panel, value=str(current_value))
                        ctrl.SetBackgroundColour(get_wx_color('bg_input'))
                        ctrl.SetForegroundColour(get_wx_color('text_primary'))
                        field_sizer.Add(ctrl, 1)

                custom_field_ctrls[field_name] = (ctrl, field_type)
                sizer.Add(field_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        else:
            no_fields_label = wx.StaticText(panel,
                label="No custom fields defined for this deck.\nEdit the deck to add custom fields.")
            no_fields_label.SetForegroundColour(get_wx_color('text_secondary'))
            sizer.Add(no_fields_label, 0, wx.ALL, 10)

        self._form_controls['custom_fields'] = custom_field_ctrls

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Custom Fields")

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

    def _on_browse_image(self, event):
        """Handle image browse button"""
        file_dlg = wx.FileDialog(self, wildcard="Images|*.jpg;*.jpeg;*.png;*.gif;*.webp")
        if file_dlg.ShowModal() == wx.ID_OK:
            new_path = file_dlg.GetPath()
            self._form_controls['image_path'].SetValue(new_path)
            # Update preview
            self.image_sizer.Clear(True)
            card = self._form_controls['card'].copy()
            card['image_path'] = new_path
            self._build_image_preview(card)
            self.image_panel.Layout()
        file_dlg.Destroy()

    def _on_add_tag(self, event):
        """Handle add new tag button"""
        result = self.parent._show_tag_dialog(self, "Add Card Tag")
        if result:
            try:
                new_id = self.db.add_card_tag(result['name'], result['color'])
                all_card_tags = self._form_controls['all_card_tags']
                all_card_tags.append({'id': new_id, 'name': result['name'], 'color': result['color']})
                checklist = self._form_controls['tag_checklist']
                checklist.Append(result['name'])
                checklist.Check(checklist.GetCount() - 1, True)
                self.parent._refresh_card_tags_list()
            except Exception as ex:
                wx.MessageBox(f"Could not add tag: {ex}", "Error", wx.OK | wx.ICON_ERROR)

    def _save_card_data(self):
        """Save current form data to database"""
        card_id = self.current_card_id
        card = self._form_controls['card']

        new_name = self._form_controls['name'].GetValue().strip()
        new_image = self._form_controls['image_path'].GetValue().strip() or None
        new_order = self._form_controls['card_order'].GetValue()

        # Get archetype value
        new_archetype = self._form_controls['archetype'].GetValue().strip() or None

        # Get rank value
        new_rank = None
        rank_ctrl = self._form_controls.get('rank')
        if rank_ctrl:
            if isinstance(rank_ctrl, wx.SpinCtrl):
                new_rank = str(rank_ctrl.GetValue())
            elif isinstance(rank_ctrl, wx.Choice):
                sel = rank_ctrl.GetSelection()
                if sel > 0:
                    new_rank = rank_ctrl.GetString(sel)

        # Get suit value
        new_suit = None
        suit_ctrl = self._form_controls.get('suit')
        if suit_ctrl:
            if isinstance(suit_ctrl, wx.TextCtrl):
                new_suit = suit_ctrl.GetValue().strip() or None
            elif isinstance(suit_ctrl, wx.Choice):
                sel = suit_ctrl.GetSelection()
                if sel > 0:
                    new_suit = suit_ctrl.GetString(sel)

        # Get notes
        new_notes = self._form_controls['notes'].GetValue().strip() or None

        # Get custom field values
        new_custom_fields = {}
        custom_field_ctrls = self._form_controls.get('custom_fields', {})
        for field_name, (ctrl, field_type) in custom_field_ctrls.items():
            if field_type == 'checkbox':
                new_custom_fields[field_name] = ctrl.GetValue()
            elif field_type == 'number':
                new_custom_fields[field_name] = ctrl.GetValue()
            elif field_type == 'select':
                sel = ctrl.GetSelection()
                if sel > 0:
                    new_custom_fields[field_name] = ctrl.GetString(sel)
                else:
                    new_custom_fields[field_name] = ''
            else:
                new_custom_fields[field_name] = ctrl.GetValue()

        # Add I Ching specific fields if present
        if 'iching_trad' in self._form_controls:
            new_custom_fields['traditional_chinese'] = self._form_controls['iching_trad'].GetValue()
        if 'iching_simp' in self._form_controls:
            new_custom_fields['simplified_chinese'] = self._form_controls['iching_simp'].GetValue()

        if new_name:
            # Update basic card info
            self.db.update_card(card_id, name=new_name, image_path=new_image, card_order=new_order)

            # Update metadata
            self.db.update_card_metadata(
                card_id,
                archetype=new_archetype,
                rank=new_rank,
                suit=new_suit,
                notes=new_notes,
                custom_fields=new_custom_fields if new_custom_fields else None
            )

            # Update card tags
            all_card_tags = self._form_controls.get('all_card_tags', [])
            checklist = self._form_controls.get('tag_checklist')
            if checklist:
                selected_card_tag_ids = []
                for i in range(checklist.GetCount()):
                    if checklist.IsChecked(i):
                        selected_card_tag_ids.append(all_card_tags[i]['id'])
                self.db.set_card_tags(card_id, selected_card_tag_ids)

            # Update card groups
            all_card_groups = self._form_controls.get('all_card_groups', [])
            group_checkboxes = self._form_controls.get('group_checkboxes')
            if group_checkboxes:
                selected_group_ids = []
                for i, cb in enumerate(group_checkboxes):
                    if cb.GetValue():
                        selected_group_ids.append(all_card_groups[i]['id'])
                self.db.set_card_groups(card_id, selected_group_ids)

            if new_image and new_image != card['image_path']:
                self.thumb_cache.get_thumbnail(new_image)

            return True
        return False

    def _on_prev(self, event):
        """Navigate to previous card"""
        if not self.card_ids:
            return
        try:
            current_index = self.card_ids.index(self.current_card_id)
            if current_index > 0:
                # Save current card first
                if self._save_card_data():
                    if self.on_refresh_callback:
                        self.on_refresh_callback()
                    self._load_card(self.card_ids[current_index - 1], preserve_tab=True)
        except ValueError:
            pass

    def _on_next(self, event):
        """Navigate to next card"""
        if not self.card_ids:
            return
        try:
            current_index = self.card_ids.index(self.current_card_id)
            if current_index < len(self.card_ids) - 1:
                # Save current card first
                if self._save_card_data():
                    if self.on_refresh_callback:
                        self.on_refresh_callback()
                    self._load_card(self.card_ids[current_index + 1], preserve_tab=True)
        except ValueError:
            pass

    def _on_save(self, event):
        """Handle save button click"""
        if self._save_card_data():
            self.save_requested = True
            self.EndModal(wx.ID_OK)

    def get_current_card_id(self):
        """Return the currently displayed card ID"""
        return self.current_card_id
