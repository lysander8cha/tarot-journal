import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { getTheme } from '../api/settings';
import type { Theme } from '../types';

/** Defaults until the saved theme loads. Only fonts.size_body is
 *  applied (as --tj-scale); colours are a fixed design in CSS. */
const DEFAULT_THEME: Theme = {
  fonts: {
    family_display: 'SF Pro Display',
    family_text: 'SF Pro Text',
    family_mono: 'SF Mono',
    size_title: 22,
    size_heading: 14,
    size_body: 13,
    size_small: 11,
  },
};

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: DEFAULT_THEME,
  setTheme: () => {},
});

/** Injects the user's TEXT SIZE as one scale factor on <html>.
 *
 * Colors and font families are no longer injected: the app's look is
 * the Nocturne token system (styles/nocturne.css + tokens.css), a
 * fixed design. Every type token multiplies --tj-scale, so the Text
 * Size setting scales the whole interface uniformly — injecting
 * per-role pixel sizes (the old way) put ported and legacy styles on
 * two different scales and broke layouts. size_body 13 = 100%. */
function applyThemeToDom(theme: Theme) {
  const root = document.documentElement;
  root.style.setProperty('--tj-scale', String(theme.fonts.size_body / 13));
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME);
  const loaded = useRef(false);

  // Load saved theme from API on startup
  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    getTheme()
      .then((saved) => setTheme({ ...saved, fonts: { ...DEFAULT_THEME.fonts, ...saved.fonts } }))
      .catch(() => {}); // Fall back to defaults silently
  }, []);

  // Apply to DOM whenever theme changes
  useEffect(() => {
    applyThemeToDom(theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
