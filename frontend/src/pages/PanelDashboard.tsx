import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Panel, type PanelDashboardResponse } from '../lib/api';
import { num, str } from '../lib/billingPanelGames';
import {
  CreditCardIcon,
  FileTextIcon,
  PenLineIcon,
  ScrollTextIcon,
  ShieldCheckIcon,
  TargetIcon,
  UsersIcon,
} from '../components/icons';

/**
 * Admin control panel home — deliberately distinct from the student
 * Dashboard: admin hero banner, platform-wide live stats, quick actions
 * for every management area, then inventory tables.
 * Backend: GET /api/v1/panel/dashboard/ → { tests{...}, questions,
 * essay_topics, users{...}, new_users_today, attempts{total,today},
 * essays{total,awaiting_review}, pending_payments, active_subscriptions,
 * role_breakdown[], recent_tests[], recent_topics[] }.
 */
export default function PanelDashboard() {
  const { t } = useLang();
  const [d, setD] = useState<PanelDashboardResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Panel.dashboard()
      .then((r) => setD(r))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, []);

  if (err) return <p className="error" role="alert">{err}</p>;
  if (!d) return <p className="muted" role="status" aria-live="polite">{t('loading')}</p>;

  const tests = d.tests ?? { total: 0, published: 0, draft: 0, archived: 0 };
  const users = d.users ?? { total: 0, active: 0, blocked: 0 };
  const attempts = d.attempts ?? { total: 0, today: 0 };
  const essays = d.essays ?? { total: 0, pending_ai: 0, awaiting_review: 0 };
  const roles = (d.role_breakdown ?? []).filter((r) => r && typeof r.key === 'string');
  const recentTests = (d.recent_tests ?? []).slice(0, 5);
  const recentTopics = (d.recent_topics ?? []).slice(0, 5);

  return (
    <div>
      <div className="card admin-hero">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="admin-hero-badge">
            <ShieldCheckIcon size={28} className="ico" />
          </span>
          <div>
            <h1 style={{ margin: 0 }}>{t('panel_dashboard')}</h1>
            <p className="muted" style={{ margin: '4px 0 0' }}>
              {t('panel_admin_hero_sub')}
            </p>
          </div>
        </div>
        <div className="admin-hero-stats">
          <div>
            <span className="stat-value">{num(attempts.today)}</span>
            <span className="stat-label">{t('panel_attempts_today')}</span>
          </div>
          <div>
            <span className="stat-value">{num(d.new_users_today)}</span>
            <span className="stat-label">{t('panel_new_users')}</span>
          </div>
          <div>
            <span className="stat-value">{num(essays.pending_ai)}</span>
            <span className="stat-label">{t('panel_essays_pending_ai')}</span>
          </div>
          <div>
            <span className="stat-value">{num(essays.awaiting_review)}</span>
            <span className="stat-label">{t('panel_essays_awaiting_review')}</span>
          </div>
          <div>
            <span className="stat-value">{num(d.pending_payments)}</span>
            <span className="stat-label">{t('panel_payments_pending')}</span>
          </div>
        </div>
      </div>

      <h2>{t('panel_quick_actions')}</h2>
      <div className="grid">
        <Link className="card stat admin-action" to="/panel/tests/new">
          <span className="stat-label"><FileTextIcon size={15} className="ico" /> {t('panel_action_new_test')}</span>
          <span className="muted small">{t('panel_action_new_test_hint')}</span>
        </Link>
        <Link className="card stat admin-action" to="/panel/topics">
          <span className="stat-label"><PenLineIcon size={15} className="ico" /> {t('panel_action_new_topic')}</span>
          <span className="muted small">{t('panel_action_new_topic_hint')}</span>
        </Link>
        <Link className="card stat admin-action" to="/teacher/essays">
          <span className="stat-label"><ScrollTextIcon size={15} className="ico" /> {t('panel_action_review_essays')}</span>
          <span className="muted small">
            {t('panel_essays_pending')}: {num(essays.awaiting_review)}
          </span>
        </Link>
        <Link className="card stat admin-action" to="/panel/users">
          <span className="stat-label"><UsersIcon size={15} className="ico" /> {t('panel_action_manage_users')}</span>
          <span className="muted small">
            {t('panel_active')}: {num(users.active)} · {t('panel_blocked')}: {num(users.blocked)}
          </span>
        </Link>
      </div>

      <h2>{t('panel_platform')}</h2>
      <div className="grid grid-4-xl">
        <div className="card stat admin-stat-gradient-blue">
          <span className="stat-label">{t('tests')}</span>
          <span className="stat-value">{num(tests.total)}</span>
          <span className="muted small">
            {t('status_published')}: {num(tests.published)} · {t('status_draft')}:{' '}
            {num(tests.draft)} · {t('status_archived')}: {num(tests.archived)}
          </span>
          <Link to="/panel/tests">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-green">
          <span className="stat-label">{t('questions')}</span>
          <span className="stat-value">{num(d.questions)}</span>
          <span className="muted small">{t('panel_all_questions_hint')}</span>
        </div>
        <div className="card stat admin-stat-gradient-amber">
          <span className="stat-label">{t('essay_topics')}</span>
          <span className="stat-value">{num(d.essay_topics)}</span>
          <span className="muted small">
            {t('panel_essays_total')}: {num(essays.total)}
          </span>
          <Link to="/panel/topics">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-purple">
          <span className="stat-label">{t('users')}</span>
          <span className="stat-value">{num(users.total)}</span>
          <span className="muted small">
            {t('panel_active')}: {num(users.active)} · {t('panel_blocked')}: {num(users.blocked)}
          </span>
          <Link to="/panel/users">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-green">
          <span className="stat-label"><TargetIcon size={15} className="ico" /> {t('panel_attempts_total')}</span>
          <span className="stat-value">{num(attempts.total)}</span>
          <span className="muted small">
            {t('panel_attempts_today')}: {num(attempts.today)}
          </span>
          <Link to="/analytics">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-purple">
          <span className="stat-label"><CreditCardIcon size={15} className="ico" /> {t('panel_subscriptions')}</span>
          <span className="stat-value">{num(d.active_subscriptions)}</span>
          <span className="muted small">
            {t('panel_payments_pending')}: {num(d.pending_payments)}
          </span>
        </div>
      </div>

      <h2>{t('panel_users_by_role')}</h2>
      <div className="grid">
        {roles.map((r) => (
          <div key={r.key} className="card stat">
            <span className="stat-label">{t(`role_${r.key}`) !== `role_${r.key}` ? t(`role_${r.key}`) : r.key}</span>
            <span className="stat-value">{r.count}</span>
          </div>
        ))}
      </div>

      <h2>{t('panel_recent_tests')}</h2>
      {recentTests.length === 0 ? (
        <p className="muted">{t('no_tests_yet')}</p>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_test_name')}</th>
                <th>{t('th_course')}</th>
                <th>{t('th_questions')}</th>
                <th>{t('status')}</th>
              </tr>
            </thead>
            <tbody>
              {recentTests.map((x) => (
                <tr key={str(x.id)}>
                  <td>
                    <Link to={`/panel/tests/${str(x.id)}/questions`}>{str(x.title)}</Link>
                  </td>
                  <td>{str(x.course_title)}</td>
                  <td>{str(x.q_count ?? '', '—')}</td>
                  <td>
                    <span className="badge">{str(x.status)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>{t('panel_recent_topics')}</h2>
      {recentTopics.length === 0 ? (
        <div className="card">
          <p>
            <strong>{t('panel_no_topics')}</strong>
          </p>
          <p className="muted small">{t('panel_no_topics_hint')}</p>
          <Link className="btn primary sm" to="/panel/topics">
            {t('panel_new_topic')}
          </Link>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_topic')}</th>
                <th>{t('panel_category')}</th>
                <th>{t('words')}</th>
              </tr>
            </thead>
            <tbody>
              {recentTopics.map((x) => (
                <tr key={str(x.id)}>
                  <td>{str(x.title)}</td>
                  <td>
                    <span className="badge">{str(x.category)}</span>
                  </td>
                  <td className="muted small">
                    {str(x.word_limit_min)}-{str(x.word_limit_max)} {t('words')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
