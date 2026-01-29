# Tarot Journal - Development Notes




## Project Mission Statement: Tarot Library & Journal App

Core Purpose
A desktop application for serious tarot practitioners to catalog cartomancy decks and maintain a visual reading journal—not to automate or replace the intuitive practice of reading cards.
Primary Functions
Deck Library

Store and organize images and metadata for tarot/cartomancy decks
Robust search and filtering across individual decks or the entire collection
Intuitive, visually pleasing, easily navigable UI

Reading Journal

Log readings with card images arranged visually in their spread layout
Quick entry workflow that produces readable, attractive journal entries for later reference
Associate entries with Querent and Reader profiles

Supporting Data Structures

Spreads: Store 2D positional layouts, position meanings, and spread metadata for visual arrangement in journal entries
User Profiles: Name, birth date/time/place, gender; assignable as Querent or Reader per entry

Planned Future Features

Data visualization: Display trends and patterns across journal entries (customizable)
Export journal entries and data graphs as formatted PDFs
Export reading data in LLM-readable format for analysis
Export decks to Anki-compatible format for SRS study
Import/export for sharing decks, spreads, profiles, and entries between users
Automatic astrological chart retrieval for profiles (natal) and entries (event charts)

Explicit Non-Goals
This app does not aim to:

Replace physical card reading
Serve primarily as a tarot learning tool
Interpret readings or substitute for human intuition in cartomancy


## User Context

- **The user is not a programmer** - explain technical choices and concepts in simple, plain language
- When making changes, briefly explain *why* a particular approach was chosen, not just *what* was done
- Avoid jargon where possible; when technical terms are necessary, provide a brief explanation.
- However, if asked explicitly for a technical explanation, be willing to explain as if to an expert.

## Git Workflow

- **Always confirm with the user before pushing to GitHub** - commit changes when asked, but wait for explicit approval before running `git push`

## IMPORTANT: Frontend Architecture

**The PRIMARY frontend is Electron/React** located in `frontend/`:
- `frontend/src/` - React components, pages, and API calls
- This is the actively developed UI that the user interacts with

**The wxPython code is DEPRECATED** - do NOT modify unless the user explicitly mentions "wxPython" or "Python frontend":
- `main.py`, `main_tk.py` - Legacy Python app entry points
- `mixin_*.py` - Legacy wxPython UI mixins
- `ui_library/`, `ui_journal/`, `card_dialogs/` - Legacy wxPython UI packages

When the user asks for UI changes, **always modify the Electron/React code in `frontend/`** unless they specifically request changes to the Python version.

---

## DEPRECATED: wxPython Styling Rules (Dark Theme)

This app uses a custom dark theme. When creating UI elements:

1. **All widgets need explicit colors** - wxPython defaults assume a light background
   - Always call `SetForegroundColour(get_wx_color('text_primary'))` on text-displaying widgets
   - For buttons and inputs, also call `SetBackgroundColour(get_wx_color('bg_secondary'))`

2. **CRITICAL: wx.CheckBox and wx.RadioButton labels don't support custom colors on macOS**
   - **NEVER** use: `wx.CheckBox(parent, label="Some text")` - the label will be BLACK and unreadable
   - **NEVER** use: `wx.RadioButton(parent, label="Some text")` - the label will be BLACK and unreadable
   - `SetForegroundColour()` does NOT work on checkbox/radiobutton labels on macOS
   - **ALWAYS** use an empty-label widget with a separate StaticText:

   For CheckBox:
     ```python
     cb_sizer = wx.BoxSizer(wx.HORIZONTAL)
     cb = wx.CheckBox(parent, label="")  # Empty label!
     cb_sizer.Add(cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
     cb_label = wx.StaticText(parent, label="Your label text")
     cb_label.SetForegroundColour(get_wx_color('text_primary'))
     cb_sizer.Add(cb_label, 0, wx.ALIGN_CENTER_VERTICAL)
     ```

   For RadioButton:
     ```python
     rb_sizer = wx.BoxSizer(wx.HORIZONTAL)
     rb = wx.RadioButton(parent, label="", style=wx.RB_GROUP)  # Empty label! Add RB_GROUP for first in group
     rb_sizer.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
     rb_label = wx.StaticText(parent, label="Your label text")
     rb_label.SetForegroundColour(get_wx_color('text_primary'))
     rb_sizer.Add(rb_label, 0, wx.ALIGN_CENTER_VERTICAL)
     ```
   - This applies to ALL checkboxes and radio buttons in the app, including those in dialogs

3. **EVERY text-displaying widget MUST have SetForegroundColour called**
   - wx.StaticText - MUST call SetForegroundColour
   - wx.TextCtrl - MUST call SetForegroundColour AND SetBackgroundColour
   - wx.Button - MUST call SetForegroundColour (and often SetBackgroundColour)
   - wx.ListCtrl - Use SetTextColour (not SetForegroundColour)
   - wx.StaticBox - SetForegroundColour for the label
   - **If you create ANY widget that displays text, you MUST set its color explicitly**

4. **Common color keys:**
   - `text_primary` - main text color (white/light) - USE THIS FOR ALL TEXT
   - `text_secondary` - dimmer text
   - `text_dim` - subtle text
   - `bg_primary` - main background
   - `bg_secondary` - slightly lighter background (for inputs, buttons)
   - `bg_input` - input field background
   - `accent` - accent color for highlights

5. **Before finishing any UI code, mentally check:**
   - Did I set foreground color on ALL StaticText widgets?
   - Did I use empty labels for ALL CheckBox and RadioButton widgets?
   - Did I set colors on ALL buttons?
   - Will ANY text appear black on the dark background?
