import { useEffect } from 'react';

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
