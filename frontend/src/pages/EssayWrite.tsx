import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import AutoGrow from '../components/AutoGrow';
import LimitExceededModal from '../components/LimitExceededModal';
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
  subject?: string;
  rubric_type?: string;
  task_type?: string;
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
  const [startedTopicId, setStartedTopicId] = useState<number | string | null>(null);
  const [limitModalOpen, setLimitModalOpen] = useState(false);
  const [limitModalMsg, setLimitModalMsg] = useState<string | undefined>();
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoSubmitDone = useRef(false);

  const words = useMemo(() => countEssayWords(text), [text]);
  const isEnglish = topic?.subject === 'english' || topic?.rubric_type?.startsWith('ielts');
  const isTask1 = topic?.rubric_type === 'ielts_task1' || topic?.task_type === 'task1';
  const defaultMin = isEnglish ? (isTask1 ? 150 : 250) : 200;
  const defaultMax = isEnglish ? (isTask1 ? 300 : 500) : 500;
  const minWords = Number(topic?.word_limit_min ?? defaultMin) || defaultMin;
  const maxWords = Number(topic?.word_limit_max ?? defaultMax) || defaultMax;
  const timeLimitMin = Number(topic?.time_limit_minutes ?? 0);
  const hasLimit = timeLimitMin > 0;
  const zone = wordZone(words, minWords, maxWords);

  const start = useCallback(
    async (topicId: number | string, pw = '', showPasswordError = true) => {
      setErr(null);
      setStartedTopicId(topicId);
      try {
        const res = (await Essays.start(topicId, pw)) as {
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
          const local = loadLocalDraft(String(topicId));
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
          // A protected topic legitimately returns 403 on the initial start
          // request when no password has been submitted yet. Keep the gate
          // visible, but only show the error after an actual user attempt.
          if (showPasswordError) setErr(msg);
          return;
        }
        setErr(msg);
      }
    },
    [navigate],
  );

  useEffect(() => {
    // The URL param `id` can be either a topic_id (from topics page) or a
    // submission_id (direct link / notification). We first fetch the user's
    // submissions to see if `id` matches a submission_id. If so, we use its
    // topic_id to start/resume. Otherwise we treat `id` as a topic_id.
    let cancelled = false;
    (async () => {
      try {
        const subsRes = (await Essays.submissions()) as {
          submissions?: Array<{ id: number; topic_id?: number | null }>;
        };
        const submissions = subsRes.submissions ?? [];
        const asSubmission = submissions.find((s) => String(s.id) === String(id));
        const topicIdToStart = asSubmission?.topic_id ?? id;
        if (!cancelled) {
          // Initialize unprotected topics and discover protected topics. The
          // second argument suppresses the expected initial missing-password 403.
          await start(topicIdToStart, '', false);
        }
      } catch {
        if (!cancelled) {
          // Fallback: treat `id` as topic_id directly.
          await start(id, '', false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [id, start]);

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
    async (sid: number, value: string, autoSubmit = false): Promise<{ ok: boolean; error?: string }> => {
      try {
        await Essays.submit(sid, value, autoSubmit);
        return { ok: true };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : undefined };
      }
    },
    [],
  );

  const submit = async () => {
    if (submissionId === null || busy || timeUp) return;
    if (words < 60) {
      setErr(`⚠️ Esse juda qisqa (kamida 60 ta so'z bo'lishi shart). Hozirgi so'zlar soni: ${words} ta.`);
      return;
    }
    if (words < minWords) return;

    // Instant client pre-validation check
    const hasCharRepeat = /([a-zA-Zа-яА-ЯёЁ0-9])\1{4,}/.test(text);
    const hasLongWord = text.split(/\s+/).some((w) => w.replace(/['-]/g, '').length > 35);
    const hasSmash = /(?:asdf|qwer|zxcv|asdasd|jkl;|ghjk|qwerty|tyui|dfgh|12345){2,}/i.test(text);
    if (hasCharRepeat || hasLongWord || hasSmash) {
      setErr('⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting.');
      return;
    }

    if (!window.confirm(t('essay_js_confirm_ai'))) return;
    setBusy(true);
    setErr(null);
    try {
      // Flush the draft first (legacy saves, then submits).
      saveLocalDraft(id, text);
      await autosaveEssay(submissionId, text);
      const res = await doSubmit(submissionId, text);
      if (res.ok) {
        clearLocalDraft(id);
        navigate(`/essays/result/${submissionId}`);
      } else {
        const errorText = res.error || t('essay_js_error');
        if (
          errorText.includes('LIMIT_EXCEEDED') ||
          errorText.includes('limitingiz tugadi') ||
          errorText.includes('Bepul sinov') ||
          errorText.includes('Kvotangiz tugadi')
        ) {
          setLimitModalMsg(t('paywall_reason_essay'));
          setLimitModalOpen(true);
        } else {
          setErr(errorText);
        }
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
      await doSubmit(submissionId, text, true);
      clearLocalDraft(id);
      navigate(`/essays/result/${submissionId}`, { replace: true });
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, hasLimit]);

  useEffect(() => {
    if (!hasLimit || timeUp) return;
    const tmr = setInterval(() => {
      setRemaining((r) => {
        if (r === null || r <= 0) return r;
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(tmr);
  }, [hasLimit, timeUp]);

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

  useEffect(() => {
    if (!topic || timeUp || busy || !text.trim() || saveState === 'saved') return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [topic, timeUp, busy, text, saveState]);

  const mm = remaining !== null ? Math.floor(Math.max(remaining, 0) / 60) : null;
  const ss =
    remaining !== null ? String(Math.max(remaining, 0) % 60).padStart(2, '0') : null;
  const saveLabel =
    saveState === 'saving'
      ? t('essay_js_saving')
      : saveState === 'saved'
        ? t('ew_saved')
        : saveState === 'error'
          ? t('essay_js_save_error')
          : t('essay_js_not_saved');

  return (
    <div className="ew">
      <header className="ew-head">
        <h1 className="clamp-2">{topic ? String(topic.title ?? t('write_essay')) : t('write_essay')}</h1>
        {topic && hasLimit && remaining !== null && !timeUp && (
          <span className={`ew-timer${remaining < 300 ? ' is-low' : ''}`} aria-label={t('ew_time_left')}>
            <ClockIcon size={14} /> {mm}:{ss}
          </span>
        )}
      </header>

      {err && (
        <p className="ew-alert" role="alert">
          {err}
        </p>
      )}

      {needPassword && submissionId === null && (
        <div className="ui-card ew-gate">
          <h2>{t('essay_enter_password')}</h2>
          <p>{t('essay_password_hint')}</p>
          <input
            type="password"
            className="ui-input"
            aria-label={t('password')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button className="ui-btn ui-btn--primary" onClick={() => void start(startedTopicId ?? id, password, true)}>
            {t('essay_confirm_start')}
          </button>
        </div>
      )}

      {timeUp && submissionId !== null && (
        <div className="ui-state">
          <h3>{t('essay_time_up')}</h3>
          <p>{t('essay_time_up_text')}</p>
          <Link className="ui-btn ui-btn--primary" to={`/essays/result/${submissionId}`}>
            {t('essay_view_result')}
          </Link>
        </div>
      )}

      {topic && !timeUp && (
        <>
          <details className="ui-card ew-task">
            <summary>{t('ew_task')}</summary>
            {String(topic.description ?? '') && <p className="ew-task__text">{String(topic.description ?? '')}</p>}
            <p className="ew-task__rule">{t('ew_range').replace('{range}', `${minWords}–${maxWords}`)}</p>
            {isEnglish ? (
              <p className="ew-task__crit">{t(isTask1 ? 'ew_criteria_ielts_t1' : 'ew_criteria_ielts_t2')}</p>
            ) : (
              <ol className="ew-task__list">
                {CRIT_KEYS.map((k) => (
                  <li key={k}>{t(k)}</li>
                ))}
              </ol>
            )}
          </details>
          {restored && <p className="ew-note">{t('essay_draft_restored')}</p>}

          <AutoGrow
            className="ew-text"
            value={text}
            onChange={(e) => onChange(e.target.value)}
            placeholder={t('essay_write_ph')}
            aria-label={t('cd_writing_area')}
            rows={12}
            autoCapitalize="sentences"
            spellCheck
          />

          <div className="ew-bar">
            <div className="ew-bar__info">
              <span className={`ew-count is-${zone}`} aria-live="polite">
                {words} / {minWords}–{maxWords} {t('cd_words')}
              </span>
              <span className={`ew-save is-${saveState}`}>{saveLabel}</span>
            </div>
            <button className="ui-btn ui-btn--sm" disabled={busy} onClick={saveNow}>
              {t('essay_save_draft')}
            </button>
            <button className="ui-btn ui-btn--primary" disabled={busy || words < minWords} onClick={submit}>
              {busy ? t('loading') : t('ew_submit')}
            </button>
          </div>
        </>
      )}
      <LimitExceededModal
        isOpen={limitModalOpen}
        onClose={() => setLimitModalOpen(false)}
        message={limitModalMsg}
        feature="essay"
        subject={isEnglish ? 'english' : 'uzbek'}
      />
    </div>
  );
}
