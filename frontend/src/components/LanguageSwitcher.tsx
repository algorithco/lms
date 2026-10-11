import { useEffect, useRef, useState } from 'react';
import { useLang, APP_LANGS } from '../i18n/LangContext';
import type { AppLang } from '../i18n/LangContext';

const LANG_LABELS: Record<AppLang, string> = {
  uz: "O'zbekcha",
  ru: 'Русский',
  en: 'English',
};

const LANG_SHORT: Record<AppLang, string> = {
  uz: 'UZ',
  ru: 'RU',
  en: 'EN',
};

/**
 * Compact segmented language switcher.
 * Desktop: [ UZ | RU | EN ]
 * Mobile: [ 🌐 UZ ▾ ] with dropdown
 */
export default function LanguageSwitcher() {
  const { lang, setLang } = useLang();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  const select = (l: AppLang) => {
    setLang(l);
    setOpen(false);
  };

  return (
    <div ref={ref} className="lang-switcher">
      {/* Desktop: segmented control */}
      <div className="lang-segmented" role="group" aria-label="Language">
        {APP_LANGS.map((l) => (
          <button
            key={l}
            type="button"
            className={`lang-btn${lang === l ? ' active' : ''}`}
            aria-pressed={lang === l}
            onClick={() => setLang(l)}
          >
            {LANG_SHORT[l]}
          </button>
        ))}
      </div>

      {/* Mobile: compact dropdown */}
      <div className="lang-dropdown">
        <button
          type="button"
          className="lang-toggle"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label="Language"
          onClick={() => setOpen((v) => !v)}
        >
          🌐 {LANG_SHORT[lang]} ▾
        </button>
        {open && (
          <ul className="lang-menu" role="listbox" aria-label="Language">
            {APP_LANGS.map((l) => (
              <li key={l}>
                <button
                  type="button"
                  role="option"
                  aria-selected={lang === l}
                  className={`lang-option${lang === l ? ' selected' : ''}`}
                  onClick={() => select(l)}
                >
                  {LANG_LABELS[l]}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}