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
  isPlatformAdmin,
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
  SwordsIcon,
  TrophyIcon,
  ZapIcon,
} from '../components/icons';
import OnboardingModal from '../components/OnboardingModal';
import CardPaymentModal from '../components/CardPaymentModal';
import FeedbackModal from '../components/FeedbackModal';
import ReferralCard from '../components/ReferralCard';

interface Stats {
  total_tests_taken?: number;
  total_passed?: number;
  total_failed?: number;
  average_percentage?: number;
  best_percentage?: number;
  total_time_spent_seconds?: number;
  total_essays_submitted?: number;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();

  const [stats, setStats] = useState<Stats | null>(null);
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [available, setAvailable] = useState<TestListItem[]>([]);
  const [, setRecent] = useState<ResultListItem[]>([]);
  const [, setErr] = useState<string | null>(null);
  const [, setLoading] = useState(true);
  const [, setTuition] = useState<TuitionOverview | null>(null);
  const [pendingReceipt, setPendingReceipt] = useState<PaymentReceiptItem | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [cardPaymentOpen, setCardPaymentOpen] = useState(false);
  const [streak, setStreak] = useState<StreakInfoResponse | null>(null);
  const [, setVaultStats] = useState<{ unresolved_count: number; weak_topics: { topic: string; error_count: number }[] } | null>(null);

  const role = (user?.role || '').toLowerCase();
  const isTeacherOrAdmin =
    role === 'teacher' ||
    role === 'admin' ||
    role === 'superadmin' ||
    role === 'center_admin' ||
    Boolean(user?.is_superuser);
  const isStudent = !isTeacherOrAdmin;

  useEffect(() => {
    if (!isStudent) {
      setOnboardingOpen(false);
      return;
    }
    const isDismissed = localStorage.getItem('onboarding_dismissed') === 'true';
    const isDone = localStorage.getItem('grandec_onboarding_done') === 'true';
    if (isDismissed || isDone || user?.onboarding_completed === true) {
      setOnboardingOpen(false);
      return;
    }
    if (user && user.onboarding_completed === false) {
      setOnboardingOpen(true);
    }
  }, [user, isStudent]);

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
    : 0;
  const testsTakenVal = stats?.total_tests_taken ?? 0;
  const streakDaysVal = streak?.current_streak ?? 0;
  const essaysCountVal = stats?.total_essays_submitted ?? 0;

  const userDisplayName = user?.full_name || t('dashboard.default_student_name', 'Hurmatli O‘quvchi');
  const isEnglishSubject = user?.active_subject === 'english' || (typeof window !== 'undefined' && localStorage.getItem('lms_subject') === 'english');

