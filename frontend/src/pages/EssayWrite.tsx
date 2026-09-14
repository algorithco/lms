import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Essays } from '../lib/api';
import type { ApiError } from '../lib/api';
import { ClockIcon } from '../components/icons';
import {
  autosaveEssay,
  clearLocalDraft,
  countEssayWords,
  loadLocalDraft,
  saveLocalDraft,
  wordZone,
} from '../lib/essays-arena';

/**
 * Essay writing — mirrors POST /tma/api/essays/<topic_id>/start/ (JWT,
 * password gate with 403 on wrong password, 410 + submission_id when the
 * timer already expired) and POST /tma/api/essays/<id>/submit/ (JWT).
 *
 * Legacy parity (templates/essays/essay_write.html):
 * - server word-count rules (letter-bearing tokens only, min/max zone bar,
 *   submit gated on min only — over-limit is a warning, not a block)
 * - 12-mezon checklist beside the editor (crit_short_* labels)
 * - server countdown from remaining_seconds; on expiry the essay is
 *   auto-submitted once and the user lands on the result page
 * - autosave: localStorage draft (always) + best-effort POST to the
 *   session-only /essays/api/autosave/ endpoint (HTML partial, no JWT
 *   equivalent). time_limit_minutes == 0 means unlimited (no timer).
 */

interface TopicInfo {
  id?: number;
  title?: string;
  description?: string;
  word_limit_min?: number;
  word_limit_max?: number;
  time_limit_minutes?: number;
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

const CRIT_KEYS = Array.from({ length: 12 }, (_, i) => `crit_short_${i + 1}`);

function submissionIdFromError(e: unknown): number | null {
  const msg = e instanceof Error ? e.message : String(e ?? '');
  const m = msg.match(/"submission_id"\s*:\s*(\d+)/);
  return m ? Number(m[1]) : null;
}

export default function EssayWrite() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const [topic, setTopic] = useState<TopicInfo | null>(null);
  const [submissionId, setSubmissionId] = useState<number | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [text, setText] = useState('');
  const [password, setPassword] = useState('');
  const [needPassword, setNeedPassword] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [restored, setRestored] = useState(false);
  const [timeUp, setTimeUp] = useState(false);
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoSubmitDone = useRef(false);

  const words = useMemo(() => countEssayWords(text), [text]);
  const minWords = Number(topic?.word_limit_min ?? 0);
  const maxWords = Number(topic?.word_limit_max ?? 0);
  const timeLimitMin = Number(topic?.time_limit_minutes ?? 0);
  const hasLimit = timeLimitMin > 0;
  const zone = wordZone(words, minWords, maxWords);

  const start = useCallback(
    async (pw = '') => {
      setErr(null);
      try {
        const res = (await Essays.start(id, pw)) as {
          submission_id: number;
          topic: TopicInfo;
          remaining_seconds: number;
          essay_text: string;
        };
        setSubmissionId(res.submission_id);
        setTopic(res.topic);
        setRemaining(res.remaining_seconds);
        const serverText = res.essay_text ?? '';
        if (serverText) {
          setText(serverText);
          setRestored(false);
        } else {
          // Resume the local draft when the server has nothing saved yet.
          const local = loadLocalDraft(id);
          if (local) {
            setText(local);
            setRestored(true);
          } else {
            setText('');
          }
        }
        setNeedPassword(false);
        // Timer already exhausted server-side → expired state (legacy
        // redirects to the result page; we show the expired card instead so
        // the user keeps context, with a direct link to the result).
        if (
          Number(res.topic?.time_limit_minutes ?? 0) > 0 &&
          Number(res.remaining_seconds ?? 1) <= 0
        ) {
          setTimeUp(true);
        }
      } catch (e) {
        const status = (e as Partial<ApiError>).status;
        const msg = e instanceof Error ? e.message : 'Failed.';
        if (status === 410) {
          const sid = submissionIdFromError(e);
          if (sid !== null) {
            navigate(`/essays/result/${sid}`, { replace: true });
            return;
          }
          setTimeUp(true);
          setErr(msg);
          return;
        }
        // Password gate: backend answers 403 for missing/wrong password.
        if (status === 403 || String(msg).toLowerCase().includes('parol')) {
          setNeedPassword(true);
        }
        setErr(msg);
      }
    },
    [id, navigate],
  );

