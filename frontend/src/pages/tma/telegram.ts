/** Minimal Telegram WebApp typings + safe helpers (old tma/index.html parity + full SPA integration). */

export interface TelegramBackButton {
  show: () => void;
  hide: () => void;
  onClick: (cb: () => void) => void;
  offClick: (cb: () => void) => void;
}

export interface TelegramHaptics {
  impactOccurred: (style: 'light' | 'medium' | 'heavy') => void;
  notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
}

export interface TelegramThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
  header_bg_color?: string;
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe?: {
    user?: {
      id?: number;
      first_name?: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    start_param?: string;
    auth_date?: number;
    hash?: string;
  };
  colorScheme: 'light' | 'dark';
  themeParams?: TelegramThemeParams;
  viewportHeight: number;
  viewportStableHeight: number;
  isExpanded: boolean;
  BackButton?: TelegramBackButton;
  HapticFeedback?: TelegramHaptics;
  ready: () => void;
  expand: () => void;
  close: () => void;
  enableClosingConfirmation: () => void;
  disableClosingConfirmation: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function tg(): TelegramWebApp | null {
  try {
    return window.Telegram?.WebApp ?? null;
  } catch {
    return null;
  }
}

export function loadTelegramScript(): Promise<void> {
  if (tg()) return Promise.resolve();
  return new Promise((resolve) => {
    const s = document.createElement('script');
    s.src = 'https://telegram.org/js/telegram-web-app.js';
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => resolve();
    document.head.appendChild(s);
  });
}

/**
 * Full Telegram WebApp setup:
 * 1. Expand viewport to full available height
 * 2. Block swipe-down-to-close via enableClosingConfirmation
 * 3. Match theme colors (header & background)
 */
export function initTelegramWebApp(): TelegramWebApp | null {
  const wa = tg();
  if (!wa) return null;
  try {
    wa.ready();
    wa.expand();
    if (typeof wa.enableClosingConfirmation === 'function') {
      wa.enableClosingConfirmation();
    }
    const isDark = wa.colorScheme === 'dark';
    try {
      wa.setHeaderColor(isDark ? '#0F172A' : '#FFFFFF');
      wa.setBackgroundColor(isDark ? '#0B0F19' : '#F8FAFC');
    } catch {
      /* older clients */
    }
  } catch (err) {
    console.warn('Telegram WebApp setup non-critical notice:', err);
  }
  return wa;
}

export function hapticImpact(style: 'light' | 'heavy' = 'light'): void {
  try {
    tg()?.HapticFeedback?.impactOccurred(style);
  } catch {
    /* older clients — ignore */
  }
}

export function hapticNotify(type: 'error' | 'success' | 'warning'): void {
  try {
    tg()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    /* older clients — ignore */
  }
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}

export function countWords(text: string): number {
  const t = text.trim();
  if (!t) return 0;
  return t.split(/\s+/).filter((w) => w.length > 0).length;
}
