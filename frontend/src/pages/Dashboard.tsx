import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { AuthExpiredError, Certificates, PaymentsApi, Results, School, Tests, Tuition, type PaymentReceiptItem, type TuitionOverview, type WeeklyReportRow } from '../lib/api';
import { num, type CertListItem, type ResultListItem, type TestListItem } from '../lib/testing';
import {
  AwardIcon,
  ClockIcon,
  FileTextIcon,
  TrophyIcon,
} from '../components/icons';
import UsageLimits from '../components/UsageLimits';
import TiltCard from '../components/TiltCard';
import OnboardingModal from '../components/OnboardingModal';
import {
  GraduationCap,
  Award,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';

interface Stats {
  total_tests_taken?: number;
  total_passed?: number;
  total_failed?: number;
  average_percentage?: number;
  best_percentage?: number;
  total_time_spent_seconds?: number;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [available, setAvailable] = useState<TestListItem[]>([]);
  const [testCount, setTestCount] = useState<number | null>(null);
  const [certs, setCerts] = useState<CertListItem[]>([]);
  const [certCount, setCertCount] = useState<number | null>(null);
  const [recent, setRecent] = useState<ResultListItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const [tuition, setTuition] = useState<TuitionOverview | null>(null);
  const [weeklyReports, setWeeklyReports] = useState<WeeklyReportRow[]>([]);
  const [pendingReceipt, setPendingReceipt] = useState<PaymentReceiptItem | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  useEffect(() => {
    if (user && user.onboarding_completed === false) {
      setOnboardingOpen(true);
    }
  }, [user]);

  // This dashboard is the landing page for every role (teachers and admins are
  // routed here too), but certificates are student-only on the server
  // (MyCertificatesView is [IsAuthenticated, IsStudent]). Requesting a list the
  // viewer may not read produced a blocking "You do not have permission to
  // perform this action." banner for staff, so the call is skipped instead.
  const isStudent = user?.role === 'student';

  useEffect(() => {
    let alive = true;
    Tuition.mine().then((value) => { if (alive) setTuition(value); }).catch(() => {});
    School.myWeeklyReports().then(({ results }) => { if (alive) setWeeklyReports(results); }).catch(() => {});
    PaymentsApi.myReceipts().then(({ results }) => {
      if (alive) {
        const pending = results.find((r) => r.status === 'pending');
        setPendingReceipt(pending || null);
      }
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const handler = () => setTick((v) => v + 1);
    window.addEventListener('subject-changed', handler);
    return () => window.removeEventListener('subject-changed', handler);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const activeSub = user?.active_subject || (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
        const results = await Promise.allSettled([
          Results.stats(),
          Tests.list({ subject: activeSub }),
          isStudent ? Certificates.mine() : Promise.resolve(null),
          Results.mine(),
        ]);
        if (cancelled) return;
        for (const item of results) {
          if (item.status === 'rejected' && item.reason instanceof AuthExpiredError) {
            navigate('/login');
            return;
          }
        }
        const [sR, tR, cRes, rRes] = results;
        const s = sR.status === 'fulfilled' ? (sR.value as unknown as Stats) : null;
        const tlist = tR.status === 'fulfilled' ? (tR.value as unknown as { count: number; results: TestListItem[] }) : null;
        const cVal = cRes.status === 'fulfilled' ? (cRes.value as unknown as { count: number; results: CertListItem[] }) : null;
        const rVal = rRes.status === 'fulfilled' ? (rRes.value as unknown as { results: ResultListItem[] }) : null;
        const failed = results.filter((x) => x.status === 'rejected');
        if (failed.length > 0 && !s && !tlist && !cVal && !rVal) {
          const first = failed[0] as PromiseRejectedResult;
          throw first.reason as Error;
        }
        if (failed.length > 0) {
          const msgs = failed.map((x) => (x as PromiseRejectedResult).reason?.message ?? '').filter(Boolean);
          if (msgs.length) setErr(msgs[0]);
        }
        setStats(s ?? null);
        setTestCount(tlist ? tlist.count : null);
        setAvailable(((tlist?.results ?? []) as TestListItem[]).slice(0, 6));
        setCertCount(cVal ? cVal.count : null);
        setCerts(((cVal?.results ?? []) as CertListItem[]).slice(0, 3));
        setRecent(((rVal?.results ?? []) as ResultListItem[]).slice(0, 5));
      } catch (e) {
        if (!cancelled) {
          if (e instanceof AuthExpiredError) navigate('/login');
          else setErr(e instanceof Error ? e.message : t('err_retry_js'));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t, navigate, tick, isStudent, user?.active_subject]);

  const avg = stats ? num(stats.average_percentage, 0) : null;

  return (
    <div>
      <h1>
        {t('welcome')}, {user?.full_name}
      </h1>

      {/* Personalized AI Roadmap Banner */}
      {user?.exam_target && user.exam_target !== 'undecided' && (
        <div
          className="card"
          style={{
            background:
              user.active_subject === 'english' || user.exam_target === 'ielts' || user.exam_target === 'multilevel'
                ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.14) 0%, rgba(79, 70, 229, 0.05) 100%)'
                : user.exam_target === 'attestation'
                ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.12) 0%, rgba(37, 99, 235, 0.05) 100%)'
                : 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.05) 100%)',
            borderColor:
              user.active_subject === 'english' || user.exam_target === 'ielts' || user.exam_target === 'multilevel'
                ? 'rgba(99, 102, 241, 0.35)'
                : user.exam_target === 'attestation'
                ? 'rgba(59, 130, 246, 0.35)'
                : 'rgba(16, 185, 129, 0.35)',
            marginBottom: 20,
            padding: '20px 24px',
            borderRadius: 16,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              flexWrap: 'wrap',
              marginBottom: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: 12,
                  background:
                    user.active_subject === 'english' || user.exam_target === 'ielts' || user.exam_target === 'multilevel'
                      ? 'rgba(99, 102, 241, 0.2)'
                      : user.exam_target === 'attestation'
                      ? 'rgba(59, 130, 246, 0.2)'
                      : 'rgba(16, 185, 129, 0.2)',
                  color:
                    user.active_subject === 'english' || user.exam_target === 'ielts' || user.exam_target === 'multilevel'
                      ? '#818CF8'
                      : user.exam_target === 'attestation'
                      ? '#60A5FA'
                      : '#34D399',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {user.active_subject === 'english' ? (
                  <span style={{ fontSize: '1.25rem', lineHeight: 1 }}>🇬🇧</span>
                ) : user.exam_target === 'attestation' ? (
                  <Award size={24} />
                ) : (
                  <GraduationCap size={24} />
                )}
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: 'var(--ink)' }}>
                  {user.active_subject === 'english' || user.exam_target === 'ielts' || user.exam_target === 'multilevel'
                    ? `🎯 Sizning rejangiz: ${user.exam_target === 'multilevel' ? 'CEFR Multi-level (B2/C1)' : 'IELTS (Academic & General)'} (Maqsad: ${user.target_grade || 'Band 7.5'})`
                    : user.exam_target === 'attestation'
                    ? `🎯 Sizning rejangiz: O'qituvchilar Attestatsiyasi 2026 (Maqsad: ${user.target_grade || 'Oliy toifa'})`
                    : `🎯 Sizning rejangiz: BMB Milliy sertifikat (Maqsad: ${user.target_grade || 'A+'})`}
                </h3>
                <span style={{ fontSize: '0.82rem', color: 'var(--ink-muted)' }}>
                  Tayyorgarlik muddati: {user.target_timeline_months || 3} oy · Boshlang'ich placement:{' '}
                  {user.placement_score !== null && user.placement_score !== undefined
                    ? `${user.placement_score}/5`
                    : 'Topshirilmagan'}
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setOnboardingOpen(true)}
              className="btn sm ghost"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.78rem',
                borderColor: 'rgba(255, 255, 255, 0.15)',
              }}
            >
              <RefreshCw size={13} />
              Rejani qayta sozlash
            </button>
          </div>

          {/* Recommended actions pill row */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
            {user.active_subject === 'english' || user.exam_target === 'ielts' || user.exam_target === 'multilevel' ? (
              <>
                <Link
                  to="/essays"
                  className="btn sm"
                  style={{
                    background: 'rgba(99, 102, 241, 0.25)',
                    borderColor: 'rgba(99, 102, 241, 0.45)',
                    color: '#C7D2FE',
                    fontWeight: 700,
                    textDecoration: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span>✍️ IELTS Writing AI Grader (Task 1 & 2)</span>
                  <ArrowRight size={14} />
                </Link>
                <Link
                  to="/tests"
                  className="btn sm ghost"
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  🎧 CBT Reading & Listening Simulator
                </Link>
                <Link
                  to="/arena"
                  className="btn sm ghost"
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  ⚔️ Vocabulary Arena
                </Link>
              </>
            ) : user.exam_target === 'attestation' ? (
              <>
                <Link
                  to="/tests"
                  className="btn sm"
                  style={{
                    background: 'rgba(59, 130, 246, 0.2)',
                    borderColor: 'rgba(59, 130, 246, 0.4)',
                    color: '#93C5FD',
                    fontWeight: 700,
                    textDecoration: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span>🎓 Rasmiy Attestatsiya Diagnostika 2026 (50 ta savol)</span>
                  <ArrowRight size={14} />
                </Link>
                <Link
                  to="/groups"
                  className="btn sm ghost"
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  👥 Guruhlar boshqaruvi
                </Link>
              </>
            ) : (
              <>
                <Link
                  to="/tests"
                  className="btn sm"
                  style={{
                    background: 'rgba(16, 185, 129, 0.2)',
                    borderColor: 'rgba(16, 185, 129, 0.4)',
                    color: '#6EE7B7',
                    fontWeight: 700,
                    textDecoration: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span>⭐️ BMB Rasmiy Mock Test (3 soatlik)</span>
                  <ArrowRight size={14} />
                </Link>
                <Link
                  to="/essays"
                  className="btn sm ghost"
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  ✍️ 12 mezonli BMB esse
                </Link>
                <Link
                  to="/arena"
                  className="btn sm ghost"
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  ⚔️ 1v1 Bilimlar Arenasi
                </Link>
              </>
            )}
          </div>
        </div>
      )}

      {err && (
        <p className="error" role="alert">
          {err}{' '}
          <button className="btn sm ghost" onClick={() => { setErr(null); setLoading(true); setTick((x) => x + 1); }}>
            {t('retry')}
          </button>
        </p>
      )}
      {loading && <p className="muted" role="status" aria-live="polite">{t('loading')}</p>}

      {/* Pending payment receipt alert banner */}
      {pendingReceipt && (
        <div
          className="card"
          style={{
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(217, 119, 6, 0.08))',
            borderColor: 'rgba(245, 158, 11, 0.35)',
            color: '#fef3c7',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '16px 20px',
            borderRadius: 12,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 24 }}>⏳</span>
            <div>
              <strong style={{ color: '#fbbf24', fontSize: 15, display: 'block' }}>
                {t('dash_receipt_pending_title')}
              </strong>
              <p className="small muted" style={{ margin: 0, color: '#fde68a' }}>
                {pendingReceipt.plan.toUpperCase()} {t('dash_receipt_pending_desc')}
              </p>
            </div>
          </div>
          <Link
            to="/subscribe"
            className="badge yellow"
            style={{
              textDecoration: 'none',
              background: 'rgba(245, 158, 11, 0.2)',
              color: '#fbbf24',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              padding: '6px 14px',
              fontSize: 12,
              fontWeight: 700,
              whiteSpace: 'nowrap',
            }}
          >
            {t('dash_view_receipt_status')}
          </Link>
        </div>
      )}

      {/* Platform subscription remains separate from course tuition. */}
      <UsageLimits />
      {tuition && (tuition.invoices.length > 0 || tuition.outstanding_uzs > 0) && (
        <section className="card" aria-label="Course tuition">
          <h2>💳 {t('tuition_title')}</h2>
          <p className="muted">{t('tuition_confirmed')}: {Number(tuition.confirmed_paid_uzs).toLocaleString()} {t('currency_uzs')} · {t('tuition_outstanding')}: {Number(tuition.outstanding_uzs).toLocaleString()} {t('currency_uzs')}</p>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>{t('tuition_period')}</th><th>{t('tuition_status')}</th><th>{t('tuition_amount')}</th><th>{t('tuition_paid')}</th><th>{t('tuition_outstanding')}</th><th>{t('tuition_deadline')}</th><th>{t('tuition_payment_instructions')}</th></tr></thead>
            <tbody>{tuition.invoices.map((invoice) => <tr key={invoice.id}>
              <td>{invoice.period_label}</td><td>{invoice.status_label}{invoice.awaiting_confirmation ? ` · ${t('tuition_pending')}` : ''}</td>
              <td>{Number(invoice.amount_due_uzs).toLocaleString()} {t('currency_uzs')}</td><td>{Number(invoice.paid_amount_uzs).toLocaleString()} {t('currency_uzs')}</td>
              <td>{Number(invoice.balance_uzs).toLocaleString()} {t('currency_uzs')}</td><td>{invoice.due_date}</td><td>{invoice.payment_instructions || '—'}</td>
            </tr>)}</tbody>
          </table></div>
        </section>
      )}
      {weeklyReports.length > 0 && (
        <section className="card" aria-label="Weekly academic reports">
          <h2>📊 {t('weekly_reports_title')}</h2>
          {weeklyReports.map((report) => <article key={report.id}>
            <h3>{report.period_label}</h3>
            <p className="muted">{t('weekly_attendance')}: {String((report.summary.attendance as Record<string, unknown> | undefined)?.attendance_percentage ?? '—')}% · {t('weekly_essays')}: {String((report.summary.essays as Record<string, unknown> | undefined)?.graded ?? 0)} · {t('weekly_tests')}: {String((report.summary.tests as Record<string, unknown> | undefined)?.completed_attempts ?? 0)}</p>
          </article>)}
        </section>
      )}

      {/* Stat cards — modern 3D Tilt & parity with legacy student_dashboard.html. */}
      <div className="grid">
        <TiltCard glare maxTilt={8} scale={1.02} style={{ borderRadius: 'var(--radius)' }}>
          <div className="card stat stat-gradient-blue" style={{ height: '100%', margin: 0 }}>
            <span className="stat-label">
              <FileTextIcon size={13} className="ico" /> {t('stat_tests_taken')}
            </span>
            <span className="stat-value">
              {stats ? num(stats.total_tests_taken, 0) : '…'}
            </span>
            <span className="muted small">{t('stat_sub_total_hint')}</span>
            <Link to="/tests">{t('tests')} →</Link>
          </div>
        </TiltCard>
        <TiltCard glare maxTilt={8} scale={1.02} style={{ borderRadius: 'var(--radius)' }}>
          <div className="card stat stat-gradient-green" style={{ height: '100%', margin: 0 }}>
            <span className="stat-label">
              <TrophyIcon size={13} className="ico" /> {t('stat_tests_passed')}
            </span>
            <span className="stat-value">
              {stats ? num(stats.total_passed, 0) : '…'}
            </span>
            <span className="muted small">
              {stats
                ? `${num(stats.total_passed, 0)}/${num(stats.total_tests_taken, 0)} ${t('stat_successfully')}`
                : t('hint_take_test')}
            </span>
            <Link to="/results">{t('my_results')} →</Link>
          </div>
        </TiltCard>
        <TiltCard glare maxTilt={8} scale={1.02} style={{ borderRadius: 'var(--radius)' }}>
          <div className="card stat stat-gradient-amber" style={{ height: '100%', margin: 0 }}>
            <span className="stat-label">
              <TrophyIcon size={13} className="ico" /> {t('average_score')}
            </span>
            <span className="stat-value">{avg === null ? '…' : `${avg}%`}</span>
            <span className="muted small">
              {avg === null
                ? ''
                : avg >= 70
                  ? t('perf_excellent')
                  : avg >= 50
                    ? t('perf_not_bad')
                    : t('perf_more_effort')}
            </span>
            <Link to="/results">{t('recent_results')} →</Link>
          </div>
        </TiltCard>
        {isStudent && (
          <TiltCard glare maxTilt={8} scale={1.02} style={{ borderRadius: 'var(--radius)' }}>
            <div className="card stat stat-gradient-purple" style={{ height: '100%', margin: 0 }}>
              <span className="stat-label">
                <AwardIcon size={13} className="ico" /> {t('certificates')}
              </span>
              <span className="stat-value">{certCount ?? '…'}</span>
              <span className="muted small">
                {t('count_certificates')} · {t('download_pdf_hint')}
              </span>
              <Link to="/certificates">{t('my_certificates')} →</Link>
            </div>
          </TiltCard>
        )}
      </div>

      {/* Available tests preview (legacy: first 6 active tests). */}
      <h2>{t('available_tests')}</h2>
      <p className="muted">{t('available_tests_hint')}</p>
      {available.length === 0 ? (
        <div className="card">
          <h3>{t('no_tests_title')}</h3>
          <p className="muted">{t('no_tests_hint')}</p>
          <Link className="btn primary" to="/tests">
            {t('view_tests')}
          </Link>
        </div>
      ) : (
        <div className="grid">
          {available.map((item) => (
            <TiltCard key={item.id} glare maxTilt={6} scale={1.02} style={{ borderRadius: 'var(--radius)', height: '100%' }}>
              <Link to={`/tests/${item.id}`} className="card link-card" style={{ height: '100%', margin: 0 }}>
                <div className="toolbar" style={{ marginBottom: 8 }}>
                  <span className="badge blue">{t(`difficulty_${item.difficulty ?? ''}`) !== `difficulty_${item.difficulty ?? ''}` ? t(`difficulty_${item.difficulty ?? ''}`) : String(item.difficulty ?? '—')}</span>
                  {(item.time_limit_minutes ?? 0) > 0 && (
                    <span className="badge amber">
                      <ClockIcon size={12} className="ico" /> {item.time_limit_minutes}{' '}
                      {t('minutes_suffix')}
                    </span>
                  )}
                </div>
                <strong>{String(item.title ?? `Test #${item.id}`)}</strong>
                <span className="muted small">
                  {num(item.total_questions, 0)} {t('questions_suffix')} ·{' '}
                  {t('pass_suffix')}: {num(item.pass_percentage, 0)}%
                </span>
              </Link>
            </TiltCard>
          ))}
        </div>
      )}
      <p className="muted small">
        <Link to="/tests">
          {t('view_all')} → ({testCount ?? '…'})
        </Link>
      </p>

      {/* Recent results (legacy: last 5, linked to detail). */}
      <h2>{t('recent_results')}</h2>
      {recent.length === 0 ? (
        <div className="card">
          <h3>{t('no_results_title')}</h3>
          <p className="muted">{t('no_results_hint')}</p>
          <Link className="btn primary" to="/tests">
            {t('view_tests')}
          </Link>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_test_name')}</th>
                <th>{t('score')}</th>
                <th>{t('status')}</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/results/${r.id}`}>
                      {String(r.test_title ?? r.test ?? `#${r.id}`)}
                    </Link>
                    <div className="muted small">{String(r.course_title ?? '')}</div>
                  </td>
                  <td>{num(r.percentage, 0)}%</td>
                  <td>
                    <span className={`badge ${r.is_passed ? 'green' : 'rose'}`}>
                      {r.is_passed ? t('status_passed') : t('status_failed')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Certificates preview (legacy: quick certificates block). */}
      {isStudent && certs.length > 0 && (
        <>
          <h2>{t('my_certificates')}</h2>
          <p className="muted">{t('my_certificates_hint')}</p>
          <div className="grid">
            {certs.map((c) => (
              <Link key={c.id} to="/certificates" className="card link-card">
                <span className="stat-label">
                  <AwardIcon size={13} className="ico" />{' '}
                  {String(c.certificate_number ?? '')}
                </span>
                <strong>
                  {String(c.course_title ?? c.test_title ?? `#${c.id}`)}
                </strong>
                <span className="muted small">
                  {num(c.percentage, 0)}% · {String(c.status ?? '')}
                </span>
              </Link>
            ))}
          </div>
        </>
      )}

      <OnboardingModal
        isOpen={onboardingOpen}
        onClose={() => setOnboardingOpen(false)}
        onSuccess={() => setTick((x) => x + 1)}
      />
    </div>
  );
}
