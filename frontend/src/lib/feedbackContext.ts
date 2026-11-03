/**
 * Context attached to a feedback message. Only page, subject, language,
 * device class and browser are collected here; role and plan are added by the
 * server. The last frontend error is kept in memory (never persisted) and is
 * sent only when the user reports a bug. No tokens, passwords or form values.
 */

let lastError = '';
let installed = false;

const short = (value: unknown, max = 280) => String(value ?? '').replace(/\s+/g, ' ').slice(0, max);

/** Call once at startup. */
export function installErrorCapture(): void {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  window.addEventListener('error', (e) => {
    lastError = short(e.message);
  });
  window.addEventListener('unhandledrejection', (e) => {
    const reason = e.reason as { message?: string } | string | undefined;
    lastError = short(typeof reason === 'string' ? reason : reason?.message);
  });
}

export interface FeedbackContext {
  path: string;
  subject: string;
  lang: string;
  device: 'mobile' | 'desktop';
  browser: string;
  source?: string;
  last_error?: string;
}

export function buildFeedbackContext(opts: { category: string; lang: string; subject?: string; source?: string }): FeedbackContext {
  let subject = opts.subject || '';
  if (!subject) {
    try {
      subject = localStorage.getItem('lms_subject') || '';
    } catch {
      /* storage can be unavailable; the subject is optional */
    }
  }
  const ctx: FeedbackContext = {
    path: window.location.pathname,
    subject: subject || 'uzbek',
    lang: opts.lang,
    device: window.matchMedia('(max-width: 767px)').matches ? 'mobile' : 'desktop',
    browser: short(navigator.userAgent, 120),
  };
  if (opts.source) ctx.source = opts.source;
  if (opts.category === 'bug' && lastError) ctx.last_error = lastError;
  return ctx;
}
