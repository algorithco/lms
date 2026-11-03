import { useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { FeedbackApi } from '../lib/api';
import { buildFeedbackContext } from '../lib/feedbackContext';

const LAST_KEY = 'fb_prompt_last';
const SNOOZE_KEY = 'fb_prompt_snooze_until';
const DAY = 24 * 60 * 60 * 1000;

const read = (key: string): number => {
  try {
    return Number(localStorage.getItem(key)) || 0;
  } catch {
    return 0;
  }
};
const write = (key: string, value: number) => {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    /* private mode: the prompt may simply show again */
  }
};

/**
 * One-tap "How was this test?" after a result. At most once a day; "Later"
 * silences it for 7 days. A star submits immediately.
 */
export default function FeedbackPrompt() {
  const { t, lang } = useLang();
  const now = Date.now();
  const [visible, setVisible] = useState(() => read(SNOOZE_KEY) < now && now - read(LAST_KEY) > DAY);
  const [sent, setSent] = useState(false);

  if (!visible) return null;

  const rate = async (n: number) => {
    write(LAST_KEY, Date.now());
    try {
      await FeedbackApi.submit({
        rating: n,
        category: 'feedback',
        message: t('feedback_quick_message').replace('{n}', String(n)),
        context: { ...buildFeedbackContext({ category: 'feedback', lang, source: 'result' }) },
      });
    } catch {
      /* a failed quick rating is not worth interrupting the result page */
    }
    setSent(true);
  };

  const later = () => {
    write(SNOOZE_KEY, Date.now() + 7 * DAY);
    setVisible(false);
  };

  return (
    <div className="card fb-prompt" role="group" aria-label={t('feedback_prompt_q')}>
      {sent ? (
        <p>{t('feedback_thanks_title')}</p>
      ) : (
        <>
          <strong>{t('feedback_prompt_q')}</strong>
          <div className="fb-stars">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" className="fb-star" aria-label={`${n} / 5`} onClick={() => rate(n)}>
                ★
              </button>
            ))}
          </div>
          <button type="button" className="btn ghost sm" onClick={later}>
            {t('feedback_prompt_later')}
          </button>
        </>
      )}
    </div>
  );
}
