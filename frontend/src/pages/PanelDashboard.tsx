import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Panel } from '../lib/api';
import { num, str } from '../lib/billingPanelGames';
import { ShieldCheckIcon } from '../components/icons';

/**
 * Admin dashboard — parity with templates/panel/dashboard.html.
 * Backend: GET /api/v1/panel/dashboard/ → { tests{total,published,draft,
 * archived}, questions, essay_topics, users{total,active,blocked},
 * role_breakdown[{key,count}], recent_tests[], recent_topics[] }.
 */
export default function PanelDashboard() {
  const { t } = useLang();
  const [d, setD] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Panel.dashboard()
      .then((r) => setD(r as unknown as Record<string, unknown>))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, []);

  if (err) return <p className="error">{err}</p>;
  if (!d) return <p className="muted">{t('loading')}</p>;

  const tests = (d.tests ?? {}) as Record<string, number>;
  const users = (d.users ?? {}) as Record<string, number>;
  const roles = ((d.role_breakdown ?? []) as { key: string; count: number }[]).filter(
    (r) => r && typeof r.key === 'string',
  );
  const recentTests = ((d.recent_tests ?? []) as Record<string, unknown>[]).slice(0, 5);
  const recentTopics = ((d.recent_topics ?? []) as Record<string, unknown>[]).slice(0, 5);

  return (
    <div>
      <h1>
        <ShieldCheckIcon size={24} className="ico" /> {t('panel_dashboard')}
      </h1>
      <div className="grid">
        <div className="card stat stat-gradient-blue">
          <span className="stat-label">{t('tests')}</span>
          <span className="stat-value">{num(tests.total)}</span>
          <span className="muted small">
            {t('status_published')}: {num(tests.published)} · {t('status_draft')}:{' '}
            {num(tests.draft)} · {t('status_archived')}: {num(tests.archived)}
          </span>
          <Link to="/panel/tests">{t('view_all')} →</Link>
        </div>
        <div className="card stat stat-gradient-green">
          <span className="stat-label">{t('questions')}</span>
          <span className="stat-value">{num(d.questions)}</span>
          <span className="muted small">{t('panel_all_questions_hint')}</span>
        </div>
        <div className="card stat stat-gradient-amber">
          <span className="stat-label">{t('essay_topics')}</span>
          <span className="stat-value">{num(d.essay_topics)}</span>
          <span className="muted small">{t('panel_topics_hint')}</span>
          <Link to="/panel/topics">{t('view_all')} →</Link>
        </div>
        <div className="card stat stat-gradient-purple">
          <span className="stat-label">{t('users')}</span>
          <span className="stat-value">{num(users.total)}</span>
          <span className="muted small">
            {t('panel_active')}: {num(users.active)} · {t('panel_blocked')}: {num(users.blocked)}
          </span>
          <Link to="/panel/users">{t('view_all')} →</Link>
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
