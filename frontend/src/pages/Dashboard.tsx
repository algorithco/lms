import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import {
  AuthExpiredError,
  Certificates,
  GamificationApi,
  PaymentsApi,
  Results,
  School,
  Tests,
  Tuition,
  type LeagueLeaderboardResponse,
  type PaymentReceiptItem,
  type StreakInfoResponse,
  type TuitionOverview,
  type WeeklyReportRow,
} from '../lib/api';
import { num, TestsApi, type CertListItem, type ResultListItem, type TestListItem } from '../lib/testing';
import {
  AwardIcon,
  CameraIcon,
  ClockIcon,
  FileTextIcon,
  FlameIcon,
  MicIcon,
  TrophyIcon,
  ZapIcon,
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
  const [streak, setStreak] = useState<StreakInfoResponse | null>(null);
  const [league, setLeague] = useState<LeagueLeaderboardResponse | null>(null);
  const [vaultStats, setVaultStats] = useState<{ unresolved_count: number; weak_topics: { topic: string; error_count: number }[] } | null>(null);

  useEffect(() => {
    const isDone = localStorage.getItem('grandec_onboarding_done') === 'true';
    if (isDone || user?.onboarding_completed === true) {
      setOnboardingOpen(false);
      return;
    }
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
    GamificationApi.streak().then((res) => { if (alive) setStreak(res); }).catch(() => {});
    GamificationApi.league().then((res) => { if (alive) setLeague(res); }).catch(() => {});
    if (isStudent) {
      TestsApi.getMistakeVault().then((v) => { if (alive) setVaultStats(v); }).catch(() => {});
    }
    return () => { alive = false; };
  }, [user]);

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
          console.warn('Dashboard non-critical partial load rejection:', msgs);
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

  const currentSubject: 'uzbek' | 'english' =
    user?.active_subject === 'english' || localStorage.getItem('lms_subject') === 'english'
      ? 'english'
      : 'uzbek';
  const isEnglish = currentSubject === 'english';
  const effectiveTarget = isEnglish
    ? (user?.exam_target === 'multilevel' ? 'multilevel' : 'ielts')
    : (user?.exam_target === 'attestation' ? 'attestation' : 'national_certificate');

  return (
    <div>
      <h1>
        {t('welcome')}, {user?.full_name}
      </h1>

      {/* Mistakes Workbench Banner */}
      {isStudent && vaultStats && vaultStats.unresolved_count > 0 && (
        <div
          className="card"
          style={{
            marginBottom: 20,
            padding: '16px 20px',
            borderRadius: 14,
            background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(245, 158, 11, 0.08) 100%)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}>
              🎯
            </div>
            <div>
              <strong style={{ color: 'var(--ink)', fontSize: '0.98rem', display: 'block' }}>
                Xatolar ustida avto-mashq: {vaultStats.unresolved_count} ta zaif nuqta aniqlangan
              </strong>
              <span className="muted small">
                {vaultStats.weak_topics.length > 0 ? `Asosiy mavzular: ${vaultStats.weak_topics.slice(0, 2).map((t: { topic: string }) => t.topic).join(', ')}` : 'Testdagi xatolaringizni mustahkamlang'}
              </span>
            </div>
          </div>
          <Link to="/results" className="btn sm primary" style={{ background: '#ef4444', border: 'none', fontWeight: 700 }}>
            🔁 Xatolarni ishlash →
          </Link>
        </div>
      )}

      {/* Personalized AI Roadmap Banner */}
      {user?.exam_target && user.exam_target !== 'undecided' && (
        <div
          className="card"
          style={{
            background: isEnglish
              ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.14) 0%, rgba(79, 70, 229, 0.05) 100%)'
              : effectiveTarget === 'attestation'
              ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.12) 0%, rgba(37, 99, 235, 0.05) 100%)'
              : 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.05) 100%)',
            borderColor: isEnglish
              ? 'rgba(99, 102, 241, 0.35)'
              : effectiveTarget === 'attestation'
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
                  background: isEnglish
                    ? 'rgba(99, 102, 241, 0.2)'
                    : effectiveTarget === 'attestation'
                    ? 'rgba(59, 130, 246, 0.2)'
                    : 'rgba(16, 185, 129, 0.2)',
                  color: isEnglish
                    ? '#818CF8'
                    : effectiveTarget === 'attestation'
                    ? '#60A5FA'
                    : '#34D399',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {isEnglish ? (
                  <span style={{ fontSize: '1.25rem', lineHeight: 1 }}>🇬🇧</span>
                ) : effectiveTarget === 'attestation' ? (
                  <Award size={24} />
                ) : (
                  <GraduationCap size={24} />
                )}
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: 'var(--ink)' }}>
                  {isEnglish
                    ? `🎯 Sizning rejangiz: ${effectiveTarget === 'multilevel' ? 'CEFR Multi-level (B2/C1)' : 'IELTS (Academic & General)'} (Maqsad: ${user.target_grade || (effectiveTarget === 'multilevel' ? 'C1' : 'Band 7.5')})`
                    : effectiveTarget === 'attestation'
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
              🔄 Rejani qayta sozlash
            </button>
          </div>

          {/* Recommended actions pill row */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
            {isEnglish ? (
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
                  <span>✍️ {effectiveTarget === 'multilevel' ? 'CEFR Writing Grader' : 'IELTS Writing AI Grader (Task 1 & 2)'}</span>
                  <ArrowRight size={14} />
                </Link>
                <Link
                  to="/speaking"
                  className="btn sm"
                  style={{
                    background: 'rgba(168, 85, 247, 0.25)',
                    borderColor: 'rgba(168, 85, 247, 0.45)',
                    color: '#E9D5FF',
                    fontWeight: 700,
                    textDecoration: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <MicIcon size={14} />
                  <span>AI Speaking Simulyatori</span>
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
            ) : effectiveTarget === 'attestation' ? (
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
                  to="/tests/scan-omr"
                  className="btn sm ghost"
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  <CameraIcon size={14} /> Titul (OMR) Skaner
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
                  to="/tests/scan-omr"
                  className="btn sm ghost"
                  style={{ fontWeight: 600, textDecoration: 'none' }}
                >
                  <CameraIcon size={14} /> Titul (OMR) Skaner
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

      {/* Duolingo-Style Gamification: Daily Streak & Weekly League */}
      {streak && (
        <section
          className="card"
          style={{
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(234, 88, 12, 0.04) 100%)',
            borderColor: 'rgba(245, 158, 11, 0.25)',
            marginBottom: 20,
            padding: '18px 22px',
            borderRadius: 16,
          }}
          aria-label="Gamifikatsiya va streak"
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, alignItems: 'center' }}>
            {/* Streak Counter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div
                style={{
                  width: 50,
                  height: 50,
                  borderRadius: 14,
                  background: streak.is_active_today
                    ? 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)'
                    : 'rgba(245, 158, 11, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: streak.is_active_today ? '#fff' : '#f59e0b',
                  boxShadow: streak.is_active_today ? '0 4px 14px rgba(234, 88, 12, 0.4)' : 'none',
                }}
              >
                <FlameIcon size={28} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f59e0b' }}>
                    {streak.current_streak} kunlik streak!
                  </span>
                  {streak.is_active_today && (
                    <span style={{ fontSize: '0.72rem', background: '#10b981', color: '#fff', padding: '2px 6px', borderRadius: 6, fontWeight: 700 }}>
                      Faol
                    </span>
                  )}
                </div>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--muted, #94a3b8)' }}>
                  {streak.is_active_today
                    ? 'Bugungi maqsad bajarildi, olov yonmoqda! 🔥'
                    : 'Streakni yo\'qotmaslik uchun bugun test yoki mashq bajaring!'}
                </p>
              </div>
            </div>

            {/* Daily Goal & XP */}
            <div
              style={{
                background: 'rgba(0, 0, 0, 0.2)',
                padding: '10px 14px',
                borderRadius: 12,
                border: '1px solid rgba(255, 255, 255, 0.06)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted, #94a3b8)', fontWeight: 600 }}>
                  Jami Tajriba (XP)
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ZapIcon size={16} style={{ color: '#fbbf24' }} />
                  <span style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fbbf24' }}>
                    {streak.xp_points} XP
                  </span>
                  <span style={{ fontSize: '0.75rem', color: '#6ee7b7', marginLeft: 4 }}>
                    (+{streak.weekly_xp} bu hafta)
                  </span>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--muted, #94a3b8)' }}>Muzlatgich</span>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#93c5fd' }}>
                  ❄️ {streak.streak_freeze_count} ta
                </div>
              </div>
            </div>

            {/* League Badge */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(0, 0, 0, 0.2)',
                padding: '10px 14px',
                borderRadius: 12,
                border: '1px solid rgba(255, 255, 255, 0.06)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted, #94a3b8)', fontWeight: 600 }}>
                  Haftalik Liga
                </span>
                <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#e2e8f0', textTransform: 'capitalize' }}>
                  {streak.weekly_league === 'diamond' ? '💎 Olmos Ligasi' :
                   streak.weekly_league === 'gold' ? '🥇 Oltin Ligasi' :
                   streak.weekly_league === 'silver' ? '🥈 Kumush Ligasi' : '🥉 Bronza Ligasi'}
                </div>
              </div>
              {league && (
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--muted, #94a3b8)' }}>Reyting</span>
                  <div style={{ fontWeight: 800, fontSize: '1rem', color: '#f59e0b' }}>
                    #{league.user_rank || '—'}
                  </div>
                </div>
              )}
            </div>
          </div>
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
        <div className="card" style={{ padding: '28px 20px', textAlign: 'center' }}>
          <h3>{isEnglish ? '🎧 English CBT Reading & Listening Testlar' : t('no_tests_title')}</h3>
          <p className="muted" style={{ maxWidth: 500, margin: '8px auto 16px' }}>
            {isEnglish
              ? 'Hozircha ommaviy CBT testlar tayyorlanmoqda. Shuningdek o\'qituvchingiz bergan mock test kodi orqali testga qo\'shilishingiz mumkin.'
              : t('no_tests_hint')}
          </p>
          <Link className="btn primary" to="/tests">
            {isEnglish ? 'CBT Testlar sahifasiga o\'tish' : t('view_tests')}
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
        onClose={() => {
          localStorage.setItem('grandec_onboarding_done', 'true');
          setOnboardingOpen(false);
        }}
        onSuccess={() => {
          localStorage.setItem('grandec_onboarding_done', 'true');
          setTick((x) => x + 1);
        }}
      />
    </div>
  );
}
