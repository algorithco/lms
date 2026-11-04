import { useCallback, useEffect, useState } from 'react';
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

/** Student dashboard: one main action, a few real indicators, recent results, weak parts, goal. */
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

  const dateOf = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(lang) : '');
  const sectionName = (code: string, fallback: string) => t(`omr_section_${code}`, fallback || code);

  const partLabel = (w: DashboardWeakPart) =>
    [
      w.section_code ? sectionName(w.section_code, w.section_name) : '',
      w.part ? `${t('rv_part')} ${w.part}` : '',
    ]
      .filter(Boolean)
      .join(', ') + ` (${t(`rv_type_${w.question_type}`, w.question_type)})`;

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

      {!data && !failed && <div className="dsh-card dsh-skeleton" aria-busy="true" />}

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
                {data.weak_parts.map((w) => (
                  <li key={`${w.section_code}|${w.part}|${w.question_type}`}>
                    <div className="dsh-list__main">
                      <strong>{partLabel(w)}</strong>
                    </div>
                    <b className="dsh-ratio">
                      {w.correct}/{w.total}
                    </b>
                  </li>
                ))}
              </ul>
              <Link to="/tests" className="ui-btn ui-btn--sm">
                {t('dsh_weak_practice')}
              </Link>
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
