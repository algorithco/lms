import { useEffect, useState } from 'react';

/**
 * Keeps `--vvh` (visual viewport height, px) up to date while `active`, so sheets and
 * exam screens can size to the area above the on-screen keyboard instead of being
 * covered by it. CSS reads it as `var(--vvh, 100dvh)`.
 */
export function useVisualViewport(active: boolean): void {
  useEffect(() => {
    if (!active || typeof window === 'undefined' || !window.visualViewport) return;
    const vv = window.visualViewport;
    const root = document.documentElement;
    const update = () => root.style.setProperty('--vvh', `${Math.round(vv.height)}px`);
    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
      root.style.removeProperty('--vvh');
    };
  }, [active]);
}

/** Scroll a focused field into view once the keyboard has opened (the sheet shrinks first). */
export function revealOnFocus(e: React.FocusEvent<HTMLElement>): void {
  const el = e.currentTarget;
  window.setTimeout(() => el.scrollIntoView({ block: 'center', behavior: 'smooth' }), 250);
}

/** True while the on-screen keyboard covers a large part of the screen and a field has focus. */
export function useKeyboardOpen(): boolean {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const check = () => {
      const tag = document.activeElement?.tagName ?? '';
      setOpen(window.innerHeight - vv.height > 140 && /^(INPUT|TEXTAREA|SELECT)$/.test(tag));
    };
    const later = () => window.setTimeout(check, 60);
    vv.addEventListener('resize', check);
    document.addEventListener('focusin', check);
    document.addEventListener('focusout', later);
    return () => {
      vv.removeEventListener('resize', check);
      document.removeEventListener('focusin', check);
      document.removeEventListener('focusout', later);
    };
  }, []);
  return open;
}

/** Narrow screens (phones, portrait tablets): one pane at a time. */
export function useIsNarrow(query = '(max-width: 767px)'): boolean {
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [query]);
  return narrow;
}
