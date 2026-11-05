import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import {
  AuthExpiredError,
  DashboardApi,
  PaymentsApi,
  type DashboardData,
  type DashboardRecent,
  type DashboardWeakPart,
  type PaymentReceiptItem,
} from '../lib/api';
import { formatDisplayName } from '../lib/displayName';
import { essayKind, essayStatus, scoreLabel } from '../lib/essays';
import { useSubject } from '../lib/useSubject';
import { daysLeft, useEntitlement, useTier } from '../lib/useTier';
import OnboardingModal from '../components/OnboardingModal';
import PlanBadge from '../components/PlanBadge';
import ReferralCard from '../components/ReferralCard';

function getStoredPlan(): Record<string, unknown> {
  try {
    const raw = localStorage.getItem('grandec_user_plan');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown>;
    }
  } catch {
    /* ignore */
  }
  return {};
}

function resolveTrackBadge(userExamTarget?: string, storedPlan?: Record<string, unknown>, subject?: string): string {
  const target = String(userExamTarget || storedPlan?.target_exam || storedPlan?.exam_target || storedPlan?.target || '');
  const sub = String(storedPlan?.sub_subject || '');
  if (target === 'milliy_sertifikat' || target === 'national_certificate') return '🇺🇿 Milliy Sertifikat';
  if (target === 'cefr' || target === 'multilevel') return '🇬🇧 CEFR Multi-level';
  if (target === 'ielts') return '🎓 IELTS Academic';
  if (target === 'attestatsiya' || target === 'attestation') return '📜 Attestatsiya 2026';
  if (target === 'other') return sub ? `📚 ${sub}` : '📚 Umumiy fanlar';
  return subject === 'english' ? '🇬🇧 Ingliz tili (CEFR / IELTS)' : '🇺🇿 Ona tili (Milliy sertifikat)';
}