  useEffect(() => {
    start();
  }, [start]);

  // Server autosave (debounced, best-effort) + local draft (always).
  const queueAutosave = useCallback(
    (sid: number, value: string) => {
      saveLocalDraft(id, value);
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
      autosaveTimer.current = setTimeout(async () => {
        setSaveState('saving');
        const r = await autosaveEssay(sid, value);
        if (r.autoSubmitted) {
          clearLocalDraft(id);
          navigate(`/essays/result/${sid}`, { replace: true });
          return;
        }
        setSaveState(r.saved ? 'saved' : 'error');
      }, 2000);
    },
    [id, navigate],
  );

  useEffect(
    () => () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    },
    [],
  );

  const onChange = (value: string) => {
    if (timeUp) return;
    setText(value);
    setRestored(false);
    if (submissionId !== null) queueAutosave(submissionId, value);
    else saveLocalDraft(id, value);
  };

  const doSubmit = useCallback(
    async (sid: number, value: string): Promise<boolean> => {
      try {
        await Essays.submit(sid, value);
        return true;
      } catch {
        return false;
      }
    },
    [],
  );

  const submit = async () => {
    if (submissionId === null || busy || timeUp) return;
    if (words < minWords) return;
    if (!window.confirm(t('essay_js_confirm_ai'))) return;
    setBusy(true);
    setErr(null);
    try {
      // Flush the draft first (legacy saves, then submits).
      saveLocalDraft(id, text);
      await autosaveEssay(submissionId, text);
      const ok = await doSubmit(submissionId, text);
      if (ok) {
        clearLocalDraft(id);
        navigate(`/essays/result/${submissionId}`);
      } else {
        setErr(t('essay_js_error'));
        setBusy(false);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Submit failed.');
      setBusy(false);
    }
  };

  // Countdown (server is authoritative — expired submits are rejected with
  // 410). On expiry: lock the editor, auto-submit once, land on result.
  useEffect(() => {
    if (!hasLimit || remaining === null || remaining > 0 || timeUp) return;
    if (autoSubmitDone.current || submissionId === null) {
      setTimeUp(true);
      return;
    }
    autoSubmitDone.current = true;
    setTimeUp(true);
    (async () => {
      await doSubmit(submissionId, text);
      clearLocalDraft(id);
      navigate(`/essays/result/${submissionId}`, { replace: true });
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, hasLimit]);

  useEffect(() => {
    if (!hasLimit || remaining === null || remaining <= 0 || timeUp) return;
    const tmr = setInterval(() => setRemaining((r) => (r !== null ? r - 1 : r)), 1000);
    return () => clearInterval(tmr);
  }, [remaining === null, hasLimit, timeUp]);

  const saveNow = async () => {
    if (submissionId === null) {
      saveLocalDraft(id, text);
      setSaveState('saved');
      return;
    }
    setSaveState('saving');
    saveLocalDraft(id, text);
    const r = await autosaveEssay(submissionId, text);
    setSaveState(r.saved ? 'saved' : 'error');
  };

  const mm = remaining !== null ? Math.floor(Math.max(remaining, 0) / 60) : null;
  const ss =
    remaining !== null ? String(Math.max(remaining, 0) % 60).padStart(2, '0') : null;
  const pct = maxWords > 0 ? Math.min(100, Math.round((words / maxWords) * 100)) : 0;

  return (
    <div>
      <h1>{topic ? String(topic.title ?? t('write_essay')) : t('write_essay')}</h1>
      {err && <p className="error">{err}</p>}

      {needPassword && submissionId === null && (
        <div className="card narrow" style={{ margin: '1rem 0' }}>
          <h2>{t('essay_enter_password')}</h2>
          <p className="muted small">{t('essay_password_hint')}</p>
          <div className="form">
            <label>
              {t('password')}
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button className="btn primary" onClick={() => start(password)}>
              {t('essay_confirm_start')}
            </button>
          </div>
        </div>
      )}

      {timeUp && submissionId !== null && (
        <div className="card" style={{ margin: '1rem 0' }}>
          <strong>{t('essay_time_up')}</strong>
          <p className="muted small">{t('essay_time_up_text')}</p>
          <Link className="btn primary sm" to={`/essays/result/${submissionId}`}>
            {t('essay_view_result')}
          </Link>
        </div>
      )}

      {topic && !timeUp && (
        <>
          <div className="toolbar">
            {hasLimit && remaining !== null && (
              <span className={`timer${remaining < 300 ? ' low' : ''}`}>
                <ClockIcon size={14} className="ico" /> {mm}:{ss}
              </span>
            )}
            <span className="badge">
              {t('words')}: {words} / {minWords}+
              {maxWords > 0 ? ` (max ${maxWords})` : ''}
            </span>
            <span className="muted small">
              {saveState === 'saving' && t('essay_js_saving')}
              {saveState === 'saved' && t('essay_js_saved')}
              {saveState === 'error' && t('essay_js_save_error')}
              {saveState === 'idle' && t('essay_js_not_saved')}
            </span>
          </div>
          {restored && <p className="muted small">{t('essay_draft_restored')}</p>}
          <p className="muted">{String(topic.description ?? '')}</p>
          <div className="grid" style={{ gridTemplateColumns: '1fr' }}>
            <div className="card">
              <strong>{t('essay_12_criteria')}</strong>{' '}
              <span className="muted small">{t('essay_0_2')}</span>
              <p className="muted small">{t('essay_criteria_hint')}</p>
              <ul className="muted small" style={{ margin: '0.5rem 0', paddingLeft: '1.2rem' }}>
                {CRIT_KEYS.map((k, i) => (
                  <li key={k}>
                    {String(i + 1).padStart(2, '0')} · {t(k)}
                  </li>
                ))}
              </ul>
              <p className="muted small">{t('essay_watch_tip')}</p>
            </div>
          </div>
          <div className="form" style={{ maxWidth: '100%' }}>
            <textarea
              rows={14}
              value={text}
              onChange={(e) => onChange(e.target.value)}
              placeholder={t('essay_write_ph')}
            />
            <div className="progress" style={{ marginTop: 8 }}>
              <div
                style={{
                  width: `${pct}%`,
                  background: zone === 'ok' ? undefined : zone === 'under' ? '#F59E0B' : '#F43F5E',
                }}
              />
            </div>
            {zone === 'under' && (
              <p className="muted small">
                {t('essay_js_write_more')} {minWords - words} {t('words_suffix')}
              </p>
            )}
            {zone === 'over' && <p className="error">{t('essay_js_over_limit')}</p>}
            {zone === 'ok' && <p className="muted small">{t('essay_js_in_range')}</p>}
            <p className="muted small">{t('essay_autosave_note')}</p>
            <div className="toolbar">
              <button className="btn sm" disabled={busy} onClick={saveNow}>
                {t('essay_save_draft')}
              </button>
              <button
                className="btn primary"
                disabled={busy || words < minWords}
                onClick={submit}
              >
                {busy ? t('loading') : t('essay_submit_btn')}
              </button>
            </div>
            {words < minWords && (
              <p className="muted small">
                {t('essay_js_need_min')} ({minWords})
              </p>
            )}
            <p className="muted small">
              {t('essay_gate_prefix')} {minWords} {t('essay_gate_suffix')}
            </p>
          </div>
        </>
      )}
    </div>
  );
}
