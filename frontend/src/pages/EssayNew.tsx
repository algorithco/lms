import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AutoGrow from '../components/AutoGrow';
import LimitExceededModal from '../components/LimitExceededModal';
import { useLang } from '../i18n/LangContext';
import { Essays, type ApiError } from '../lib/api';
import { revealOnFocus } from '../lib/useVisualViewport';

const MIN_WORDS = 50; // the server's minimum for an essay without a topic
const DRAFT_KEY = 'essay-new-draft';

const countWords = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

/** Own-topic Ona tili essay: title + text, kept locally while typing, graded on the 12 criteria. */
export default function EssayNew() {
  const { t } = useLang();
  const navigate = useNavigate();
  const [title, setTitle] = useState(() => readDraft().title);
  const [text, setText] = useState(() => readDraft().text);
  const [saved, setSaved] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [limitOpen, setLimitOpen] = useState(false);
  const words = useMemo(() => countWords(text), [text]);

  // Local draft (debounced), so a reload or a closed tab loses nothing.
  useEffect(() => {
    setSaved(false);
    const id = window.setTimeout(() => {
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify({ title, text }));
        setSaved(true);
      } catch {
        /* storage unavailable: the leave warning still protects the text */
      }
    }, 600);
    return () => window.clearTimeout(id);
  }, [title, text]);

  useEffect(() => {
    if (!text.trim() || busy) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [text, busy]);

  const submit = async () => {
    if (title.trim().length < 3) {
      setErr(t('en_err_title'));
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const res = await Essays.custom(title.trim(), text);
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch {
        /* ignore */
      }
      navigate(`/essays/result/${res.submission_id}`, { replace: true });
    } catch (e) {
      const ae = e as ApiError;
      if (ae.status === 403) setLimitOpen(true);
      else setErr(ae.code === 'too_short' ? t('en_err_short').replace('{n}', String(MIN_WORDS)) : ae.message || t('essay_js_error'));
      setBusy(false);
    }
  };

  const zone = words < MIN_WORDS ? 'under' : 'ok';

  return (
    <div className="ew">
      <header className="ew-head">
        <h1>{t('es_new')}</h1>
      </header>
      <p className="ew-note">{t('en_hint')}</p>
      {err && (
        <p className="ew-alert" role="alert">
          {err}
        </p>
      )}
      <label className="ew-label" htmlFor="en-title">
        {t('en_title')}
      </label>
      <input
        id="en-title"
        className="ew-field"
        value={title}
        maxLength={200}
        onChange={(e) => setTitle(e.target.value)}
        onFocus={revealOnFocus}
        autoCapitalize="sentences"
        enterKeyHint="next"
      />
      <AutoGrow
        className="ew-text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={revealOnFocus}
        placeholder={t('essay_write_ph')}
        aria-label={t('cd_writing_area')}
        rows={12}
        autoCapitalize="sentences"
        spellCheck
      />
      <div className="ew-bar">
        <div className="ew-bar__info">
          <span className={`ew-count is-${zone}`} aria-live="polite">
            {words} {t('cd_words')} · {t('en_min').replace('{n}', String(MIN_WORDS))}
          </span>
          <span className={`ew-save${saved ? ' is-saved' : ''}`}>{saved ? t('ew_saved') : t('essay_js_saving')}</span>
        </div>
        <button className="ui-btn ui-btn--primary" disabled={busy || words < MIN_WORDS} onClick={() => void submit()}>
          {busy ? t('loading') : t('ew_submit')}
        </button>
      </div>
      <LimitExceededModal isOpen={limitOpen} onClose={() => setLimitOpen(false)} message={t('paywall_reason_essay')} feature="essay" subject="uzbek" />
    </div>
  );
}

function readDraft(): { title: string; text: string } {
  try {
    const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}') as { title?: string; text?: string };
    return { title: d.title || '', text: d.text || '' };
  } catch {
    return { title: '', text: '' };
  }
}
