/** Minimal Telegram WebApp typings + safe helpers (old tma/index.html parity). */

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

export interface TelegramWebApp {
  initData: string;
  colorScheme: 'light' | 'dark';
  BackButton?: TelegramBackButton;
  HapticFeedback?: TelegramHaptics;
  ready: () => void;
  expand: () => void;
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