  return (
    <div className="dash-container pt-2 sm:pt-4" style={{ maxWidth: 1240, margin: '0 auto', overflowX: 'hidden' }}>
      {/* 1. YUQORI SARLAVHA (HEADER) */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
          padding: '4px 0 20px',
          borderBottom: '1px solid var(--border)',
          marginBottom: 20,
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 'clamp(1.3rem, 4vw, 1.95rem)',
              fontWeight: 800,
              color: 'var(--ink)',
              margin: '0 0 4px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              letterSpacing: '-0.02em',
            }}
          >
            <span>{t('dashboard.welcome', 'Xush kelibsiz')}, {userDisplayName}!</span>
            <span style={{ fontSize: '1.25rem' }}>✨</span>
          </h1>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)', fontWeight: 500 }}>
            {t('dashboard.subtitle', 'Bilimingizni charxlang va Milliy Sertifikatga ishonch bilan tayyorlaning.')}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Joriy tarif ko'rsatkichi */}
          {isPlatformAdmin(user) ? (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                borderRadius: 999,
                background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.2) 0%, rgba(217, 119, 6, 0.15) 100%)',
                border: '1px solid rgba(168, 85, 247, 0.4)',
                color: '#c084fc',
                fontWeight: 800,
                fontSize: 12,
              }}
            >
              <span>{t('dashboard.admin_badge', '👑 Tizim Administratori (Root Access)')}</span>
            </div>
          ) : user?.is_paid && user?.plan && user?.plan.toUpperCase() !== 'FREE' ? (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 999,
                background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.08) 100%)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                color: '#f59e0b',
                fontWeight: 700,
                fontSize: 12,
              }}
            >
              <CrownIcon size={14} style={{ color: '#f59e0b' }} />
              <span>{t('dashboard.tariff_label', 'Tarif')}: <strong>{user.plan.toUpperCase()}</strong></span>
            </div>
          ) : (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  borderRadius: 999,
                  background: 'rgba(148, 163, 184, 0.12)',
                  border: '1px solid rgba(148, 163, 184, 0.25)',
                  color: 'var(--muted)',
                  fontWeight: 600,
                  fontSize: 12,
                }}
              >
                <span>{t('dashboard.tariff_label', 'Tarif')}: <strong>{t('dashboard.tariff_free', 'BEPUL')}</strong></span>
              </div>
              <button
                type="button"
                onClick={() => setCardPaymentOpen(true)}
                className="btn sm"
                style={{
                  fontSize: 11.5,
                  padding: '5px 12px',
                  fontWeight: 700,
                  background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: 8,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  boxShadow: '0 2px 6px rgba(217, 119, 6, 0.25)',
                }}
              >
                <ZapIcon size={13} />
                <span>{t('dashboard.activate_sub', 'Obunani faollashtirish')}</span>
              </button>
            </div>
          )}

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
            padding: '12px 16px',
            borderRadius: 16,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>⏳</span>
            <div>
              <strong style={{ color: '#fbbf24', fontSize: 13 }}>{t('dashboard.pending_receipt_title', 'To‘lov kvitansiyasi tekshirilmoqda')}</strong>
              <p style={{ margin: 0, fontSize: 11, color: '#fde68a' }}>
                {pendingReceipt.plan.toUpperCase()} {t('dashboard.pending_receipt_desc', 'tarifi tasdiqlanishi kutilmoqda.')}
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
              padding: '6px 12px',
              borderRadius: 8,
              textDecoration: 'none',
            }}
          >
            {t('dashboard.view_status', 'Holatni ko‘rish')}
          </Link>
        </div>
      )}

      {/* 2. ILHOMLANTIRUVCHI BOSH BANNER (WARM LUXURY LIGHT CARD) */}
      <section className="dash-hero-banner">
        {/* Soft amber radial glow */}
        <div
          style={{
            position: 'absolute',
            top: -30,
            right: -30,
            width: 200,
            height: 200,
            background: 'radial-gradient(circle, rgba(245, 158, 11, 0.15) 0%, transparent 70%)',
            filter: 'blur(30px)',
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
            gap: 16,
          }}
        >
          <div style={{ maxWidth: 640, width: '100%' }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 999,
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                color: '#B45309',
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: '0.04em',
                marginBottom: 8,
              }}
            >
              <SparklesIcon size={12} />
              <span>{t('dashboard.quote_title', 'KUN HIKMATI VA MOTIVATSIYA')}</span>
            </div>
            <h2
              className="dash-hero-title"
              style={{
                fontSize: '15px',
                fontWeight: 700,
                margin: '0 0 6px',
                lineHeight: 1.45,
              }}
            >
              &ldquo;{t('dashboard.quote_text', 'Ilm — o‘rganish bilan, yuksak natija esa uzluksiz intilish bilan qo‘lga kiritiladi.')}&rdquo;
            </h2>
            <p
              className="dash-hero-desc"
              style={{
                margin: '0 0 16px',
                fontSize: 13,
                lineHeight: 1.5,
              }}
            >
              {t('dashboard.hero_desc', 'BMB Milliy Sertifikat 2026 standarti bo‘yicha yangilangan rasmiy mock test va 12 mezonli AI esse topshirig‘i sizni kutmoqda.')}
            </p>
            <div className="dash-hero-actions" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              {isTeacherOrAdmin ? (
                <>
                  <Link
                    to="/tests/create"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 20px',
                      borderRadius: 14,
                      background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                      color: '#FFFFFF',
                      fontWeight: 800,
                      fontSize: 13.5,
                      textDecoration: 'none',
                      boxShadow: '0 4px 14px rgba(217, 119, 6, 0.35)',
                      minHeight: 44,
                      cursor: 'pointer',
                      border: 'none',
                    }}
                  >
                    <span>✍️</span>
                    <span>{t('dashboard.new_test_smart', '+ Yangi test yaratish (Smart Paste)')}</span>
                  </Link>
                  <Link
                    to="/teacher"
                    className="dash-hero-btn-secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 18px',
                      borderRadius: 14,
                      fontWeight: 700,
                      fontSize: 13,
                      textDecoration: 'none',
                      minHeight: 44,
                    }}
                  >
                    <span>{t('dashboard.students_groups', '👥 O‘quvchilar va Guruhlar')}</span>
                    <span style={{ fontSize: 15, color: '#D97706' }}>→</span>
                  </Link>
                  <Link
                    to="/essays"
                    className="dash-hero-btn-secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 16px',
                      borderRadius: 14,
                      fontWeight: 700,
                      fontSize: 13,
                      textDecoration: 'none',
                      minHeight: 44,
                    }}
                  >
                    <PenLineIcon size={14} color="#D97706" />
                    <span>{t('dashboard.check_essay_teacher', 'AI Esse tekshiruvi')}</span>
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    to="/tests"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 22px',
                      borderRadius: 14,
                      background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                      color: '#FFFFFF',
                      fontWeight: 800,
                      fontSize: 13.5,
                      textDecoration: 'none',
                      boxShadow: '0 4px 14px rgba(217, 119, 6, 0.35)',
                      minHeight: 44,
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    <ZapIcon size={16} />
                    <span>{t('dashboard.cta_mock', '⚡️ BMB Mock Test topshirish')}</span>
                  </Link>
                  <Link
                    to="/essays"
                    className="dash-hero-btn-secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 18px',
                      borderRadius: 14,
                      fontWeight: 700,
                      fontSize: 13,
                      textDecoration: 'none',
                      minHeight: 44,
                    }}
                  >
                    <PenLineIcon size={15} color="#D97706" />
                    <span>{t('dashboard.cta_essay', '✍️ AI Esse tekshirtirish')}</span>
                  </Link>
                  <Link
                    to="/arena"
                    className="dash-hero-btn-secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 18px',
                      borderRadius: 14,
                      fontWeight: 700,
                      fontSize: 13,
                      textDecoration: 'none',
                      minHeight: 44,
                    }}
                  >
                    <SwordsIcon size={15} color="#D97706" />
                    <span>{t('dashboard.cta_arena', '⚔️ 1v1 Arena bellashuvi')}</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => setFeedbackModalOpen(true)}
                    className="dash-hero-btn-secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '11px 18px',
                      borderRadius: 14,
                      fontWeight: 700,
                      fontSize: 13,
                      minHeight: 44,
                      cursor: 'pointer',
                      border: '1px solid rgba(245, 158, 11, 0.4)',
                      background: 'rgba(245, 158, 11, 0.08)',
                    }}
                  >
                    <span>💬</span>
                    <span>{t('dashboard.feedback', 'Fikr yoki taklif')}</span>
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Academic badge visual */}
          <div
            className="dash-hero-badge-wrap"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '14px 18px',
              borderRadius: 16,
            }}
          >
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#D97706',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <AwardIcon size={24} />
            </div>
            <div>
              <div style={{ fontSize: 10.5, textTransform: 'uppercase', color: '#64748B', fontWeight: 800, letterSpacing: '0.06em' }}>
                {t('dashboard.next_milestone', 'Keyingi Marra')}
              </div>
              <div style={{ fontSize: 15, fontWeight: 900, color: '#0F172A' }}>
                {t('dashboard.next_target', 'A+ Sertifikat (65+ Ball)')}
              </div>
              <div style={{ fontSize: 12, color: '#059669', fontWeight: 700 }}>
                {t('dashboard.prep_level', 'Tayyorgarlik darajasi: 72%')}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2.05 PRO OBUNA TUGASHIGA OGOHLANTIRISH BANNERI */}
      {user?.is_expiring_soon && (
        <div
          style={{
            marginBottom: 20,
            padding: '16px 20px',
            borderRadius: 16,
            background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(245, 158, 11, 0.12) 100%)',
            border: '1.5px solid rgba(239, 68, 68, 0.4)',
            boxShadow: '0 8px 24px rgba(239, 68, 68, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: 'rgba(239, 68, 68, 0.2)',
                color: '#EF4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 22,
                flexShrink: 0,
              }}
            >
              ⚠️
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 900,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    padding: '2px 8px',
                    borderRadius: 6,
                    background: '#EF4444',
                    color: '#FFFFFF',
                  }}
                >
                  {t('dashboard.expiry_alert_badge', 'Obuna Ogohlantirishi')}
                </span>
                <span style={{ fontSize: 13, fontWeight: 800, color: '#DC2626' }}>
                  {t('dashboard.expiry_days_left', `PRO obunangiz tugashiga ${user?.days_until_expiration || 1} kun qoldi!`)}
                </span>
              </div>
              <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748B', fontWeight: 500 }}>
                {t('dashboard.expiry_desc', "Uzluksiz ta'lim olish va sun'iy intellekt xizmatlaridan foydalanishda davom etish uchun obunani yangilang.")}
              </p>
            </div>
          </div>
          <Link
            to="/subscribe"
            className="btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 20px',
              borderRadius: 12,
              background: 'linear-gradient(135deg, #EF4444, #DC2626)',
              color: '#FFFFFF',
              fontWeight: 800,
              fontSize: 13,
              textDecoration: 'none',
              boxShadow: '0 4px 14px rgba(239, 68, 68, 0.35)',
              whiteSpace: 'nowrap',
            }}
          >
            <span>💳</span>
            <span>{t('dashboard.expiry_renew_btn', 'Obunani yangilash')}</span>
          </Link>
        </div>
      )}

      {/* 2.1 BO'SH HOLAT UCHUN ILHOMLANTIRUVCHI BANNER (0-STATE) */}
      {testsTakenVal === 0 && essaysCountVal === 0 && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(147, 51, 234, 0.05) 100%)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            borderRadius: 20,
            padding: '20px 24px',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ maxWidth: 650 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 22 }}>🚀</span>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: 'var(--ink)' }}>
                {t('dashboard.first_step_title', "Grand Education platformasiga xush kelibsiz!")}
              </h3>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)', lineHeight: 1.5 }}>
              {t('dashboard.first_step_desc', "Siz hali birorta ham test topshirmadingiz. O'z bilim darajangizni aniqlash uchun birinchi sinovni boshlang!")}
            </p>
          </div>
          <Link
            to="/tests"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '11px 22px',
              borderRadius: 14,
              background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: 13.5,
              textDecoration: 'none',
              boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)',
              whiteSpace: 'nowrap',
            }}
          >
            <span>🚀</span>
            <span>{t('dashboard.start_first_test', "Boshlang'ich testni yechish")}</span>
          </Link>
        </div>
      )}

      {/* 3. ASOSIY METRIKALAR KARTALARI (2x2 Grid on Mobile, 4-col on Desktop) */}
      <section
        className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
          marginBottom: 20,
        }}
      >
        {/* Stat 1: Yechilgan testlar */}
        <div
          className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-all hover:shadow-md flex flex-col justify-between"
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            minHeight: 135,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted, #64748b)' }}>
                {t('dashboard.metric_tests', 'Yechilgan testlar')}
              </span>
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'rgba(56, 189, 248, 0.12)',
                  color: '#0284c7',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <FileTextIcon size={17} />
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '6px 0 2px' }}>
              <span style={{ fontSize: 24, fontWeight: 800, color: 'var(--ink)', lineHeight: 1.2 }}>
                {testsTakenVal}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
                {t('dashboard.unit_item', 'ta')}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#10b981', fontWeight: 600, flexWrap: 'wrap', marginTop: 4 }}>
            {testsTakenVal > 0 ? (
              <>
                <span>{stats?.total_passed ?? 0} {t('dashboard.passed_label', 'ta o‘tgan')}</span>
                <span style={{ color: 'var(--muted)' }}>· {testsTakenVal - (stats?.total_passed ?? 0)} {t('dashboard.failed_label', "ta o'tmagan")}</span>
              </>
            ) : (
              <span style={{ color: 'var(--muted)' }}>{t('dashboard.no_tests_yet', 'Hali test topshirilmagan')}</span>
            )}
          </div>
        </div>

        {/* Stat 2: Yozilgan esselar */}
        <div
          className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-all hover:shadow-md flex flex-col justify-between"
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            minHeight: 135,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted, #64748b)' }}>
                {t('dashboard.metric_essays', 'Yozilgan esselar')}
              </span>
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'rgba(168, 85, 247, 0.12)',
                  color: '#9333ea',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <PenLineIcon size={17} />
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '6px 0 2px' }}>
              <span style={{ fontSize: 24, fontWeight: 800, color: 'var(--ink)', lineHeight: 1.2 }}>
                {essaysCountVal}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
                {t('dashboard.unit_item', 'ta')}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#9333ea', fontWeight: 600, flexWrap: 'wrap', marginTop: 4 }}>
            {essaysCountVal > 0 ? (
              <>
                <span>{t('dashboard.bmb_criteria', 'BMB 12 mezon')}</span>
                <span style={{ color: 'var(--muted)' }}>· {t('dashboard.ai_analysis', 'AI tahlili')}</span>
              </>
            ) : (
              <span style={{ color: 'var(--muted)' }}>{t('dashboard.no_essays_yet', 'Hali esse yozilmagan')}</span>
            )}
          </div>
        </div>

        {/* Stat 3: O'rtacha natija */}
        <div
          className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-all hover:shadow-md flex flex-col justify-between"
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            minHeight: 135,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted, #64748b)' }}>
                {t('dashboard.metric_avg', 'O‘rtacha natija')}
              </span>
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'rgba(245, 158, 11, 0.12)',
                  color: '#f59e0b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <TrophyIcon size={17} />
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 2, margin: '6px 0 2px' }}>
              <span style={{ fontSize: 24, fontWeight: 800, color: 'var(--ink)', lineHeight: 1.2 }}>
                {avgVal}
              </span>
              <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>
                %
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#f59e0b', fontWeight: 600, flexWrap: 'wrap', marginTop: 4 }}>
            {testsTakenVal > 0 ? (
              <>
                <span>{avgVal >= 70 ? t('dashboard.high_score', 'A / A+ Yuqori daraja') : avgVal >= 50 ? t('dashboard.good_score', 'B / B+ Yaxshi daraja') : t('dashboard.needs_prep', 'Tayyorgarlik talab etiladi')}</span>
              </>
            ) : (
              <span style={{ color: 'var(--muted)' }}>{t('dashboard.no_result_yet', 'Sinov natijasi yo‘q')}</span>
            )}
          </div>
        </div>

        {/* Stat 4: Kundalik faollik (Streak) */}
        <div
          className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-all hover:shadow-md flex flex-col justify-between"
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 18,
            minHeight: 135,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted, #64748b)' }}>
                {t('dashboard.metric_streak', 'Kundalik faollik')}
              </span>
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'rgba(239, 68, 68, 0.12)',
                  color: '#ef4444',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <FlameIcon size={17} />
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '6px 0 2px' }}>
              <span style={{ fontSize: 24, fontWeight: 800, color: 'var(--ink)', lineHeight: 1.2 }}>
                {streakDaysVal}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
                {t('dashboard.unit_days', 'kun')}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#ef4444', fontWeight: 600, flexWrap: 'wrap', marginTop: 4 }}>
            <span>{t('dashboard.streak_streak', 'Ketma-ket')} 🔥</span>
            <span style={{ color: 'var(--muted)' }}>· {streak?.xp_points ?? 0} XP</span>
          </div>
        </div>
      </section>

      {/* 3.1 REFERAL VA MUKOFOT BLOKI (IXCHAM KARTA) */}
      <ReferralCard />

      {/* 4. ASOSIY ISHCHI OYNA (1-col on Mobile, 2-col on Desktop) */}
      <div className="dash-main-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 24, marginBottom: 24 }}>
        {/* CHAP USTUN — MENING TESTLARIM (UPCOMING / ACTIVE TESTS) */}
        <div
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 20,
            padding: '22px 20px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 9,
                  background: 'rgba(2, 132, 199, 0.12)',
                  color: '#0284c7',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <FileTextIcon size={15} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0, color: 'var(--ink)' }}>
                {t('my_tests', t('dashboard.my_tests', 'Mening Testlarim'))}
              </h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {isTeacherOrAdmin && (
                <Link
                  to="/tests/create"
                  style={{
                    fontSize: 12,
                    fontWeight: 800,
                    color: '#D97706',
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    borderRadius: 8,
                    padding: '4px 10px',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>✍️</span> {t('dashboard.add_test', '+ Test qo‘shish')}
                </Link>
              )}
              <Link
                to="/tests"
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: '#0284c7',
                  textDecoration: 'none',
                }}
              >
                {t('dashboard.view_all', 'Barchasi')} →
              </Link>
            </div>
          </div>

          <p style={{ margin: '0 0 14px', fontSize: 12, color: 'var(--muted)' }}>
            {t('dashboard.my_tests_desc', 'Ona tili va adabiyotidan faol topshiriqlar va rasmiy mock sinovlar:')}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                  >
                    <div className="dash-test-item-row" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                      <div style={{ flex: 1, minWidth: 180 }}>
                        <strong style={{ fontSize: 13.5, color: 'var(--ink)', display: 'block', marginBottom: 4, fontWeight: 700 }}>
                          {test.title}
                        </strong>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--muted)', flexWrap: 'wrap' }}>
                          <span>{isEnglishSubject ? t('dashboard.subject_english', 'Ingliz tili (CEFR / IELTS)') : t('dashboard.subject_label', 'Ona tili va Adabiyot')}</span>
                          <span>•</span>
                          <span>{num(test.total_questions, 0)} {t('dashboard.unit_questions', 'ta savol')}</span>
                          {test.time_limit_minutes && (
                            <>
                              <span>•</span>
                              <span><ClockIcon size={11} style={{ display: 'inline', verticalAlign: 'middle' }} /> {test.time_limit_minutes} {t('dashboard.unit_minutes', 'daqiqa')}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <Link
                        to={`/tests/${test.id}`}
                        className="dash-test-btn"
                        style={{
                          whiteSpace: 'nowrap',
                          padding: '9px 18px',
                          borderRadius: 10,
                          fontWeight: 800,
                          fontSize: 12.5,
                          textDecoration: 'none',
                          minHeight: 40,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                          color: '#FFFFFF',
                          boxShadow: '0 2px 8px rgba(217, 119, 6, 0.25)',
                          border: 'none',
                        }}
                      >
                        {progressPct > 0 ? t('dashboard.continue', 'Davom ettirish') : t('dashboard.start', 'Boshlash')}
                      </Link>
                    </div>

                    {/* Progress Bar */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: 3 }}>
                        <span>{t('dashboard.mastery', 'O‘zlashtirish')}</span>
                        <span>{progressPct}%</span>
                      </div>
                      <div style={{ width: '100%', height: 5, background: 'rgba(255, 255, 255, 0.1)', borderRadius: 999, overflow: 'hidden' }}>
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
              (isEnglishSubject ? [
                { id: 'mock-1', title: 'CEFR Multi-Level Mock Exam #1 (Full Exam)', q: '75 questions', progress: 0 },
                { id: 'mock-2', title: 'IELTS Academic Reading & Listening Practice', q: '40 questions', progress: 0 },
                { id: 'mock-3', title: 'English Grammar & Advanced Vocabulary Diagnostic', q: '30 questions', progress: 0 },
              ] : [
                { id: 'mock-1', title: 'BMB Milliy Sertifikat 2026 — Variant #1', q: '35 ta savol', progress: 80 },
                { id: 'mock-2', title: 'Morfologiya va Fonetika Chuqur Diagnostikasi', q: '25 ta savol', progress: 45 },
                { id: 'mock-3', title: 'Mumtoz Adabiyot va Matn Tahlili Sinovi', q: '30 ta savol', progress: 0 },
              ]).map((item) => (
                <div
                  key={item.id}
                  style={{
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                    borderRadius: 14,
                    padding: '14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 180 }}>
                      <strong style={{ fontSize: 13, color: 'var(--ink)', display: 'block', marginBottom: 3 }}>
                        {item.title}
                      </strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--muted)' }}>
                        <span>{isEnglishSubject ? t('dashboard.subject_english', 'Ingliz tili (CEFR / IELTS)') : t('dashboard.subject_label', 'Ona tili va Adabiyot')}</span>
                        <span>•</span>
                        <span>{item.q}</span>
                      </div>
                    </div>
                    <Link
                      to="/tests"
                      className="btn sm primary"
                      style={{
                        whiteSpace: 'nowrap',
                        padding: '8px 16px',
                        borderRadius: 9,
                        fontWeight: 700,
                        fontSize: 12,
                        textDecoration: 'none',
                        minHeight: 38,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {item.progress > 0 ? t('dashboard.continue', 'Davom ettirish') : t('dashboard.start', 'Boshlash')}
                    </Link>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: 3 }}>
                      <span>{t('dashboard.mastery', 'O‘zlashtirish')}</span>
                      <span>{item.progress}%</span>
                    </div>
                    <div style={{ width: '100%', height: 5, background: 'rgba(255, 255, 255, 0.1)', borderRadius: 999, overflow: 'hidden' }}>
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
            padding: '22px 20px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 9,
                  background: 'rgba(147, 51, 234, 0.12)',
                  color: '#9333ea',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <PenLineIcon size={15} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0, color: 'var(--ink)' }}>
                {t('ai_essay_studio', t('dashboard.essay_studio', 'AI Esse Studiyasi'))}
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
              {t('dashboard.view_all', 'Barchasi')} →
            </Link>
          </div>

          {/* Bugungi kun tavsiya etilgan mavzusi */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 16,
              background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
              border: '1px solid rgba(147, 51, 234, 0.25)',
              marginBottom: 14,
            }}
          >
            <span style={{ fontSize: 10, fontWeight: 800, color: '#a855f7', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {t('dashboard.today_topic_tag', 'Bugungi tavsiya etilgan mavzu')}
            </span>
            <h4 style={{ fontSize: 14, fontWeight: 800, color: 'var(--ink)', margin: '4px 0 10px', lineHeight: 1.4 }}>
              {isEnglishSubject
                ? t('dashboard.today_topic_en', 'Some people believe that university education should be free for everyone. Discuss both views and give your opinion.')
                : t('dashboard.today_topic_title', 'Alisher Navoiy “Xamsa” dostonidagi insonparvarlik g‘oyalari va zamonaviy talqin').replace(/^["“«\s]+|["”»\s]+$/g, '')}
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                {isEnglishSubject ? t('dashboard.essay_rubric_en', 'IELTS Task 2 · Band 9.0 Rubric') : t('dashboard.today_topic_meta', 'BMB 12 mezon · 50 ball')}
              </span>
              <Link
                to="/essays"
                className="btn sm"
                style={{
                  background: '#9333ea',
                  color: '#ffffff',
                  fontWeight: 700,
                  fontSize: 12,
                  padding: '8px 16px',
                  borderRadius: 9,
                  textDecoration: 'none',
                  border: 'none',
                  minHeight: 38,
                  display: 'inline-flex',
                  alignItems: 'center',
                }}
              >
                {t('dashboard.write_essay_cta', '+ Yangi Esse yozish / Yuklash')}
              </Link>
            </div>
          </div>

          {/* So'nggi baholangan esselar tarixi */}
          <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 8px' }}>
            {t('dashboard.recent_essays', 'So‘nggi baholangan esselar')}
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(isEnglishSubject ? [
              {
                title: "Discuss the advantages and disadvantages of artificial intelligence in education",
                score: 'Band 7.5',
                grade: 'CEFR C1',
                date: t('dashboard.yesterday', 'Kecha'),
              },
              {
                title: "Should governments invest more in public transportation or road infrastructure?",
                score: 'Band 7.0',
                grade: 'CEFR B2',
                date: t('dashboard.days_ago', '3 kun oldin'),
              },
            ] : [
              {
                title: "Abdulla Qodiriyning 'O‘tkan kunlar' romanida milliy xarakter",
                score: '56 / 60',
                grade: 'A+ Daraja',
                date: t('dashboard.yesterday', 'Kecha'),
              },
              {
                title: "Mumtoz g‘azaliyotda tashxis va istiora san'atlarining qo‘llanilishi",
                score: '52 / 60',
                grade: 'A Daraja',
                date: t('dashboard.days_ago', '3 kun oldin'),
              },
            ]).map((eItem, i) => (
              <div
                key={i}
                style={{
                  padding: '10px 12px',
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
                  <strong style={{ fontSize: 12, color: 'var(--ink)', display: 'block', marginBottom: 2 }}>
                    {eItem.title}
                  </strong>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {eItem.date} · {t('dashboard.criteria_checked', '12 mezon tekshirildi')}
                  </span>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: '#10b981' }}>
                    {eItem.score}
                  </div>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#f59e0b' }}>
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
          padding: '22px 20px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 10,
            marginBottom: 14,
          }}
        >
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 800, margin: '0 0 3px', color: 'var(--ink)' }}>
              {t('dashboard.path_title', 'Milliy Sertifikat Maqsadiga Erishish (Path to Excellence)')}
            </h3>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
              {t('dashboard.path_subtitle', 'Umumiy tayyorgarlik darajangiz va navbatdagi maqsadga erishish bosqichlari.')}
            </p>
          </div>
          <div
            style={{
              padding: '5px 12px',
              borderRadius: 8,
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#10b981',
              fontWeight: 800,
              fontSize: 12,
            }}
          >
            {t('dashboard.target_badge', 'Maqsad: A+ Sertifikat (70 ball)')}
          </div>
        </div>

        {/* Big Progress Bar */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, marginBottom: 5 }}>
            <span style={{ color: 'var(--ink)' }}>{t('dashboard.readiness_indicator', 'Joriy tayyorgarlik ko‘rsatkichi')}</span>
            <span style={{ color: '#10b981' }}>72%</span>
          </div>
          <div
            style={{
              width: '100%',
              height: 8,
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
        <div className="dash-milestones-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '12px',
              borderRadius: 12,
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
            }}
          >
            <div style={{ color: '#10b981', flexShrink: 0 }}><CheckCircle2 size={18} /></div>
            <div>
              <strong style={{ fontSize: 12, color: 'var(--ink)', display: 'block' }}>{t('dashboard.step1_title', '1. Boshlang‘ich Diagnostika')}</strong>
              <span style={{ fontSize: 11, color: '#10b981', fontWeight: 600 }}>{t('dashboard.step1_desc', 'Topshirildi (88% natija)')}</span>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '12px',
              borderRadius: 12,
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
            }}
          >
            <div style={{ color: '#f59e0b', flexShrink: 0 }}><ZapIcon size={18} /></div>
            <div>
              <strong style={{ fontSize: 12, color: 'var(--ink)', display: 'block' }}>{t('dashboard.step2_title', '2. 12 Mezonli Esse & Mashq')}</strong>
              <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 600 }}>{t('dashboard.step2_desc', 'Faol jarayonda (72%)')}</span>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '12px',
              borderRadius: 12,
              background: 'var(--card-2)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ color: 'var(--muted)', flexShrink: 0 }}><BookOpenIcon size={18} /></div>
            <div>
              <strong style={{ fontSize: 12, color: 'var(--muted)', display: 'block' }}>{t('dashboard.step3_title', '3. Rasmiy BMB Mock Imtihon')}</strong>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>{t('dashboard.step3_desc', 'Kutilmoqda (Navbatdagi sinov)')}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Onboarding Modal */}
      {isStudent && (
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
      )}
      <CardPaymentModal
        isOpen={cardPaymentOpen}
        onClose={() => setCardPaymentOpen(false)}
      />
      <FeedbackModal
        isOpen={feedbackModalOpen}
        onClose={() => setFeedbackModalOpen(false)}
      />
    </div>
  );
}
