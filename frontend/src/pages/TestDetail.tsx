import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Tests as TestsApi } from '../lib/api';
import { Results as ResultsApi } from '../lib/api';
import { num } from '../lib/testing';
import { CheckIcon, ClockIcon, HashIcon, StarIcon } from '../components/icons';

interface Detail {
  id: number;
  title: string;
  description: string;
  course?: number;
  difficulty: string;
  time_limit_minutes: number;
  max_attempts: number;
  pass_percentage: number;
  total_questions: number;
  total_points: number;
  has_time_limit: boolean;
  shuffle_questions?: boolean;
  shuffle_choices?: boolean;
  show_results_immediately?: boolean;
  questions?: { id: number; text: string; points: number }[];
}

export default function TestDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [myAttempts, setMyAttempts] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    TestsApi.detail(id)
      .then((d) => {
        if (!cancelled) setDetail(d as unknown as Detail);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : t('err_retry_js'));
      });
    // Attempts used on this test (for "X/Y urinish" parity with legacy stats).
    ResultsApi.mine()
      .then((p) => {
        if (cancelled) return;
        const n = (p.results ?? []).filter(
          (r) => String((r as Record<string, unknown>).test ?? '') === String(id),
        ).length;
        setMyAttempts(n);
      })
      .catch(() => {
        /* non-fatal */
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const start = async () => {
    setStarting(true);
    setErr(null);
    try {
      const res = await TestsApi.start(id);
      const attemptId =
        'id' in res && typeof res.id === 'number'
          ? res.id
          : (res as { attempt_id: number }).attempt_id;
      navigate(`/take/${attemptId}`);
    } catch (e) {
      // Backend StartAttemptService 400 cases: active attempt in progress
      // (resume it) or max_attempts exhausted. Surface the message verbatim.
      setErr(e instanceof Error ? e.message : t('err_retry_js'));
      setStarting(false);
    }
  };

  if (!detail && !err) return <p className="muted">{t('loading')}</p>;

  const maxAttempts = detail ? num(detail.max_attempts, 1) : 1;
  const attemptsLeft =
    myAttempts === null || maxAttempts === 0 ? null : Math.max(0, maxAttempts - myAttempts);

  return (
    <div>
      <p className="muted small">
        <Link to="/tests">← {t('tests')}</Link>
      </p>
      <h1>{detail ? detail.title : `Test #${id}`}</h1>
      {err && <p className="error">{err}</p>}
      {detail && (
        <>
          {detail.description && <p className="muted">{detail.description}</p>}
          <div className="toolbar">
            <span className="badge blue">{detail.difficulty}</span>
            <span className="badge">
              <HashIcon size={12} className="ico" /> {detail.total_questions} {t('questions_suffix')}
            </span>
            <span className="badge">
              <StarIcon size={12} className="ico" /> {detail.total_points} {t('points')}
            </span>
            {detail.has_time_limit && (
              <span className="badge amber">
                <ClockIcon size={12} className="ico" /> {detail.time_limit_minutes} {t('minutes_suffix')}
              </span>
            )}
            <span className="badge green">
              <CheckIcon size={12} className="ico" /> {t('pass_suffix')}: {detail.pass_percentage}%
            </span>
          </div>
          <div className="card" style={{ marginTop: 12 }}>
            <p className="muted small">
              {t('th_attempts')}: {maxAttempts === 0 ? '∞' : maxAttempts}
              {attemptsLeft !== null && ` · ${t('test_attempts_left')}: ${attemptsLeft}`}
              {myAttempts !== null && myAttempts > 0 && ` · ${t('test_my_attempts')}: ${myAttempts}`}
            </p>
            {attemptsLeft === 0 && (
              <p className="error">{t('test_no_attempts_left')}</p>
            )}
          </div>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button
              className="btn primary"
              onClick={start}
              disabled={starting || attemptsLeft === 0}
            >
              {starting ? t('loading') : t('start_test')}
            </button>
            <Link className="btn ghost" to="/results">
              {t('my_results')}
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