/** Student dashboard: one main action, daily goal, real indicators, recent results, weak parts, goal. */
export default function Dashboard() {
  const { user } = useAuth();
  const { t, lang } = useLang();
  const navigate = useNavigate();
  const subject = useSubject();
  const tier = useTier();
  const entitlement = useEntitlement();

  const [data, setData] = useState<DashboardData | null>(null);
  const [failed, setFailed] = useState(false);
  const [pendingReceipt, setPendingReceipt] = useState<PaymentReceiptItem | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  const role = (user?.role || '').toLowerCase();
  const isStudent = !(role === 'teacher' || role === 'admin' || role === 'superadmin' || role === 'center_admin' || user?.is_superuser);

  useEffect(() => {
    if (!isStudent || !user) {
      setOnboardingOpen(false);
      return;
    }
    const done =
      localStorage.getItem('onboarding_dismissed') === 'true' ||
      localStorage.getItem('grandec_onboarding_done') === 'true' ||
      localStorage.getItem('grand_ed_onboarding_done') === 'true' ||
      user.onboarding_completed === true;
    setOnboardingOpen(!done && user.onboarding_completed === false);
  }, [user, isStudent]);

  useEffect(() => {
    let alive = true;
    PaymentsApi.myReceipts()
      .then(({ results }) => alive && setPendingReceipt(results.find((r) => r.status === 'pending') ?? null))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [user?.id]);

  const load = useCallback(() => {
    let alive = true;
    setFailed(false);
    DashboardApi.get(subject)
      .then((d) => alive && setData(d))
      .catch((e) => {
        if (!alive) return;
        if (e instanceof AuthExpiredError) navigate('/login');
        else setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [subject, navigate]);

  useEffect(() => {
    setData(null);
    return load();
  }, [load]);

  const name = formatDisplayName(user?.full_name, user?.email) || t('user_default');
  const days = tier.isPaid && !tier.isAdmin ? daysLeft(entitlement?.expires_at) : null;
  const expiring = days !== null && days <= 5 && entitlement?.source === 'subscription';
  const ind = data?.indicators;
  const hasActivity = Boolean(ind && (ind.tests_taken > 0 || ind.essays.count > 0));

  // Daily Goal calculation
  const storedPlan = useMemo(() => getStoredPlan(), [user?.onboarding_completed, user?.daily_goal_minutes]);
  const goalMinutes = useMemo(() => {
    const fromApi = Number(data?.daily_goal?.goal_minutes);
    if (Number.isFinite(fromApi) && fromApi > 0) return fromApi;
    const fromUser = Number(user?.daily_goal_minutes || (user?.daily_plan_summary as Record<string, unknown> | undefined)?.daily_minutes);
    if (Number.isFinite(fromUser) && fromUser > 0) return fromUser;
    const fromLocal = Number(storedPlan.daily_goal_minutes || storedPlan.daily_minutes);
    if (Number.isFinite(fromLocal) && fromLocal > 0) return fromLocal;
    return 15;
  }, [data?.daily_goal?.goal_minutes, user?.daily_goal_minutes, user?.daily_plan_summary, storedPlan]);

  const completedMinutes = useMemo(() => {
    const fromApi = Number(data?.daily_goal?.completed_minutes);
    const todayStr = new Date().toDateString();
    let mins = 0;
    if (data?.recent) {
      for (const r of data.recent) {
        if (r.finished_at && new Date(r.finished_at).toDateString() === todayStr) {
          mins += 15;
        }
      }
    }
    if (data?.indicators?.essays?.recent) {
      for (const e of data.indicators.essays.recent) {
        if (e.updated_at && new Date(e.updated_at).toDateString() === todayStr) {
          mins += 10;
        }
      }
    }
    const fromSummary = Number((user?.daily_plan_summary as Record<string, unknown> | undefined)?.completed_minutes || storedPlan.completed_minutes || 0);
    return Math.max(
      Number.isFinite(fromApi) ? fromApi : 0,
      mins,
      Number.isFinite(fromSummary) ? fromSummary : 0,
    );
  }, [data, user?.daily_plan_summary, storedPlan]);

  const dailyProgressPct = Math.min(100, Math.round((completedMinutes / Math.max(1, goalMinutes)) * 100));
  const trackBadgeLabel = resolveTrackBadge(data?.daily_goal?.target_exam || user?.exam_target || user?.target_exam, storedPlan, subject);

  const dateOf = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(lang) : '');
  const sectionName = (code: string, fallback: string) => t(`omr_section_${code}`, fallback || code);

  const partLabel = (w: DashboardWeakPart) => {
    if (w.label) return w.label;
    return (
      [
        w.section_code ? sectionName(w.section_code, w.section_name) : '',
        w.part ? `${t('rv_part')} ${w.part}` : '',
      ]
        .filter(Boolean)
        .join(', ') + ` (${t(`rv_type_${w.question_type}`, w.question_type)})`
    );
  };

  const weakPracticeUrl = (w: DashboardWeakPart) =>
    `/tests?skill=${encodeURIComponent(w.section_code || '')}&type=${encodeURIComponent(w.question_type || '')}&mode=practice`;

  const recentSummary = (r: DashboardRecent): string => {
    if (r.trial) return `${t('dsh_trial_tag')}: ${r.correct}/${r.total}`;
    if (r.sections.length > 1) {
      return r.sections.map((s) => `${sectionName(s.code, s.name)} ${Math.round(s.score)}/${s.max}`).join(' · ');
    }
    if (r.kind === 'bmb') {
      return `${Math.round(r.percentage)}%${r.grade ? ` · ${t('dsh_grade')} ${r.grade}` : ''}`;
    }
    return `${r.correct}/${r.total}`;
  };

  const indicators: { label: string; value: string; note?: string }[] = [];
  if (ind) {
    indicators.push({ label: t('dsh_ind_tests'), value: String(ind.tests_taken) });
    if (subject === 'english') {
      indicators.push({
        label: t('dsh_ind_listening'),
        value: ind.best_sections.LISTENING != null ? String(ind.best_sections.LISTENING) : '—',
        note: ind.best_sections.LISTENING != null ? t('dsh_ind_of_75') : undefined,
      });
      indicators.push({
        label: t('dsh_ind_reading'),
        value: ind.best_sections.READING != null ? String(ind.best_sections.READING) : '—',
        note: ind.best_sections.READING != null ? t('dsh_ind_of_75') : undefined,
      });
    } else {
      indicators.push({
        label: t('dsh_ind_avg'),
        value: ind.average_percentage != null ? `${Math.round(ind.average_percentage)}%` : '—',
      });
      indicators.push({ label: t('dsh_ind_best_grade'), value: ind.best_grade || '—' });
    }
    indicators.push({
      label: t('dsh_ind_essays'),
      value: String(ind.essays.count),
      note:
        ind.essays.last_score != null && ind.essays.last_max
          ? t('dsh_ind_essay_last').replace('{score}', String(Math.round(ind.essays.last_score))).replace('{max}', String(ind.essays.last_max))
          : undefined,
    });
  }

  return (
    <div className="dsh">
      <header className="dsh-head">
        <div className="dsh-head__text">
          <h1>
            {t('dsh_hello')} {name}
          </h1>
          <div className="dsh-head__meta">
            <span className="dsh-subject">{t(subject === 'english' ? 'subject_english' : 'subject_uzbek')}</span>
            <PlanBadge variant="chip" />
          </div>
        </div>
        {isStudent && (
          <div className="dsh-primary">
            {data?.resume ? (
              <>
                <Link to={data.resume.route} className="ui-btn ui-btn--primary dsh-primary__btn">
                  {t('dsh_resume')}
                </Link>
                <span className="dsh-primary__hint">{t('dsh_resume_hint').replace('{title}', data.resume.title)}</span>
              </>
            ) : (
              <Link to="/tests" className="ui-btn ui-btn--primary dsh-primary__btn">
                {t('dsh_start_mock')}
              </Link>
            )}
          </div>
        )}
      </header>

      {/* Daily Personal Goal Banner (Kunlik shaxsiy reja) */}
      {isStudent && (
        <section className="dsh-daily" aria-label="Kunlik shaxsiy reja">
          <div className="dsh-daily__top">
            <div className="dsh-daily__title-wrap">
              <p className="dsh-daily__title">
                🔥 Bugungi reja: {completedMinutes} / {goalMinutes} daqiqa
              </p>
              <span className="dsh-daily__badge">{trackBadgeLabel}</span>
            </div>
            <Link to="/onboarding" className="dsh-daily__edit">
              ⚙️ Rejani o&apos;zgartirish
            </Link>
          </div>
          <div
            className="dsh-daily__bar"
            role="progressbar"
            aria-valuenow={dailyProgressPct}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="dsh-daily__fill" style={{ width: `${Math.max(6, dailyProgressPct)}%` }} />
          </div>
        </section>
      )}

      {pendingReceipt && (
        <div className="dsh-banner" role="status">
          <span>
            <b>{t('dsh_receipt_title')}</b> · {pendingReceipt.plan.toUpperCase()}
          </span>
          <Link to="/subscribe" className="ui-btn ui-btn--sm">
            {t('dsh_receipt_view')}
          </Link>
        </div>
      )}
      {expiring && days !== null && (
        <div className="dsh-banner" role="status">
          <span>{t('dsh_expiry').replace('{n}', String(days))}</span>
          <Link to="/subscribe" className="ui-btn ui-btn--sm">
            {t('dsh_expiry_renew')}
          </Link>
        </div>
      )}

      {failed && (
        <div className="dsh-card dsh-empty" role="alert">
          <p>{t('dsh_error')}</p>
          <button type="button" className="ui-btn" onClick={() => load()}>
            {t('error_retry')}
          </button>
        </div>
      )}

      {/* Structured Multi-Card Shimmer Skeleton */}
      {!data && !failed && (
        <div className="dsh-skeleton-grid" aria-busy="true" aria-label="Yuklanmoqda">
          {/* Hero Skeleton */}
          <div className="dsh-skeleton" style={{ padding: 20, minHeight: 88, display: 'grid', gap: 10 }}>
            <div className="dsh-skeleton-line" style={{ width: '48%', height: 18 }} />
            <div className="dsh-skeleton-line" style={{ width: '75%', height: 12 }} />
          </div>

          {/* 4 Metric Card Skeletons */}
          <div className="dsh-stats">
            {[0, 1, 2, 3].map((idx) => (
              <div key={idx} className="dsh-skeleton" style={{ padding: 16, minHeight: 84, display: 'grid', gap: 8 }}>
                <div className="dsh-skeleton-line" style={{ width: '55%', height: 12 }} />
                <div className="dsh-skeleton-line" style={{ width: '40%', height: 26 }} />
              </div>
            ))}
          </div>

          {/* 2 Panel Skeletons */}
          <div className="dsh-skeleton-panels">
            {[0, 1].map((idx) => (
              <div key={idx} className="dsh-skeleton" style={{ padding: 18, minHeight: 150, display: 'grid', gap: 12 }}>
                <div className="dsh-skeleton-line" style={{ width: '42%', height: 16 }} />
                <div className="dsh-skeleton-line" style={{ width: '90%', height: 14 }} />
                <div className="dsh-skeleton-line" style={{ width: '82%', height: 14 }} />
                <div className="dsh-skeleton-line" style={{ width: '65%', height: 14 }} />
              </div>
            ))}
          </div>
        </div>
      )}

      {data && !hasActivity && !failed && (
        <section className="dsh-card dsh-empty">
          <h2>{t('dsh_empty_title')}</h2>
          <p>{t(subject === 'english' ? 'dsh_empty_english' : 'dsh_empty_uzbek')}</p>
        </section>
      )}

      {data && hasActivity && (
        <>
          <section className="dsh-stats" aria-label={t('dsh_ind_tests')}>
            {indicators.map((i) => (
              <div key={i.label} className="dsh-stat">
                <span className="dsh-stat__label">{i.label}</span>
                <strong className="dsh-stat__value">{i.value}</strong>
                {i.note && <span className="dsh-stat__note">{i.note}</span>}
              </div>
            ))}
          </section>

          {data.recent.length > 0 && (
            <section className="dsh-card">
              <div className="dsh-card__head">
                <h2>{t('dsh_recent_title')}</h2>
                <Link to="/results">{t('dsh_recent_all')}</Link>
              </div>
              <ul className="dsh-list">
                {data.recent.map((r) => (
                  <li key={r.result_id}>
                    <div className="dsh-list__main">
                      <strong>{r.title}</strong>
                      <span>{recentSummary(r)}</span>
                      <small>{dateOf(r.finished_at)}</small>
                    </div>
                    <Link to={`/results/${r.result_id}`} className="ui-btn ui-btn--sm">
                      {t('details')}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.weak_parts.length > 0 && (
            <section className="dsh-card">
              <div className="dsh-card__head">
                <h2>{t('dsh_weak_title')}</h2>
                <small>{t('dsh_weak_hint')}</small>
              </div>
              <ul className="dsh-list">
                {data.weak_parts.map((w) => {
                  const targetUrl = weakPracticeUrl(w);
                  return (
                    <li
                      key={`${w.section_code}|${w.part}|${w.question_type}`}
                      className="dsh-weak-item"
                      onClick={() => navigate(targetUrl)}
                    >
                      <div className="dsh-list__main">
                        <strong>{partLabel(w)}</strong>
                        <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                          Natija: <b className="dsh-ratio">{w.correct}/{w.total}</b> to&apos;g&apos;ri
                        </span>
                      </div>
                      <Link
                        to={targetUrl}
                        className="dsh-weak-pill"
                        onClick={(e) => e.stopPropagation()}
                      >
                        🎯 Mashq qilish →
                      </Link>
                    </li>
                  );
                })}
              </ul>
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <Link
                  to={
                    data.weak_parts[0]
                      ? weakPracticeUrl(data.weak_parts[0])
                      : '/tests?mode=practice'
                  }
                  className="dsh-weak-pill"
                >
                  🎯 {t('dsh_weak_practice', 'Mashq qilish')} →
                </Link>
              </div>
            </section>
          )}

          {data.goal && (
            <section className="dsh-card">
              <div className="dsh-card__head">
                <h2>{t('dsh_goal_title')}</h2>
              </div>
              <p className="dsh-goal">
                <b>{t('dsh_goal_target').replace('{target}', data.goal.target)}</b>
                <span>
                  {data.goal.current
                    ? t('dsh_goal_current').replace('{current}', data.goal.current)
                    : t('dsh_goal_none')}
                </span>
                {data.goal.reached === true && <span className="dsh-goal__ok">{t('dsh_goal_reached')}</span>}
                {data.goal.reached === false && <span>{t('dsh_goal_gap')}</span>}
              </p>
            </section>
          )}
        </>
      )}

      {data && isStudent && !hasActivity && (data.recommended_practice || []).length > 0 && (
        <section className="dsh-card">
          <div className="dsh-card__head">
            <h2>{t('dsh_weak_title')}</h2>
            <small>Yo&apos;nalishingiz bo&apos;yicha tavsiya etilgan mashqlar</small>
          </div>
          <ul className="dsh-list">
            {(data.recommended_practice || []).map((w) => {
              const targetUrl = weakPracticeUrl(w);
              return (
                <li
                  key={`${w.section_code}|${w.part}|${w.question_type}`}
                  className="dsh-weak-item"
                  onClick={() => navigate(targetUrl)}
                >
                  <div className="dsh-list__main">
                    <strong>{partLabel(w)}</strong>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                      Diagnostik mashq · Bo&apos;lim bo&apos;yicha amaliyot
                    </span>
                  </div>
                  <Link
                    to={targetUrl}
                    className="dsh-weak-pill"
                    onClick={(e) => e.stopPropagation()}
                  >
                    🎯 Mashq qilish →
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {data && isStudent && (
        <section className="dsh-card">
          <div className="dsh-card__head">
            <h2>{t('dsh_essays_title')}</h2>
            <Link to="/essays">{t('dsh_essays_all')}</Link>
          </div>
          {data.indicators.essays.recent.length === 0 ? (
            <div className="dsh-empty-row">
              <p>{t('dsh_essays_empty')}</p>
              <Link to="/essays" className="ui-btn ui-btn--sm">
                {t('es_write')}
              </Link>
            </div>
          ) : (
            <ul className="dsh-list">
              {data.indicators.essays.recent.map((e) => {
                const st = essayStatus(e.status);
                const href = st === 'draft' && e.topic_id ? `/essays/write/${e.topic_id}` : `/essays/result/${e.id}`;
                return (
                  <li key={e.id}>
                    <div className="dsh-list__main">
                      <strong className="clamp-2">{e.title || t('es_untitled')}</strong>
                      <span>
                        {t(`es_kind_${essayKind(e)}`)} · {t(`es_status_${st}`)}
                        {st === 'graded' && scoreLabel(e, t) ? ` · ${scoreLabel(e, t)}` : ''}
                      </span>
                    </div>
                    <Link to={href} className="ui-btn ui-btn--sm">
                      {t('details')}
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {isStudent && <ReferralCard variant="compact" />}

      <OnboardingModal isOpen={onboardingOpen} onClose={() => setOnboardingOpen(false)} onSuccess={() => setOnboardingOpen(false)} />
    </div>
  );
}
