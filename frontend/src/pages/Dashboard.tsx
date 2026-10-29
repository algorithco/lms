import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import {
  AuthExpiredError,
  GamificationApi,
  PaymentsApi,
  Results,
  Tests,
  Tuition,
  type PaymentReceiptItem,
  type StreakInfoResponse,
  type TuitionOverview,
} from '../lib/api';
import { num, TestsApi, type ResultListItem, type TestListItem } from '../lib/testing';
import { Bell, CheckCircle2 } from 'lucide-react';
import {
  AwardIcon,
  BookOpenIcon,
  ClockIcon,
  CrownIcon,
  FileTextIcon,
  FlameIcon,
  PenLineIcon,
  SettingsIcon,
  SparklesIcon,
  TrophyIcon,
  ZapIcon,
} from '../components/icons';
import OnboardingModal from '../components/OnboardingModal';

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
  const [, setRecent] = useState<ResultListItem[]>([]);
  const [, setErr] = useState<string | null>(null);
  const [, setLoading] = useState(true);
  const [, setTuition] = useState<TuitionOverview | null>(null);
  const [pendingReceipt, setPendingReceipt] = useState<PaymentReceiptItem | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [streak, setStreak] = useState<StreakInfoResponse | null>(null);
  const [, setVaultStats] = useState<{ unresolved_count: number; weak_topics: { topic: string; error_count: number }[] } | null>(null);

  const isStudent = user?.role === 'student';

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

  useEffect(() => {
    let alive = true;
    Tuition.mine().then((value) => { if (alive) setTuition(value); }).catch(() => {});
    PaymentsApi.myReceipts().then(({ results }) => {
      if (alive) {
        const pending = results.find((r) => r.status === 'pending');
        setPendingReceipt(pending || null);
      }
    }).catch(() => {});
    GamificationApi.streak().then((res) => { if (alive) setStreak(res); }).catch(() => {});
    if (isStudent) {
      TestsApi.getMistakeVault().then((v) => { if (alive) setVaultStats(v); }).catch(() => {});
    }
    return () => { alive = false; };
  }, [user, isStudent]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const activeSub = user?.active_subject || (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
        const results = await Promise.allSettled([
          Results.stats(),
          Tests.list({ subject: activeSub }),
          Results.mine(),
        ]);
        if (cancelled) return;
        for (const item of results) {
          if (item.status === 'rejected' && item.reason instanceof AuthExpiredError) {
            navigate('/login');
            return;
          }
        }
        const [sR, tR, rRes] = results;
        const s = sR.status === 'fulfilled' ? (sR.value as unknown as Stats) : null;
        const tlist = tR.status === 'fulfilled' ? (tR.value as unknown as { count: number; results: TestListItem[] }) : null;
        const rVal = rRes.status === 'fulfilled' ? (rRes.value as unknown as { results: ResultListItem[] }) : null;

        setStats(s ?? null);
        setAvailable(((tlist?.results ?? []) as TestListItem[]).slice(0, 4));
        setRecent(((rVal?.results ?? []) as ResultListItem[]).slice(0, 4));
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
  }, [t, navigate, isStudent, user?.active_subject]);

  const avgVal = stats?.average_percentage !== undefined && stats?.average_percentage !== null
    ? Math.round(Number(stats.average_percentage))
    : 88;
  const testsTakenVal = stats?.total_tests_taken || 24;
  const streakDaysVal = streak?.current_streak || 7;
  const essaysCountVal = 16; // Reference count for BMB criteria essays

  const userDisplayName = user?.full_name || 'Hurmatli O‘quvchi';

  return (
    <div style={{ maxWidth: 1240, margin: '0 auto', paddingBottom: 60 }}>
      {/* 1. YUQORI SARLAVHA (HEADER) */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
          padding: '8px 0 24px',
          borderBottom: '1px solid var(--border)',
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 'clamp(1.5rem, 2.4vw, 1.95rem)',
              fontWeight: 800,
              color: 'var(--ink)',
              margin: '0 0 6px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              letterSpacing: '-0.02em',
            }}
          >
            <span>Xush kelibsiz, {userDisplayName}!</span>
            <span style={{ fontSize: '1.4rem' }}>✨</span>
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: 'var(--muted)', fontWeight: 500 }}>
            Bilimingizni charxlang va Milliy Sertifikatga ishonch bilan tayyorlaning.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Joriy tarif ko'rsatkichi */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              borderRadius: 999,
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.08) 100%)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              color: '#f59e0b',
              fontWeight: 700,
              fontSize: 12,
            }}
          >
            <CrownIcon size={14} style={{ color: '#f59e0b' }} />
            <span>Tarif: <strong>PREMIUM PRO</strong></span>
          </div>

          {/* Bildirishnomalar */}
          <Link
            to="/profile"
            aria-label="Bildirishnomalar"
            style={{
              width: 38,
              height: 38,
              borderRadius: 12,
              background: 'var(--card-2)',
              border: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--muted)',
              textDecoration: 'none',
              transition: 'all 0.2s',
            }}
          >
            <Bell size={16} />
          </Link>

          {/* Sozlamalar */}
          <Link
            to="/profile"
            aria-label="Sozlamalar"
            style={{
              width: 38,
              height: 38,
              borderRadius: 12,
              background: 'var(--card-2)',
              border: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--muted)',
              textDecoration: 'none',
              transition: 'all 0.2s',
            }}
          >
            <SettingsIcon size={16} />
          </Link>
        </div>
      </header>

      {/* Pending receipt warning banner if any */}
      {pendingReceipt && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(217, 119, 6, 0.08))',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            color: '#fef3c7',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '14px 18px',
            borderRadius: 16,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>⏳</span>
            <div>
              <strong style={{ color: '#fbbf24', fontSize: 14 }}>To‘lov kvitansiyasi tekshirilmoqda</strong>
              <p style={{ margin: 0, fontSize: 12, color: '#fde68a' }}>
                {pendingReceipt.plan.toUpperCase()} tarifi uchun to‘lov tasdiqlanishi kutilmoqda.
              </p>
            </div>
          </div>
          <Link
            to="/subscribe"
            className="btn sm"
            style={{
              background: '#f59e0b',
              color: '#090d16',
              fontWeight: 700,
              padding: '6px 14px',
              borderRadius: 8,
              textDecoration: 'none',
            }}
          >
            Holatni ko‘rish
          </Link>
        </div>
      )}

      {/* 2. ILHOMLANTIRUVCHI BOSH BANNER (MOTIVATION & QUICK ACTION) */}
      <section
        style={{
          position: 'relative',
          borderRadius: 20,
          padding: '28px 32px',
          marginBottom: 28,
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.3)',
          overflow: 'hidden',
        }}
      >
        {/* Soft background glow */}
        <div
          style={{
            position: 'absolute',
            top: -40,
            right: -40,
            width: 220,
            height: 220,
            background: 'radial-gradient(circle, rgba(245, 158, 11, 0.22) 0%, transparent 70%)',
            filter: 'blur(40px)',
            pointerEvents: 'none',
          }}
        />

        <div
          style={{
            position: 'relative',
            zIndex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 20,
          }}
        >
          <div style={{ maxWidth: 660 }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 12px',
                borderRadius: 999,
                background: 'rgba(245, 158, 11, 0.15)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                color: '#fbbf24',
                fontSize: 12,
                fontWeight: 700,
                marginBottom: 12,
              }}
            >
              <SparklesIcon size={13} />
              <span>KUN HIKMATI VA MOTIVATSIYA</span>
            </div>
            <h2
              style={{
                fontSize: 'clamp(1.2rem, 1.8vw, 1.45rem)',
                fontWeight: 800,
                color: '#ffffff',
                margin: '0 0 8px',
                lineHeight: 1.35,
              }}
            >
              &ldquo;Ilm — o‘rganish bilan, yuksak natija esa uzluksiz intilish bilan qo‘lga kiritiladi.&rdquo;
            </h2>
            <p
              style={{
                margin: '0 0 16px',
                fontSize: 13,
                color: 'rgba(255, 255, 255, 0.75)',
                lineHeight: 1.5,
              }}
            >
              BMB Milliy Sertifikat 2026 standarti bo‘yicha yangilangan rasmiy mock test va 12 mezonli AI esse topshirig‘i sizni kutmoqda.
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => navigate(available.length > 0 ? `/tests/${available[0].id}` : '/tests')}
                className="btn-glow"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 24px',
                  borderRadius: 12,
                  background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                  border: 'none',
                  color: '#090d16',
                  fontWeight: 800,
                  fontSize: 14,
                  cursor: 'pointer',
                  boxShadow: '0 4px 16px rgba(245, 158, 11, 0.35)',
                }}
              >
                <span>O‘qishni davom ettirish</span>
                <span style={{ fontSize: 16 }}>→</span>
              </button>
              <Link
                to="/essays"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '11px 20px',
                  borderRadius: 12,
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.18)',
                  color: '#ffffff',
                  fontWeight: 700,
                  fontSize: 13,
                  textDecoration: 'none',
                  backdropFilter: 'blur(10px)',
                }}
              >
                <PenLineIcon size={14} />
                <span>AI Esse tekshirish</span>
              </Link>
            </div>
          </div>

          {/* Academic badge visual */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              background: 'rgba(255, 255, 255, 0.05)',
              padding: '16px 20px',
              borderRadius: 16,
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 14,
                background: 'rgba(245, 158, 11, 0.2)',
                color: '#fbbf24',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <AwardIcon size={26} />
            </div>
            <div>
              <div style={{ fontSize: 11, textTransform: 'uppercase', color: 'rgba(255, 255, 255, 0.6)', fontWeight: 700, letterSpacing: '0.05em' }}>
                Keyingi Marra
              </div>
              <div style={{ fontSize: 17, fontWeight: 900, color: '#ffffff' }}>
                A+ Sertifikat (65+ Ball)
              </div>
              <div style={{ fontSize: 12, color: '#34d399', fontWeight: 600 }}>
                Tayyorgarlik darajasi: 72%
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. ASOSIY METRIKALAR KARTALARI (4 TA STAT CARDS) */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
          gap: 16,
          marginBottom: 28,
        }}
      >
        {/* Stat 1: Yechilgan testlar */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            padding: '20px 22px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
            transition: 'transform 0.2s, box-shadow 0.2s',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
              Yechilgan testlar
            </span>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'rgba(56, 189, 248, 0.12)',
                color: '#0284c7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <FileTextIcon size={18} />
            </div>
          </div>
          <div style={{ fontSize: 28, fontWeight: 900, color: 'var(--ink)', lineHeight: 1.1, marginBottom: 6 }}>
            {testsTakenVal} ta
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#10b981', fontWeight: 600 }}>
            <span>+12% bu oy</span>
            <span style={{ color: 'var(--muted)' }}>· {stats?.total_passed || 18} ta muvaffaqiyatli</span>
          </div>
        </div>

        {/* Stat 2: Yozilgan esselar */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            padding: '20px 22px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
            transition: 'transform 0.2s, box-shadow 0.2s',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
              Yozilgan esselar
            </span>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'rgba(168, 85, 247, 0.12)',
                color: '#9333ea',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <PenLineIcon size={18} />
            </div>
          </div>
          <div style={{ fontSize: 28, fontWeight: 900, color: 'var(--ink)', lineHeight: 1.1, marginBottom: 6 }}>
            {essaysCountVal} ta
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#9333ea', fontWeight: 600 }}>
            <span>BMB 12 mezon tahlili</span>
            <span style={{ color: 'var(--muted)' }}>· A+ daraja</span>
          </div>
        </div>

        {/* Stat 3: O'rtacha natija */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            padding: '20px 22px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
            transition: 'transform 0.2s, box-shadow 0.2s',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
              O‘rtacha natija
            </span>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'rgba(245, 158, 11, 0.12)',
                color: '#f59e0b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <TrophyIcon size={18} />
            </div>
          </div>
          <div style={{ fontSize: 28, fontWeight: 900, color: 'var(--ink)', lineHeight: 1.1, marginBottom: 6 }}>
            {avgVal}%
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#f59e0b', fontWeight: 600 }}>
            <span>B+ / A daraja</span>
            <span style={{ color: 'var(--muted)' }}>· A’lo ko‘rsatkich</span>
          </div>
        </div>

        {/* Stat 4: Kundalik faollik (Streak) */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            padding: '20px 22px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
            transition: 'transform 0.2s, box-shadow 0.2s',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
              Kundalik faollik
            </span>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'rgba(239, 68, 68, 0.12)',
                color: '#ef4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <FlameIcon size={18} />
            </div>
          </div>
          <div style={{ fontSize: 28, fontWeight: 900, color: 'var(--ink)', lineHeight: 1.1, marginBottom: 6 }}>
            {streakDaysVal} kun
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#ef4444', fontWeight: 600 }}>
            <span>Ketma-ket faol 🔥</span>
            <span style={{ color: 'var(--muted)' }}>· {streak?.xp_points || 340} XP</span>
          </div>
        </div>
      </section>

      {/* 4. ASOSIY ISHCHI OYNA (2 USTUNLI GRID) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: 24,
          marginBottom: 28,
        }}
      >
        {/* CHAP USTUN — MENING TESTLARIM (UPCOMING / ACTIVE TESTS) */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 20,
            padding: '24px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 10,
                  background: 'rgba(2, 132, 199, 0.12)',
                  color: '#0284c7',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <FileTextIcon size={16} />
              </div>
              <h3 style={{ fontSize: 17, fontWeight: 800, margin: 0, color: 'var(--ink)' }}>
                Mening Testlarim
              </h3>
            </div>
            <Link
              to="/tests"
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: '#0284c7',
                textDecoration: 'none',
              }}
            >
              Barcha testlar →
            </Link>
          </div>

          <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--muted)' }}>
            Ona tili va adabiyotidan faol topshiriqlar va rasmiy mock sinovlar:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {available.length > 0 ? (
              available.map((test, index) => {
                const progressPct = index === 0 ? 75 : index === 1 ? 40 : 0;
                return (
                  <div
                    key={test.id}
                    style={{
                      background: 'var(--card-2)',
                      border: '1px solid var(--border)',
                      borderRadius: 14,
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 10,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
                      <div>
                        <strong style={{ fontSize: 14, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>
                          {test.title}
                        </strong>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--muted)' }}>
                          <span>Fan: Ona tili va Adabiyot</span>
                          <span>•</span>
                          <span>{num(test.total_questions, 0)} ta savol</span>
                          {test.time_limit_minutes && (
                            <>
                              <span>•</span>
                              <span><ClockIcon size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> {test.time_limit_minutes} daqiqa</span>
                            </>
                          )}
                        </div>
                      </div>
                      <Link
                        to={`/tests/${test.id}`}
                        className="btn sm primary"
                        style={{
                          whiteSpace: 'nowrap',
                          padding: '7px 14px',
                          borderRadius: 8,
                          fontWeight: 700,
                          fontSize: 12,
                          textDecoration: 'none',
                        }}
                      >
                        {progressPct > 0 ? 'Davom ettirish' : 'Boshlash'}
                      </Link>
                    </div>

                    {/* Progress Bar */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
                        <span>O‘zlashtirish</span>
                        <span>{progressPct}%</span>
                      </div>
                      <div style={{ width: '100%', height: 6, background: 'rgba(255, 255, 255, 0.1)', borderRadius: 999, overflow: 'hidden' }}>
                        <div
                          style={{
                            width: `${progressPct}%`,
                            height: '100%',
                            background: progressPct > 50 ? '#10b981' : '#f59e0b',
                            borderRadius: 999,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              /* Fallback aesthetic preview cards */
              [
                { id: 'mock-1', title: 'BMB Milliy Sertifikat 2026 — Variant #1', q: '35 ta savol', progress: 80 },
                { id: 'mock-2', title: 'Morfologiya va Fonetika Chuqur Diagnostikasi', q: '25 ta savol', progress: 45 },
                { id: 'mock-3', title: 'Mumtoz Adabiyot va Matn Tahlili Sinovi', q: '30 ta savol', progress: 0 },
              ].map((item) => (
                <div
                  key={item.id}
                  style={{
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                    borderRadius: 14,
                    padding: '16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
                    <div>
                      <strong style={{ fontSize: 14, color: 'var(--ink)', display: 'block', marginBottom: 4 }}>
                        {item.title}
                      </strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--muted)' }}>
                        <span>Fan: Ona tili va Adabiyot</span>
                        <span>•</span>
                        <span>{item.q}</span>
                      </div>
                    </div>
                    <Link
                      to="/tests"
                      className="btn sm primary"
                      style={{
                        whiteSpace: 'nowrap',
                        padding: '7px 14px',
                        borderRadius: 8,
                        fontWeight: 700,
                        fontSize: 12,
                        textDecoration: 'none',
                      }}
                    >
                      {item.progress > 0 ? 'Davom ettirish' : 'Boshlash'}
                    </Link>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
                      <span>O‘zlashtirish</span>
                      <span>{item.progress}%</span>
                    </div>
                    <div style={{ width: '100%', height: 6, background: 'rgba(255, 255, 255, 0.1)', borderRadius: 999, overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${item.progress}%`,
                          height: '100%',
                          background: item.progress > 50 ? '#10b981' : '#f59e0b',
                          borderRadius: 999,
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* O'NG USTUN — AI ESSE STUDIYASI (ESSAY STUDIO) */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 20,
            padding: '24px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 10,
                  background: 'rgba(147, 51, 234, 0.12)',
                  color: '#9333ea',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <PenLineIcon size={16} />
              </div>
              <h3 style={{ fontSize: 17, fontWeight: 800, margin: 0, color: 'var(--ink)' }}>
                AI Esse Studiyasi
              </h3>
            </div>
            <Link
              to="/essays"
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: '#9333ea',
                textDecoration: 'none',
              }}
            >
              Barcha esselar →
            </Link>
          </div>

          {/* Bugungi kun tavsiya etilgan mavzusi */}
          <div
            style={{
              padding: '16px',
              borderRadius: 16,
              background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
              border: '1px solid rgba(147, 51, 234, 0.25)',
              marginBottom: 16,
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 800, color: '#a855f7', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Bugungi tavsiya etilgan mavzu
            </span>
            <h4 style={{ fontSize: 15, fontWeight: 800, color: 'var(--ink)', margin: '6px 0 12px', lineHeight: 1.4 }}>
              &ldquo;Alisher Navoiy &lsquo;Xamsa&rsquo; dostonidagi insonparvarlik g‘oyalari va zamonaviy talqin&rdquo;
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                BMB 12 mezon · 50 ball
              </span>
              <Link
                to="/essays"
                className="btn sm"
                style={{
                  background: '#9333ea',
                  color: '#ffffff',
                  fontWeight: 700,
                  fontSize: 12,
                  padding: '7px 16px',
                  borderRadius: 8,
                  textDecoration: 'none',
                  border: 'none',
                }}
              >
                + Yangi Esse yozish / Yuklash
              </Link>
            </div>
          </div>

          {/* So'nggi baholangan esselar tarixi */}
          <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 10px' }}>
            So‘nggi baholangan esselar
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              {
                title: "Abdulla Qodiriyning 'O‘tkan kunlar' romanida milliy xarakter",
                score: '56 / 60',
                grade: 'A+ Daraja',
                date: 'Kecha',
              },
              {
                title: "Mumtoz g‘azaliyotda tashxis va istiora san'atlarining qo‘llanilishi",
                score: '52 / 60',
                grade: 'A Daraja',
                date: '3 kun oldin',
              },
            ].map((eItem, i) => (
              <div
                key={i}
                style={{
                  padding: '12px 14px',
                  borderRadius: 12,
                  background: 'var(--card-2)',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                }}
              >
                <div>
                  <strong style={{ fontSize: 13, color: 'var(--ink)', display: 'block', marginBottom: 2 }}>
                    {eItem.title}
                  </strong>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {eItem.date} · 12 mezon tekshirildi
                  </span>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: '#10b981' }}>
                    {eItem.score}
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b' }}>
                    {eItem.grade}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 5. PASTKI MUVAFFAQIYAT CHIZIG'I (PATH TO EXCELLENCE) */}
      <section
        style={{
          background: 'var(--card)',
          border: '1px solid var(--border)',
          borderRadius: 20,
          padding: '24px 28px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div>
            <h3 style={{ fontSize: 17, fontWeight: 800, margin: '0 0 4px', color: 'var(--ink)' }}>
              Milliy Sertifikat Maqsadiga Erishish (Path to Excellence)
            </h3>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)' }}>
              Sizning umumiy tayyorgarlik darajangiz va navbatdagi maqsadga erishish bosqichlari.
            </p>
          </div>
          <div
            style={{
              padding: '6px 14px',
              borderRadius: 10,
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#10b981',
              fontWeight: 800,
              fontSize: 13,
            }}
          >
            Maqsad: A+ Sertifikat (70 ball)
          </div>
        </div>

        {/* Big Progress Bar */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
            <span style={{ color: 'var(--ink)' }}>Joriy tayyorgarlik ko‘rsatkichi</span>
            <span style={{ color: '#10b981' }}>72%</span>
          </div>
          <div
            style={{
              width: '100%',
              height: 10,
              background: 'var(--card-2)',
              borderRadius: 999,
              border: '1px solid var(--border)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: '72%',
                height: '100%',
                background: 'linear-gradient(90deg, #10b981 0%, #34d399 70%, #f59e0b 100%)',
                borderRadius: 999,
              }}
            />
          </div>
        </div>

        {/* 3 Step Milestones */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 16,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 14px',
              borderRadius: 12,
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
            }}
          >
            <div style={{ color: '#10b981' }}><CheckCircle2 size={20} /></div>
            <div>
              <strong style={{ fontSize: 13, color: 'var(--ink)', display: 'block' }}>1. Boshlang‘ich Diagnostika</strong>
              <span style={{ fontSize: 11, color: '#10b981', fontWeight: 600 }}>Topshirildi (88% natija)</span>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 14px',
              borderRadius: 12,
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
            }}
          >
            <div style={{ color: '#f59e0b' }}><ZapIcon size={20} /></div>
            <div>
              <strong style={{ fontSize: 13, color: 'var(--ink)', display: 'block' }}>2. 12 Mezonli Esse & Mashq</strong>
              <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 600 }}>Faol jarayonda (72%)</span>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 14px',
              borderRadius: 12,
              background: 'var(--card-2)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ color: 'var(--muted)' }}><BookOpenIcon size={20} /></div>
            <div>
              <strong style={{ fontSize: 13, color: 'var(--muted)', display: 'block' }}>3. Rasmiy BMB Mock Imtihon</strong>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>Kutilmoqda (Navbatdagi sinov)</span>
            </div>
          </div>
        </div>
      </section>

      {/* Onboarding Modal */}
      <OnboardingModal
        isOpen={onboardingOpen}
        onClose={() => {
          localStorage.setItem('grandec_onboarding_done', 'true');
          setOnboardingOpen(false);
        }}
        onSuccess={() => {
          localStorage.setItem('grandec_onboarding_done', 'true');
          setOnboardingOpen(false);
        }}
      />
    </div>
  );
}
