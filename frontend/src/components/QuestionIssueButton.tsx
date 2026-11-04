import { useEffect, useId, useRef, useState } from 'react';
import { Flag } from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import { FeedbackApi, type ApiError } from '../lib/api';
import { givenAnswer, type ReviewQuestion } from '../lib/review';
import { revealOnFocus, useVisualViewport } from '../lib/useVisualViewport';

const REASONS = ['wrong_key', 'unclear', 'media', 'other'] as const;
type Reason = (typeof REASONS)[number];
const MAX = 500;

interface Props {
  testId?: number;
  question: ReviewQuestion;
}

/** "Problem with this question?" — step 1: pick a reason, step 2: optional note, send. */
export default function QuestionIssueButton({ question }: Props) {
  const { t } = useLang();
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [reason, setReason] = useState<Reason | null>(null);
  const [comment, setComment] = useState('');
  const [withAnswer, setWithAnswer] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useVisualViewport(open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('keydown', onKey);
    dialogRef.current?.querySelector<HTMLElement>('button')?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [open, step]);

  const given = givenAnswer(question);

  const submit = async () => {
    if (!reason) return;
    if (reason === 'other' && comment.trim().length < 3) {
      setError(t('qi_err_comment'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await FeedbackApi.questionIssue({
        question_id: question.question_id,
        reason,
        comment: comment.trim() || undefined,
        given: withAnswer && given ? given : undefined,
      });
      setSent(true);
      setOpen(false);
    } catch (e) {
      setError((e as ApiError).status === 429 ? t('qi_err_limit') : t('qi_err_failed'));
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <span className="qi-sent" role="status">
        {t('qi_sent')}
      </span>
    );
  }

  return (
    <>
      <button type="button" className="qi-btn" onClick={() => { setOpen(true); setStep(1); setError(null); }}>
        <Flag size={14} aria-hidden="true" />
        {t('rv_report_issue')}
      </button>

      {open && (
        <div className="sheet-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
          <div ref={dialogRef} className="sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
            <div className="sheet__grip" aria-hidden="true" />
            <h2 id={titleId} className="sheet__title">
              {t('rv_report_issue')} <small>{question.number ? `№${question.number}` : ''}</small>
            </h2>

            {step === 1 ? (
              <div className="sheet__body">
                <p className="sheet__hint">{t('qi_step1')}</p>
                <div className="sheet__chips" role="radiogroup" aria-label={t('qi_step1')}>
                  {REASONS.map((r) => (
                    <button
                      key={r}
                      type="button"
                      role="radio"
                      aria-checked={reason === r}
                      className={`sheet__chip${reason === r ? ' on' : ''}`}
                      onClick={() => {
                        setReason(r);
                        setStep(2);
                      }}
                    >
                      {t(`qi_reason_${r}`)}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="sheet__body">
                <p className="sheet__hint">
                  <b>{reason && t(`qi_reason_${reason}`)}</b>
                </p>
                <label className="sheet__label" htmlFor={`${titleId}-c`}>
                  {reason === 'other' ? t('qi_comment_required') : t('qi_comment_optional')}
                </label>
                <textarea
                  id={`${titleId}-c`}
                  className="ui-input sheet__textarea"
                  rows={4}
                  maxLength={MAX}
                  value={comment}
                  onFocus={revealOnFocus}
                  onChange={(e) => setComment(e.target.value)}
                  autoCapitalize="sentences"
                />
                {given && (
                  <label className="sheet__check">
                    <input type="checkbox" checked={withAnswer} onChange={(e) => setWithAnswer(e.target.checked)} />
                    <span>{t('qi_with_answer')}</span>
                  </label>
                )}
                {error && (
                  <p className="sheet__error" role="alert">
                    {error}
                  </p>
                )}
                <div className="sheet__actions">
                  <button type="button" className="ui-btn" onClick={() => setStep(1)} disabled={busy}>
                    {t('qi_back')}
                  </button>
                  <button type="button" className="ui-btn ui-btn--primary" onClick={() => void submit()} disabled={busy}>
                    {busy ? t('feedback_sending') : t('feedback_send')}
                  </button>
                </div>
              </div>
            )}

            {step === 1 && (
              <div className="sheet__actions">
                <button type="button" className="ui-btn" onClick={() => setOpen(false)}>
                  {t('feedback_cancel')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
