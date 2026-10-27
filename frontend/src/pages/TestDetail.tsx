import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Tests as TestsApi } from '../lib/api';
import { Results as ResultsApi } from '../lib/api';
import { num } from '../lib/testing';
import { CheckIcon, ClockIcon, HashIcon, StarIcon } from '../components/icons';
import SEO from '../components/SEO';

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
  subject?: string;
  exam_type?: string;
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
  const [modeModalOpen, setModeModalOpen] = useState(false);

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

  const startWithMode = async (mode: 'strict' | 'practice') => {
    setStarting(true);
    setErr(null);
    setModeModalOpen(false);
    try {
      const res = await TestsApi.start(id, mode);
      const attemptId =
        'id' in res && typeof res.id === 'number'
          ? res.id
          : (res as { attempt_id: number }).attempt_id;
      
      const isEnglish = detail?.subject === 'english' ||
        detail?.exam_type?.includes('ielts') ||
        detail?.exam_type?.includes('cefr');

      if (isEnglish) {
        navigate(`/english-exam/${attemptId}`);
      } else {
        navigate(`/take/${attemptId}`);
      }
    } catch (e) {
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
      <SEO
        title={detail ? `${detail.title} — Online Test | GRANDEC` : `Test #${id} | GRANDEC`}
        description={detail?.description || `GRANDEC platformasida ${detail?.title || 'test'} bo'yicha online imtihon topshiring.`}
        canonical={`/tests/${id}`}
        type="article"
      />
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
              onClick={() => setModeModalOpen(true)}
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
      {/* Mode Selection Modal */}
      {modeModalOpen && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="card" style={{ maxWidth: 560, width: '100%', padding: 24, borderRadius: 16 }}>
            <h3 style={{ marginTop: 0, fontSize: 20 }}>Format va Rejimni Tanlang</h3>
            <p className="muted" style={{ fontSize: 13, marginBottom: 20 }}>
              Testni qanday formatda topshirmoqchisiz? Rasmiy imtihon qatʼiy nazorat ostida o'tkaziladi.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
              {/* Option 1: Strict Exam Mode */}
              <button
                onClick={() => startWithMode('strict')}
                style={{
                  textAlign: 'left',
                  padding: 16,
                  borderRadius: 12,
                  border: '2px solid rgba(239, 68, 68, 0.4)',
                  backgroundColor: 'rgba(239, 68, 68, 0.05)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 'bold', color: '#ef4444' }}>
                  <span>🛑 Strict Exam Mode (Rasmiy Imtihon)</span>
                </div>
                <p style={{ margin: 0, fontSize: 12, color: 'inherit', opacity: 0.85 }}>
                  To'liq ekran (F11), 3 marta boshqa oynaga o'tishda avto-yakunlash (Anti-Cheat), audioni bir marta eshitish (Audio Lock), yordamsiz qat'iy sinov.
                </p>
              </button>

              {/* Option 2: Practice / Study Mode */}
              <button
                onClick={() => startWithMode('practice')}
                style={{
                  textAlign: 'left',
                  padding: 16,
                  borderRadius: 12,
                  border: '2px solid rgba(16, 185, 129, 0.4)',
                  backgroundColor: 'rgba(16, 185, 129, 0.05)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 'bold', color: '#10b981' }}>
                  <span>💡 Practice / Study Mode (O'rganish)</span>
                </div>
                <p style={{ margin: 0, fontSize: 12, color: 'inherit', opacity: 0.85 }}>
                  Cheklovlarsiz erkin format: audio qayta eshitilishi, savollar o'rtasida erkin o'tish va har bir savol ostida [ 💡 AI Tushuntirish ] tugmasi.
                </p>
              </button>
            </div>

            <div style={{ marginTop: 20, textAlign: 'right' }}>
              <button
                className="btn ghost"
                onClick={() => setModeModalOpen(false)}
                style={{ fontSize: 13 }}
              >
                Bekor qilish
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
