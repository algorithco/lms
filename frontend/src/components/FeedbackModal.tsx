import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { FeedbackApi, type ApiError, type FeedbackPayload } from '../lib/api';
import { buildFeedbackContext } from '../lib/feedbackContext';

type Category = FeedbackPayload['category'];

const CATEGORIES: { id: Category; key: string }[] = [
  { id: 'feedback', key: 'feedback_cat_feedback' },
  { id: 'suggestion', key: 'feedback_cat_suggestion' },
  { id: 'bug', key: 'feedback_cat_bug' },
  { id: 'praise', key: 'feedback_cat_praise' },
];
const MAX = 2000;

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Where the form was opened from (e.g. "result"); stored in the context. */
  source?: string;
}

export default function FeedbackModal({ isOpen, onClose, source }: FeedbackModalProps) {
  const { user } = useAuth();
  const { t, lang } = useLang();
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [category, setCategory] = useState<Category>('feedback');
  const [message, setMessage] = useState('');
  const [name, setName] = useState('');
  const [consent, setConsent] = useState(false);
  const [trap, setTrap] = useState(''); // honeypot: real users never see it
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setRating(0);
    setHover(0);
    setCategory('feedback');
    setMessage('');
    setName('');
    setConsent(false);
    setDone(false);
    setError(null);
  }, []);

  // Escape closes; Tab stays inside; focus returns to where it was.
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>('[role=radio]')?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !dialogRef.current) return;
      const items = [...dialogRef.current.querySelectorAll<HTMLElement>('button, input, textarea, [tabindex="0"]')].filter(
        (el) => !el.hasAttribute('disabled') && el.offsetParent !== null,
      );
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous?.focus?.();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const shown = hover || rating;
  const displayName = user ? user.full_name || '' : name.trim();
  const canConsent = Boolean(displayName) && (rating >= 4 || category === 'praise');

  const onStarKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
      e.preventDefault();
      setRating((r) => Math.min(5, r + 1));
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
      e.preventDefault();
      setRating((r) => Math.max(1, r - 1));
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rating) return setError(t('feedback_err_rating'));
    if (message.trim().length < 3) return setError(t('feedback_err_short'));
    setSubmitting(true);
    setError(null);
    try {
      await FeedbackApi.submit({
        rating,
        category,
        message: message.trim(),
        name: user ? undefined : name.trim() || undefined,
        consent_public: canConsent && consent,
        website: trap,
        context: { ...buildFeedbackContext({ category, lang, source }) },
      });
      setDone(true);
    } catch (err) {
      const e2 = err as ApiError;
      setError(e2.status === 429 ? t('feedback_err_limit') : t('feedback_err_failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const close = () => {
    onClose();
    // keep the success screen visible until the dialog is gone
    window.setTimeout(reset, 200);
  };

  return (
    <div className="fb-backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div ref={dialogRef} className="fb-dialog card" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        {done ? (
          <div className="fb-done">
            <h2 id={titleId}>{t('feedback_thanks_title')}</h2>
            <p className="muted">{t('feedback_thanks_text')}</p>
            <button type="button" className="btn primary" onClick={close}>
              {t('feedback_close')}
            </button>
          </div>
        ) : (
          <form onSubmit={submit} noValidate>
            <h2 id={titleId}>{t('feedback_title')}</h2>

            <div className="fb-field">
              <span className="fb-label" id={`${titleId}-r`}>{t('feedback_rating')}</span>
              <div className="fb-stars" role="radiogroup" aria-labelledby={`${titleId}-r`} onKeyDown={onStarKey}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    role="radio"
                    aria-checked={rating === n}
                    aria-label={`${n} / 5`}
                    tabIndex={rating === n || (!rating && n === 1) ? 0 : -1}
                    className={`fb-star${n <= shown ? ' on' : ''}`}
                    onMouseEnter={() => setHover(n)}
                    onMouseLeave={() => setHover(0)}
                    onClick={() => setRating(n)}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>

            <div className="fb-field">
              <span className="fb-label" id={`${titleId}-c`}>{t('feedback_category')}</span>
              <div className="fb-chips" role="radiogroup" aria-labelledby={`${titleId}-c`}>
                {CATEGORIES.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    role="radio"
                    aria-checked={category === c.id}
                    className={`fb-chip${category === c.id ? ' on' : ''}`}
                    onClick={() => setCategory(c.id)}
                  >
                    {t(c.key)}
                  </button>
                ))}
              </div>
            </div>

            {!user && (
              <div className="fb-field">
                <label className="fb-label" htmlFor={`${titleId}-n`}>{t('feedback_name')}</label>
                <input id={`${titleId}-n`} className="fb-input" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
              </div>
            )}

            <div className="fb-field">
              <label className="fb-label" htmlFor={`${titleId}-m`}>{t('feedback_message')}</label>
              <textarea
                id={`${titleId}-m`}
                className="fb-input"
                rows={5}
                maxLength={MAX}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={t(category === 'bug' ? 'feedback_ph_bug' : 'feedback_ph')}
              />
              <span className={`fb-count${message.length > MAX - 100 ? ' warn' : ''}`}>
                {message.length} / {MAX}
              </span>
            </div>

            {/* honeypot */}
            <input
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
              className="fb-trap"
              name="website"
              value={trap}
              onChange={(e) => setTrap(e.target.value)}
            />

            {canConsent && (
              <label className="fb-consent">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                <span>{t('feedback_consent').replace('{name}', shortName(displayName))}</span>
              </label>
            )}

            {category === 'bug' && <p className="muted small">{t('feedback_bug_hint')}</p>}
            {error && (
              <p className="fb-error" role="alert">
                {error}
              </p>
            )}

            <div className="fb-actions">
              <button type="button" className="btn ghost" onClick={close}>
                {t('feedback_cancel')}
              </button>
              <button type="submit" className="btn primary" disabled={submitting}>
                {submitting ? t('feedback_sending') : t('feedback_send')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

/** "Komiljon Roziyev" → "Komiljon R." (same rule as the server). */
function shortName(full: string): string {
  const [first = '', second = ''] = full.trim().split(/\s+/);
  const f = first.charAt(0).toUpperCase() + first.slice(1).toLowerCase();
  return second ? `${f} ${second.charAt(0).toUpperCase()}.` : f;
}
