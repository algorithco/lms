import { useEffect, useRef, useState } from 'react';
import { translate, useLang } from '../../i18n/LangContext';
import { TmaApi, tmaErrorMessage } from './api';
import type { TmaEssayResult, TmaEssayStart, TmaEssayTopic } from './api';
import { countWords, formatClock, hapticNotify } from './telegram';

type View = 'topics' | 'write' | 'result';

export default function Essays({
  setBackHandler,
}: {
  setBackHandler: (fn: (() => void) | null) => void;
}) {
  const { t } = useLang();
  const [view, setView] = useState<View>('topics');
  const [topics, setTopics] = useState<TmaEssayTopic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [passwordFor, setPasswordFor] = useState<number | null>(null);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<TmaEssayStart | null>(null);
  const [text, setText] = useState('');
  const [remaining, setRemaining] = useState(0);
  const [result, setResult] = useState<TmaEssayResult | null>(null);
  const [grading, setGrading] = useState(false);
  const timerRef = useRef<number | null>(null);
  const pollRef = useRef<number | null>(null);
  const textRef = useRef('');
  textRef.current = text;

  const stopTimers = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopTimers, []);

  const loadTopics = async () => {
    setError(null);
    try {
      const data = await TmaApi.essayTopics();
      setTopics(data.topics ?? []);
    } catch (e) {
      setError(tmaErrorMessage(e, t('tma_loading_error')));
    }
  };

  useEffect(() => {
    void loadTopics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exitToTopics = () => {
    stopTimers();
    setSession(null);
    setResult(null);
    setText('');
    setPassword('');
    setPasswordFor(null);
    setView('topics');
    void loadTopics();
  };

  useEffect(() => {
    if (view === 'write') {
      setBackHandler(() => {
        if (window.confirm(t('tma_exit_essay'))) exitToTopics();
      });
    } else {
      setBackHandler(null);
    }
    return () => setBackHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  const openTopic = (topic: TmaEssayTopic) => {
    setError(null);
    if (topic.has_password) {
      setPasswordFor(topic.id);
      setPassword('');
    } else {
      void begin(topic.id, undefined);
    }
  };

  const begin = async (topicId: number, pw: string | undefined) => {
    setBusy(true);
    setError(null);
    try {
      const data = await TmaApi.essayStart(topicId, pw);
      setSession(data);
      setText(data.essay_text || '');
      setRemaining(data.remaining_seconds ?? data.topic.time_limit_minutes * 60);
      setPasswordFor(null);
      setPassword('');
      setView('write');
      stopTimers();
      timerRef.current = window.setInterval(() => {
        setRemaining((prev) => {
          if (prev <= 1) {
            stopTimers();
            hapticNotify('warning');
            void submitEssay();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } catch (e) {
      setError(tmaErrorMessage(e, t('tma_loading_error')));
    } finally {
      setBusy(false);
    }
  };

  const submitEssay = async () => {
    if (!session) return;
    const value = textRef.current.trim();
    if (!value) {
      setError(t('tma_empty_essay'));
      return;
    }
    stopTimers();
    setBusy(true);
    setError(null);
    try {
      const res = await TmaApi.essaySubmit(session.submission_id, value);
      if (res.status === 'graded') {
        const full = await TmaApi.essayResult(session.submission_id);
        setResult(full);
      } else {
        setGrading(true);
        const full = await TmaApi.essayResult(session.submission_id);
        setResult(full);
        if (full.status === 'pending') {
          const every = (full.poll_after ?? 3) * 1000;
          pollRef.current = window.setInterval(() => void refreshResult(session.submission_id), every);
        } else {
          setGrading(false);
        }
      }
      setView('result');
    } catch (e) {
      setError(tmaErrorMessage(e, t('tma_loading_error')));
    } finally {
      setBusy(false);
    }
  };

  const refreshResult = async (submissionId: number) => {
    try {
      const full = await TmaApi.essayResult(submissionId);
      setResult(full);
      if (full.status !== 'pending') {
        setGrading(false);
        if (pollRef.current !== null) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
        hapticNotify('success');
      }
    } catch {
      /* keep polling */
    }
  };

  if (view === 'result' && result) {
    const score = result.total_score ?? 0;
    return (
      <div className="tma-slide">
        <h2 style={{ fontSize: 18, fontWeight: 800, margin: '0 0 16px' }}>{result.topic_title}</h2>
        {grading || result.status === 'pending' ? (
          <div className="tma-center" style={{ padding: '24px 0' }}>
            <div className="tma-spin" />
            <p className="tma-muted">{t('tma_grading')}</p>
          </div>
        ) : (
          <div className="tma-card" style={{ marginBottom: 16 }}>
            <div className="tma-center" style={{ marginBottom: 12 }}>
              <p style={{ fontSize: 36, fontWeight: 800, margin: 0, color: 'var(--tma-hl)' }}>{score}</p>
              <p className="tma-sub">
                / {result.max_score ?? 24}
                {typeof result.score_percentage === 'number' ? ` · ${Math.round(result.score_percentage)}%` : ''}
              </p>
            </div>
            {!!result.summary && <p className="tma-muted">{result.summary}</p>}
            {!!result.criteria?.length && (
              <div style={{ marginTop: 12 }}>
                <p className="tma-h3">{t('tma_criteria')}</p>
                {result.criteria.map((c) => (
                  <div key={c.id} className="tma-crit">
                    <div>
                      <b>{c.name}</b>
                      {!!c.reason && <small>{c.reason}</small>}
                      {!!c.errors?.length && (
                        <small style={{ display: 'block', opacity: 0.8 }}>
                          {c.errors.map((e) => `“${e}”`).join(' · ')}
                        </small>
                      )}
                    </div>
                    <b>{c.score}<small style={{ opacity: 0.6 }}>/{c.max_score ?? 2}</small></b>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        <button className="tma-btn tma-btn-card" onClick={exitToTopics}>
          {t('tma_back')}
        </button>
      </div>
    );
  }

  if (view === 'write' && session) {
    const words = countWords(text);
    return (
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0 }}>{session.topic.title}</h2>
          <div className="tma-timer">⏱ {formatClock(remaining)}</div>
        </div>
        {!!session.topic.description && <p className="tma-muted" style={{ marginBottom: 12 }}>{session.topic.description}</p>}
        <div className="tma-sub" style={{ marginBottom: 8 }}>
          📏 {session.topic.word_limit_min}-{session.topic.word_limit_max} {t('tma_words')} · ⏱ {session.topic.time_limit_minutes} daqiqa · <span>{words} {t('tma_words')}</span>
        </div>
        <textarea
          className="tma-textarea big"
          placeholder={t('tma_write_hint')}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        {error && <p style={{ color: '#f87171', fontSize: 13 }}>{error}</p>}
        <div className="tma-btn-row">
          <button className="tma-btn tma-btn-card" onClick={exitToTopics}>
            {t('tma_cancel')}
          </button>
          <button className="tma-btn tma-btn-green" disabled={busy} onClick={() => void submitEssay()}>
            {busy ? '…' : t('tma_submit')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="tma-slide">
      <h2 style={{ fontSize: 18, fontWeight: 800, margin: '0 0 16px' }}>✍️ {t('tma_essays_title')}</h2>
      {error && <div className="tma-err" style={{ marginBottom: 12 }}>{error}</div>}
      {!topics && (
        <div className="tma-list">
          <div className="tma-skel" />
        </div>
      )}
      {topics && topics.length === 0 && <div className="tma-empty">{t('tma_no_topics')}</div>}
      {topics && topics.length > 0 && (
        <div className="tma-list">
          {topics.map((item) => (
            <div key={item.id}>
              <button onClick={() => openTopic(item)} className="tma-card tma-press">
                <div className="tma-row">
                  <div className="tma-ico" style={{ background: 'rgba(168,85,247,0.2)' }}>
                    {item.has_password ? '🔒' : '📝'}
                  </div>
                  <div className="tma-grow">
                    <p className="tma-title">{item.title}</p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                      <span className="tma-sub">
                        {item.word_limit_min}-{item.word_limit_max} {t('tma_words')} · {item.time_limit_minutes} daqiqa
                      </span>
                      <StatusBadge topic={item} />
                    </div>
                  </div>
                  <span style={{ color: '#6b7280', fontSize: 14 }}>→</span>
                </div>
              </button>
              {passwordFor === item.id && (
                <div className="tma-card" style={{ marginTop: 8 }}>
                  <p className="tma-sub" style={{ marginBottom: 8 }}>🔒 {t('tma_enter_password')}</p>
                  <input
                    className="tma-input"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void begin(item.id, password);
                    }}
                  />
                  <div className="tma-btn-row">
                    <button className="tma-btn tma-btn-hl" disabled={busy || !password} onClick={() => void begin(item.id, password)}>
                      {busy ? '…' : t('tma_submit')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ topic }: { topic: TmaEssayTopic }) {
  const st = topic.user_status;
  if (!st) return <span className="tma-sub">🆕 {translate('tma_new')}</span>;
  if (st.status === 'graded') {
    return <span style={{ fontSize: 10, color: 'var(--tma-green)' }}>✅ {st.total_score ?? 0}/24</span>;
  }
  return <span style={{ fontSize: 10, color: 'var(--tma-green)' }}>⏳ {st.status}</span>;
}
